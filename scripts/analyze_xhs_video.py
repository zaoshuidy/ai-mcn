"""Stage 2 真实视频端到端理解执行脚本（v2）。

流程：获取视频（yt-dlp → XHS-Downloader）→ ffmpeg -i 元数据校验
→ 抽音频 → 转写（VideoCaptioner CLI → faster-whisper 本地兜底）
→ 关键帧（每 2 秒 + 场景切换，近似去重）→ 12 字段 video_timeline.json
→ video_evidence_manifest.json → stage_2_real_video_analysis.md。

铁律：
- 原始视频/音频/完整转写/关键帧只存 tmp/xhs_video_poc/，一律不入 Git；
- Git 只提交 video_timeline.json、证据清单（含 SHA-256）、分析报告；
- 任一步骤失败如实停止并记录，不得绕过验证码/风控，不伪造产物；
- 视觉类字段无视觉模型标注，一律 None。

用法：
  python scripts/analyze_xhs_video.py                     # 从候选 JSON 读取并全链路执行
  python scripts/analyze_xhs_video.py --video-file tmp/xhs_video_poc/source_video.mp4
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.xhs_video_adapter import VideoAcquisitionFailed, acquire_video  # noqa: E402
from src.video_analyzer import (  # noqa: E402
    build_video_segments,
    dedupe_keyframes,
    extract_audio,
    extract_keyframes,
    generate_transcript,
    parse_srt,
    probe_video_metadata,
    sha256_file,
    transcribe_with_faster_whisper,
)
from src.video_models import (  # noqa: E402
    VideoEvidenceManifest,
    VideoTimelineV2,
)

TMP_DIR = ROOT / "tmp/xhs_video_poc"
CANDIDATE_JSON = ROOT / "data/processed/xhs_video_candidate.json"
TIMELINE_JSON = ROOT / "data/processed/video_timeline.json"
MANIFEST_JSON = ROOT / "data/processed/video_evidence_manifest.json"
ANALYSIS_MD = ROOT / "reports/stage_2_real_video_analysis.md"
WHISPER_LOCAL = ROOT / "tmp/whisper_models/tiny_local"


def transcribe(video_path: Path) -> Path:
    """VideoCaptioner CLI 优先；不可用回退 faster-whisper（CAND-010，本地）。"""
    try:
        _, srt_path = generate_transcript(video_path, TMP_DIR)
        print("[ASR] VideoCaptioner CLI 转写完成")
        return srt_path
    except FileNotFoundError:
        print("[ASR] VideoCaptioner 不可用，回退 faster-whisper 本地模型")
    audio = extract_audio(video_path, TMP_DIR / "audio.wav")
    print(f"[ASR] 音频抽取完成：{audio}")
    _, srt_path = transcribe_with_faster_whisper(audio, TMP_DIR,
                                                 model_size=str(WHISPER_LOCAL))
    print(f"[ASR] faster-whisper 转写完成：{srt_path}")
    return srt_path


def build_analysis_md(timeline: VideoTimelineV2, manifest: VideoEvidenceManifest,
                      scene_change_count: int) -> str:
    """基于真实数据生成分析报告骨架（10 个必答点，仅转述与时间戳证据）。"""
    segs = timeline.segments
    duration = timeline.duration_seconds
    hook = [s for s in segs if s.start_time < 3 and s.transcript_summary]
    hook_text = " / ".join(s.transcript_summary for s in hook) if hook else (
        "前 3 秒无口播（画面/音乐钩子，需人工查看关键帧标注）"
    )
    total_chars = sum(len(s.transcript_summary) for s in segs)
    speech_time = sum(s.end_time - s.start_time for s in segs)
    wps = round(total_chars / speech_time, 2) if speech_time > 0 else 0
    first_product = next(
        (s.product_first_appearance for s in segs if s.product_first_appearance is not None),
        None,
    )
    commercial = [s for s in segs if s.commercial_expression]
    risks = [(s.start_time, w) for s in segs for w in s.compliance_risks]
    avg_shot = round(duration / scene_change_count, 1) if scene_change_count else None

    def ts(seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    structure_lines = [
        f"- {ts(s.start_time)}–{ts(s.end_time)}：{s.transcript_summary[:30]}"
        for s in segs[:20]
    ]
    risk_lines = [f"- {ts(t)} 命中风险词「{w}」" for t, w in risks] or ["- 口播未命中风险词"]
    lines = [
        "# Stage 2 真实视频内容分析",
        "",
        f"- 笔记：{timeline.creator_name}《{timeline.title}》",
        f"- 来源：{timeline.canonical_url}",
        f"- 视频：{manifest.duration_seconds}s / {manifest.resolution} / "
        f"{manifest.video_codec}（SHA-256 见 video_evidence_manifest.json）",
        f"- 转写：{manifest.transcription_tool}（完整转写仅存 tmp/，不入 Git）",
        "",
        "## 1. 前 3 秒钩子",
        "",
        hook_text,
        "",
        "## 2. 标题与开场对应关系",
        "",
        f"标题《{timeline.title}》与开场口播的对应见上方钩子与时间线；",
        "具体呼应方式为人工读解项，本报告不臆断。",
        "",
        "## 3. 完整视频结构",
        "",
        f"共 {len(segs)} 个口播片段，总时长 {duration:.1f}s：",
        "",
        *structure_lines,
        "",
        "## 4. 镜头节奏",
        "",
        (
            f"场景切换关键帧 {scene_change_count} 个，平均镜头时长约 {avg_shot}s。"
            if avg_shot else "场景切换帧数量不足，无法估计镜头节奏。"
        ),
        "",
        "## 5. 口播、字幕、环境音关系",
        "",
        f"- 口播覆盖 {speech_time:.1f}s / {duration:.1f}s，语速 {wps} 字/秒；",
        "- 屏幕字幕：无视觉模型，未标注（None，不编造）；",
        "- 环境音：未做声源分离，非语音部分未标注。",
        "",
        "## 6. 食物/产品首次出现时间",
        "",
        (
            f"口播首次提及产品相关词：{first_product:.1f}s（仅口播证据，confidence≤0.6）"
            if first_product is not None else "口播未明确提及产品相关词"
        ),
        "",
        "## 7. 商业植入方式",
        "",
        (
            f"口播含商业表达 {len(commercial)} 处（如链接/同款/橱窗类词汇）"
            if commercial else "口播未检出商业表达词汇，倾向自然分享"
        ),
        "",
        "## 8. 可复用的高层风格",
        "",
        "结构层面可复用：开场钩子 → 主体叙述 → 结尾收口的时长分配与语速控制；",
        "具体数值见第 3、4、5 节。",
        "",
        "## 9. 不得复制的达人专属表达",
        "",
        "达人具体措辞、口头禅与人设化表达不复制，仅学习结构。",
        "",
        "## 10. 合规风险表达（减肥/燃脂/降糖/医疗）",
        "",
        *risk_lines,
        "",
        "> 可追溯性声明：以上结论仅来自真实转写文本、真实关键帧数量与页面观察数据；",
        "> 视觉类字段（字幕/场景/动作/镜头类型）无证据一律为 None，未编造。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-file", default="", help="已有视频文件（跳过获取）")
    args = parser.parse_args()

    candidate = json.loads(CANDIDATE_JSON.read_text("utf-8"))
    url = candidate["canonical_url"]
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 获取视频
    video_path = args.video_file
    acquired_by = "manual_input" if video_path else ""
    if not video_path:
        try:
            asset = acquire_video(url, TMP_DIR)
            video_path = asset.local_path
            acquired_by = asset.acquired_by
            print(f"[VIDEO] 获取成功（{acquired_by}）：{video_path}")
        except VideoAcquisitionFailed as exc:
            print(f"[STOP] 视频获取失败：{exc}")
            return 5
    vp = Path(video_path)
    if not vp.is_file() or vp.stat().st_size == 0:
        print(f"[STOP] 视频文件无效：{video_path}")
        return 5

    # 2. 元数据校验
    meta = probe_video_metadata(vp)
    print(f"[VIDEO] 元数据：{meta['duration_seconds']}s / {meta['resolution']} / "
          f"{meta['video_codec']}")
    if meta["duration_seconds"] is None:
        print("[STOP] 无法读取视频时长，文件可能损坏")
        return 5
    video_sha = sha256_file(vp)

    # 3. 转写
    try:
        srt_path = transcribe(vp)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"[STOP] 转写失败：{exc}")
        return 6
    segments = parse_srt(srt_path.read_text(encoding="utf-8"))
    print(f"[ASR] 转写片段 {len(segments)} 条")

    # 4. 关键帧 + 近似去重（仅存 tmp/）
    keyframe_dir = TMP_DIR / "keyframes"
    try:
        raw_frames = extract_keyframes(vp, keyframe_dir)
    except FileNotFoundError as exc:
        print(f"[STOP] 抽帧失败：{exc}")
        return 7
    scene_frames = [f for f in raw_frames if f.kind == "scene_change"]
    kept_paths = {str(p) for p in dedupe_keyframes(
        [Path(f.path) for f in raw_frames])}
    keyframes = [f for f in raw_frames if f.path in kept_paths]
    removed = len(raw_frames) - len(keyframes)
    print(f"[FRAME] 关键帧 {len(keyframes)} 张（去重移除 {removed} 张，"
          f"场景切换 {len(scene_frames)} 个）")

    # 5. 12 字段时间线
    v2_segments = build_video_segments(segments, keyframes)
    duration = max((s.end for s in segments), default=meta["duration_seconds"] or 0)
    timeline = VideoTimelineV2(
        note_id=candidate["note_id"],
        canonical_url=url,
        creator_name=candidate.get("creator_name", ""),
        title=candidate.get("title", ""),
        duration_seconds=round(duration, 3),
        observed_at=candidate.get("observed_at", ""),
        source="page_observed",
        human_verified=False,
        segments=v2_segments,
        notes="视觉类字段无视觉模型一律 None；转写为 faster-whisper tiny 本地模型"
              "（中文识别质量有限，仅作 POC 证据）；完整转写与关键帧仅存 tmp/",
    )
    TIMELINE_JSON.parent.mkdir(parents=True, exist_ok=True)
    TIMELINE_JSON.write_text(timeline.model_dump_json(indent=2), encoding="utf-8")
    print(f"[OUT] 时间线：{TIMELINE_JSON}（{len(v2_segments)} 段）")

    # 6. 证据清单
    manifest = VideoEvidenceManifest(
        note_id=candidate["note_id"],
        canonical_url=url,
        video_sha256=video_sha,
        video_bytes=vp.stat().st_size,
        duration_seconds=meta["duration_seconds"],
        resolution=meta["resolution"],
        video_codec=meta["video_codec"],
        audio_codec=meta["audio_codec"],
        acquired_by=acquired_by,
        acquired_at=datetime.now(timezone.utc).isoformat(),
        ffmpeg_version=meta["ffmpeg_version"],
        transcription_tool="faster-whisper tiny local (CAND-010)",
        keyframe_count=len(keyframes),
        keyframe_dir="tmp/xhs_video_poc/keyframes",
        transcript_srt_sha256=sha256_file(srt_path),
        notes="原始视频/音频/完整转写/关键帧仅存 tmp/，不入 Git",
    )
    MANIFEST_JSON.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    print(f"[OUT] 证据清单：{MANIFEST_JSON}")

    # 7. 分析报告
    ANALYSIS_MD.write_text(
        build_analysis_md(timeline, manifest, len(scene_frames)), encoding="utf-8")
    print(f"[OUT] 分析报告：{ANALYSIS_MD}")
    risk_hits = sorted({w for s in v2_segments for w in s.compliance_risks})
    if risk_hits:
        print(f"[RISK] 命中风险词：{'、'.join(risk_hits)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
