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
