"""Stage 2 视频理解 POC 执行脚本。

流程：获取视频（yt-dlp → XHS-Downloader）→ 转写（VideoCaptioner）
→ 关键帧（FFmpeg）→ video_timeline.json → content_analysis.md。

任一步骤不可用即如实停止并记录，不得绕过验证码/风控，不伪造产物。
视频仅存 tmp/；Git 只保留元数据、转写、低分辨率关键帧与分析报告。

用法：
  python scripts/analyze_xhs_video.py --url <笔记URL>
  python scripts/analyze_xhs_video.py --video-file tmp/xhs_video/xxx.mp4 --url <笔记URL>
  python scripts/analyze_xhs_video.py --srt tmp/xhs_video/transcript.srt --url <笔记URL>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.xhs_video_adapter import VideoAcquisitionFailed, acquire_video  # noqa: E402
from src.video_analyzer import (  # noqa: E402
    analyze_content,
    build_timeline,
    extract_keyframes,
    generate_transcript,
    parse_srt,
    render_analysis_md,
)

TMP_DIR = ROOT / "tmp/xhs_video"
TIMELINE_JSON = ROOT / "data/processed/video_timeline.json"
ANALYSIS_MD = ROOT / "reports/content_analysis.md"
KEYFRAME_DIR = ROOT / "screenshots/stage_2_browser_poc/keyframes"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="笔记 URL（来源追溯）")
    parser.add_argument("--video-file", default="", help="已有视频文件（跳过获取）")
    parser.add_argument("--srt", default="", help="已有转写 SRT（跳过转写）")
    args = parser.parse_args()

    video_path = args.video_file
    if not video_path:
        try:
            asset = acquire_video(args.url, TMP_DIR)
            video_path = asset.local_path
            print(f"[VIDEO] 获取成功（{asset.acquired_by}）：{video_path}")
        except VideoAcquisitionFailed as exc:
            print(f"[STOP] 视频获取失败：{exc}")
            return 5

    if args.srt:
        srt_path = Path(args.srt)
    else:
        try:
            _, srt_path = generate_transcript(video_path, TMP_DIR)
            print(f"[VIDEO] 转写完成：{srt_path}")
        except FileNotFoundError as exc:
            print(f"[STOP] 转写失败：{exc}")
            return 6

    segments = parse_srt(srt_path.read_text(encoding="utf-8"))
    print(f"[VIDEO] 转写片段 {len(segments)} 条")

    keyframes = []
    try:
        keyframes = extract_keyframes(video_path, KEYFRAME_DIR)
        print(f"[VIDEO] 关键帧 {len(keyframes)} 张（低分辨率）")
    except FileNotFoundError as exc:
        print(f"[WARN] {exc}，时间线将仅基于转写")

    timeline = build_timeline(
        source_url=args.url,
        segments=segments,
        keyframes=keyframes,
        transcript_file=str(srt_path),
        keyframe_dir=str(KEYFRAME_DIR) if keyframes else "",
    )
    TIMELINE_JSON.parent.mkdir(parents=True, exist_ok=True)
    TIMELINE_JSON.write_text(timeline.model_dump_json(indent=2), encoding="utf-8")
    print(f"[VIDEO] 时间线：{TIMELINE_JSON}（{len(timeline.entries)} 条）")

    analysis = analyze_content(timeline)
    ANALYSIS_MD.write_text(render_analysis_md(analysis, timeline), encoding="utf-8")
    print(f"[VIDEO] 分析报告：{ANALYSIS_MD}")
    if analysis.risk_notes:
        print(f"[RISK] {'；'.join(analysis.risk_notes)}")
    print(json.dumps({"timeline": str(TIMELINE_JSON), "analysis": str(ANALYSIS_MD)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
