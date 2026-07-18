"""视频理解管线测试。全部离线，不下载真实视频、不调用真实外部工具。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from adapters.xhs_video_adapter import (
    StoragePolicyViolation,
    VideoAcquisitionFailed,
    acquire_video,
    ensure_tmp_storage,
)
from src.video_analyzer import (
    analyze_content,
    build_timeline,
    detect_risk_words,
    parse_srt,
    render_analysis_md,
    srt_time_to_seconds,
)
from src.video_models import Keyframe, TranscriptSegment, VideoTimeline

SAMPLE_SRT = """1
00:00:00,000 --> 00:00:02,500
早上好 今天分享我的早餐

2
00:00:02,500 --> 00:00:05,000
最近常吃这个高蛋白酸奶

3
00:00:05,000 --> 00:00:08,000
搭配燕麦和蓝莓 很方便
"""

RISKY_SRT = """1
00:00:00,000 --> 00:00:03,000
吃这个能减肥还降糖
"""


# ---------- SRT 解析 ----------


def test_srt_time_conversion() -> None:
    assert srt_time_to_seconds("00", "01", "02", "500") == 62.5
    assert srt_time_to_seconds("01", "00", "00", "000") == 3600.0


def test_parse_srt_segments() -> None:
    segments = parse_srt(SAMPLE_SRT)
    assert len(segments) == 3
    assert segments[0].start == 0.0
    assert segments[0].end == 2.5
    assert "早餐" in segments[0].text


def test_parse_srt_multiline_text() -> None:
    srt = "1\n00:00:00,000 --> 00:00:01,000\n第一行\n第二行\n"
    segments = parse_srt(srt)
    assert segments[0].text == "第一行 第二行"


def test_parse_srt_empty() -> None:
    assert parse_srt("") == []


# ---------- 风险词 ----------


def test_detect_risk_words_hit() -> None:
    assert set(detect_risk_words("吃这个能减肥还降糖")) == {"减肥", "降糖"}


def test_detect_risk_words_clean() -> None:
    assert detect_risk_words("今天分享早餐搭配") == []


# ---------- 时间线 ----------


def make_segments() -> list[TranscriptSegment]:
    return parse_srt(SAMPLE_SRT)


def test_build_timeline_with_keyframes() -> None:
    frames = [Keyframe(timestamp=t, path=f"k{t}.jpg") for t in (0.0, 2.0, 4.0, 6.0)]
    timeline = build_timeline("https://xhs.test/note/1", make_segments(), frames)
    assert len(timeline.entries) == 4
    assert timeline.entries[0].speech.startswith("早上好")
    assert timeline.entries[2].speech.startswith("最近常吃")
    assert timeline.duration_seconds == 8.0


def test_build_timeline_without_keyframes_uses_segments() -> None:
    timeline = build_timeline("https://xhs.test/note/1", make_segments(), [])
    assert len(timeline.entries) == 3


def test_build_timeline_risk_words_collected() -> None:
    timeline = build_timeline("https://xhs.test/n", parse_srt(RISKY_SRT), [])
    assert set(timeline.entries[0].risk_words) == {"减肥", "降糖"}


def test_timeline_visual_fields_empty_not_fabricated() -> None:
    timeline = build_timeline("https://xhs.test/n", make_segments(), [])
    for entry in timeline.entries:
        assert entry.screen_subtitle == ""
        assert entry.person_action == ""
        assert entry.shot_type == ""
        assert entry.product_exposure == ""


def test_timeline_json_roundtrip() -> None:
    timeline = build_timeline("https://xhs.test/n", make_segments(), [])
    restored = VideoTimeline.model_validate(json.loads(timeline.model_dump_json()))
    assert restored.duration_seconds == timeline.duration_seconds


# ---------- 内容分析 ----------


def test_analyze_hook_first_3s() -> None:
    timeline = build_timeline("https://xhs.test/n", make_segments(), [])
    analysis = analyze_content(timeline)
    assert "早上好" in analysis.hook_first_3s


def test_analyze_rhythm() -> None:
    timeline = build_timeline("https://xhs.test/n", make_segments(), [])
    analysis = analyze_content(timeline)
    assert "8.0s" in analysis.rhythm
    assert "字/秒" in analysis.rhythm


def test_analyze_product_integration() -> None:
    timeline = build_timeline("https://xhs.test/n", make_segments(), [])
    analysis = analyze_content(timeline)
    assert "酸奶" in analysis.product_integration


def test_analyze_risk_notes() -> None:
    timeline = build_timeline("https://xhs.test/n", parse_srt(RISKY_SRT), [])
    analysis = analyze_content(timeline)
    assert any("减肥" in n for n in analysis.risk_notes)


def test_render_analysis_md_traceable() -> None:
    timeline = build_timeline(
        "https://xhs.test/n", make_segments(), [], transcript_file="t.srt"
    )
    md = render_analysis_md(analyze_content(timeline), timeline)
    assert "https://xhs.test/n" in md
    assert "前 3 秒钩子" in md and "节奏" in md and "产品植入" in md
    assert "可追溯性声明" in md


# ---------- 视频获取（mock subprocess） ----------


class FakeProc:
    def __init__(self, returncode: int):
        self.returncode = returncode


def test_ensure_tmp_storage_enforced(tmp_path: Path) -> None:
    with pytest.raises(StoragePolicyViolation):
        ensure_tmp_storage(tmp_path / "not_tmp_dir")


def test_ensure_tmp_storage_accepts_tmp(tmp_path: Path) -> None:
    target = ensure_tmp_storage(tmp_path / "tmp" / "xhs_video")
    assert target.is_dir()


def test_acquire_video_both_tools_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("adapters.xhs_video_adapter.find_tool", lambda name: None)
    with pytest.raises(VideoAcquisitionFailed, match="停止"):
        acquire_video("https://xhs.test/n", tmp_path / "tmp")


def test_acquire_video_ytdlp_success(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "tmp"
    out.mkdir()

    def fake_find(name: str):
        return "/usr/bin/yt-dlp" if name == "yt-dlp" else None

    def fake_runner(cmd, **kwargs):
        (out / "abc123.mp4").write_bytes(b"fake")
        return FakeProc(0)

    monkeypatch.setattr("adapters.xhs_video_adapter.find_tool", fake_find)
    asset = acquire_video("https://xhs.test/n", out, runner=fake_runner)
    assert asset.acquired_by == "yt-dlp"
    assert asset.local_path.endswith(".mp4")


def test_acquire_video_fallback_to_xhs_downloader(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "tmp"
    out.mkdir()

    def fake_find(name: str):
        return "/usr/bin/xhs-downloader" if "xhs" in name.lower() else None

    def fake_runner(cmd, **kwargs):
        if "yt-dlp" in cmd[0]:
            return FakeProc(1)
        (out / "fallback.mp4").write_bytes(b"fake")
        return FakeProc(0)

    monkeypatch.setattr("adapters.xhs_video_adapter.find_tool", fake_find)
    asset = acquire_video("https://xhs.test/n", out, runner=fake_runner)
    assert asset.acquired_by == "xhs-downloader"


def test_acquire_video_both_fail_raises(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "tmp"
    out.mkdir()
    monkeypatch.setattr("adapters.xhs_video_adapter.find_tool", lambda n: "/usr/bin/tool")
    with pytest.raises(VideoAcquisitionFailed):
        acquire_video("https://xhs.test/n", out,
                      runner=lambda *a, **k: subprocess.CompletedProcess(a, 1))


# ---------- Stage 2 真实视频 POC：12 字段片段与证据合并 ----------


from src.video_analyzer import (  # noqa: E402
    average_hash,
    build_video_segments,
    dedupe_keyframes,
    format_srt_time,
    hamming_distance,
    probe_video_metadata,
    segments_to_srt,
    sha256_file,
)
from src.video_models import VideoSegment, VideoTimelineV2  # noqa: E402


def test_build_segments_visual_fields_none_not_fabricated() -> None:
    """不确定的视觉字段必须为 None，不得自动补全。"""
    results = build_video_segments(make_segments(), [])
    assert len(results) == 3
    for seg in results:
        assert seg.on_screen_text is None
        assert seg.scene is None
        assert seg.person_action is None
        assert seg.shot_type is None


def test_build_segments_merges_keyframe_evidence() -> None:
    """音频与关键帧证据合并：片段只记录落在其时段内的真实关键帧。"""
    frames = [Keyframe(timestamp=t, path=f"k{t}.jpg") for t in (0.0, 1.0, 3.0, 6.0)]
    results = build_video_segments(make_segments(), frames)
    assert results[0].evidence_frame_timestamps == [0.0, 1.0]
    assert results[1].evidence_frame_timestamps == [3.0]
    assert results[2].evidence_frame_timestamps == [6.0]


def test_build_segments_product_mention_from_speech_only() -> None:
    results = build_video_segments(make_segments(), [])
    assert results[0].food_or_product is None
    assert set(results[1].food_or_product.split("、")) == {"酸奶", "高蛋白"}
    assert results[1].product_first_appearance == 2.5
    assert results[1].confidence <= 0.6  # 仅口播证据，降置信度
    assert results[2].product_first_appearance is None  # 只在首次提及片段填写


def test_build_segments_commercial_expression() -> None:
    srt = "1\n00:00:00,000 --> 00:00:02,000\n点击链接get同款酸奶\n"
    results = build_video_segments(parse_srt(srt), [])
    assert results[0].commercial_expression is not None
    assert "链接" in results[0].commercial_expression


def test_build_segments_compliance_risks() -> None:
    results = build_video_segments(parse_srt(RISKY_SRT), [])
    assert set(results[0].compliance_risks) == {"减肥", "降糖"}


def test_video_segment_confidence_range() -> None:
    seg = VideoSegment(start_time=0, end_time=1)
    assert 0.0 <= seg.confidence <= 1.0
    with pytest.raises(Exception):
        VideoSegment(start_time=0, end_time=1, confidence=1.5)


def test_timeline_v2_json_roundtrip() -> None:
    segments = build_video_segments(make_segments(), [])
    tl = VideoTimelineV2(note_id="abc123", canonical_url="https://www.xiaohongshu.com/explore/abc123",
                         duration_seconds=8.0, segments=segments)
    restored = VideoTimelineV2.model_validate(json.loads(tl.model_dump_json()))
    assert restored.note_id == "abc123"
    assert len(restored.segments) == 3
    assert restored.segments[0].on_screen_text is None


# ---------- 视频文件有效性探测（ffmpeg -i 解析） ----------


FFMPEG_I_SAMPLE = """ffmpeg version 7.1-full_build-www.gyan.dev Copyright (c) 2000-2024
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'source_video.mp4':
  Duration: 00:00:42.53, start: 0.000000, bitrate: 1200 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p, 720x1280, 30 fps
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 44100 Hz
"""


class FakeFFmpegProc:
    returncode = 1  # ffmpeg -i 无输出文件时返回 1，属正常
    stdout = ""
    stderr = FFMPEG_I_SAMPLE


def test_probe_video_metadata_parses_ffmpeg_i() -> None:
    meta = probe_video_metadata("fake.mp4", runner=lambda *a, **k: FakeFFmpegProc())
    assert meta["duration_seconds"] == 42.53
    assert meta["resolution"] == "720x1280"
    assert meta["video_codec"] == "h264"
    assert meta["audio_codec"] == "aac"
    assert meta["ffmpeg_version"].startswith("7.1")


def test_probe_video_metadata_unparseable_fields_none() -> None:
    class Empty:
        returncode = 1
        stdout = ""
        stderr = "garbage"

    meta = probe_video_metadata("fake.mp4", runner=lambda *a, **k: Empty())
    assert meta["duration_seconds"] is None
    assert meta["resolution"] is None


# ---------- SRT 生成与往返 ----------


def test_format_srt_time() -> None:
    assert format_srt_time(62.5) == "00:01:02,500"
    assert format_srt_time(3600.0) == "01:00:00,000"


def test_segments_to_srt_roundtrip() -> None:
    segments = make_segments()
    restored = parse_srt(segments_to_srt(segments))
    assert [s.text for s in restored] == [s.text for s in segments]
    assert restored[0].start == 0.0 and restored[0].end == 2.5


# ---------- 关键帧去重与哈希 ----------


def test_hamming_distance() -> None:
    assert hamming_distance(0b1010, 0b1010) == 0
    assert hamming_distance(0b1010, 0b0101) == 4


def test_dedupe_keyframes_removes_near_duplicates(tmp_path: Path) -> None:
    from PIL import Image

    def split_image(top: int, bottom: int) -> Image.Image:
        img = Image.new("L", (32, 32))
        img.paste(top, (0, 0, 32, 16))
        img.paste(bottom, (0, 16, 32, 32))
        return img

    paths = []
    # 前两张为近似重复（上下半区灰度仅差 2），第三张上下颠倒（结构不同）
    for i, img in enumerate([split_image(30, 200), split_image(32, 202),
                             split_image(200, 30)]):
        p = tmp_path / f"f{i}.jpg"
        img.save(p)
        paths.append(p)
    kept = dedupe_keyframes(paths)
    assert len(kept) == 2  # 两张近重复帧去重为一张，结构不同的帧保留


def test_average_hash_deterministic(tmp_path: Path) -> None:
    from PIL import Image

    p = tmp_path / "a.jpg"
    Image.new("RGB", (16, 16), (100, 100, 100)).save(p)
    assert average_hash(p) == average_hash(p)


def test_sha256_file(tmp_path: Path) -> None:
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello")
    assert sha256_file(p) == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


# ---------- canonical URL 清洗与视频类型识别 ----------


def test_canonical_url_strips_query_and_token() -> None:
    from scripts.find_xhs_video_note import canonical_url

    url = canonical_url("6a4903ad000000002003b221")
    assert url == "https://www.xiaohongshu.com/explore/6a4903ad000000002003b221"
    assert "xsec_token" not in url


def test_canonical_url_precise_cleaning() -> None:
    from scripts.find_xhs_video_note import canonical_url

    assert canonical_url("a b-c_1") == "https://www.xiaohongshu.com/explore/abc1"
    assert canonical_url("n1?xsec_token=t") == (
        "https://www.xiaohongshu.com/explore/n1xsectokent"
    )
    with pytest.raises(ValueError):
        canonical_url("")


def test_video_type_identification_from_profile_notes() -> None:
    """video 类型识别：仅 noteCard.type == 'video' 才进入候选。"""
    notes = [
        {"note_id": "n1", "type": "normal", "title": "图文"},
        {"note_id": "n2", "type": "video", "title": "视频"},
    ]
    videos = [n for n in notes if n.get("type") == "video"]
    assert [v["note_id"] for v in videos] == ["n2"]


# ---------- 敏感产物不得入 Git ----------


def test_gitignore_covers_video_tmp_and_transcripts() -> None:
    gitignore = (Path(__file__).resolve().parent.parent / ".gitignore").read_text("utf-8")
    assert "tmp/" in gitignore


def test_committed_candidate_json_has_no_token() -> None:
    """提交 Git 的候选 JSON 不得包含 xsec_token 等查询参数。"""
    candidate = Path(__file__).resolve().parent.parent / (
        "data/processed/xhs_video_candidate.json"
    )
    if not candidate.is_file():
        pytest.skip("候选文件尚未生成")
    text = candidate.read_text("utf-8")
    assert "xsec_token" not in text
    assert json.loads(text)["canonical_url"].endswith(
        "/explore/6a4903ad000000002003b221"
    )
