"""视频理解管线：转写、关键帧、时间线与内容分析。

可追溯原则：
- 口播仅来自 transcript.srt；
- 风险词由 RISK_WORDS 规则扫描转写文本得出；
- 视觉类字段（屏幕字幕/人物动作/场景/镜头类型/产品露出）POC 阶段无视觉模型，
  一律留空并在报告说明，禁止编造；
- 所有结论必须能追溯到 URL、转写文本或关键帧路径。
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

from src.video_models import (
    ContentAnalysis,
    Keyframe,
    TimelineEntry,
    TranscriptSegment,
    VideoTimeline,
)

Runner = Callable[..., subprocess.CompletedProcess]

# 食品广告合规风险词（与 Stage 1 合规边界一致）
RISK_WORDS = [
    "减肥", "瘦身", "降糖", "降血糖", "控制血糖", "治疗", "治病", "药用",
    "无糖", "不长胖", "吃了就瘦", "最有效", "百分百", "100%", "第一",
]

PRODUCT_HINTS = ["酸奶", "轻醒", "希腊", "高蛋白", "0蔗糖", "益生菌"]

SRT_TIME_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


def srt_time_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(srt_text: str) -> list[TranscriptSegment]:
    """解析 SRT 转写文件为片段列表。"""
    segments: list[TranscriptSegment] = []
    blocks = re.split(r"\n\s*\n", srt_text.strip())
    for block in blocks:
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        time_line_idx = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if time_line_idx is None:
            continue
        match = SRT_TIME_RE.search(lines[time_line_idx])
        if not match:
            continue
        start = srt_time_to_seconds(*match.group(1, 2, 3, 4))
        end = srt_time_to_seconds(*match.group(5, 6, 7, 8))
        text = " ".join(lines[time_line_idx + 1 :])
        if text:
            segments.append(TranscriptSegment(start=start, end=end, text=text))
    return segments


def detect_risk_words(text: str) -> list[str]:
    """扫描文本中的风险词。"""
    return [w for w in RISK_WORDS if w in text]


def find_ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg")


def extract_keyframes(
    video_path: str | Path,
    out_dir: str | Path,
    interval_seconds: int = 2,
    max_width: int = 640,
    scene_change: bool = True,
    runner: Runner = subprocess.run,
) -> list[Keyframe]:
    """FFmpeg 抽帧：每 interval 秒一帧 + 场景切换帧，低分辨率输出。

    FFmpeg 不可用时抛 FileNotFoundError（如实记录，不伪造）。
    """
    tool = find_ffmpeg()
    if not tool:
        raise FileNotFoundError("ffmpeg 不可用，无法抽取关键帧")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    scale = f"scale='min({max_width},iw)':-2"
    interval_tpl = str(out / "interval_%04d.jpg")
    runner(
        [tool, "-y", "-i", str(video_path), "-vf", f"fps=1/{interval_seconds},{scale}",
         "-q:v", "5", interval_tpl],
        capture_output=True, timeout=600,
    )
    frames: list[Keyframe] = []
    for i, f in enumerate(sorted(out.glob("interval_*.jpg"))):
        frames.append(Keyframe(timestamp=float(i * interval_seconds),
                               path=str(f), kind="interval"))
    if scene_change:
        scene_tpl = str(out / "scene_%04d.jpg")
        runner(
            [tool, "-y", "-i", str(video_path),
             "-vf", f"select='gt(scene,0.4)',showinfo,{scale}",
             "-vsync", "vfr", "-q:v", "5", scene_tpl],
            capture_output=True, timeout=600,
        )
        for f in sorted(out.glob("scene_*.jpg")):
            frames.append(Keyframe(timestamp=-1.0, path=str(f), kind="scene_change"))
    return frames


def generate_transcript(
    video_path: str | Path,
    out_dir: str | Path,
    runner: Runner = subprocess.run,
) -> tuple[Path, Path]:
    """调用 VideoCaptioner CLI 生成 transcript.txt / transcript.srt。

    VideoCaptioner（GPL-3.0）仅 CLI 调用；不可用或失败时抛 FileNotFoundError。
    """
    tool = shutil.which("VideoCaptioner") or shutil.which("video-captioner")
    if not tool:
        raise FileNotFoundError("VideoCaptioner 不可用，无法生成转写")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    proc = runner(
        [tool, "--input", str(video_path), "--output", str(out),
         "--formats", "txt,srt"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800,
    )
    txt, srt = out / "transcript.txt", out / "transcript.srt"
    if proc.returncode != 0 or not srt.is_file():
        raise FileNotFoundError("VideoCaptioner 转写失败")
    return txt, srt


def build_timeline(
    source_url: str,
    segments: list[TranscriptSegment],
    keyframes: list[Keyframe],
    transcript_file: str = "",
    keyframe_dir: str = "",
) -> VideoTimeline:
    """按关键帧时间点对齐口播，生成时间线。无关键帧时按转写片段生成。"""
    entries: list[TimelineEntry] = []
    points = sorted({k.timestamp for k in keyframes if k.timestamp >= 0})
    if not points:
        points = [s.start for s in segments]
    for t in points:
        seg = next((s for s in segments if s.start <= t < s.end), None)
        text = seg.text if seg else ""
        entries.append(TimelineEntry(time=t, speech=text, risk_words=detect_risk_words(text)))
    duration = max((s.end for s in segments), default=0.0)
    return VideoTimeline(
        source_url=source_url,
        duration_seconds=duration,
        transcript_file=transcript_file,
        keyframe_dir=keyframe_dir,
        entries=entries,
        notes="视觉类字段（屏幕字幕/人物动作/场景/镜头/产品露出）需人工或视觉模型标注，POC 留空",
    )


def analyze_content(timeline: VideoTimeline) -> ContentAnalysis:
    """基于时间线生成内容分析（全部结论可追溯到转写）。"""
    entries = timeline.entries
    first3 = [e.speech for e in entries if e.time < 3 and e.speech]
    no_speech = "前 3 秒无口播（可能为画面/音乐钩子，需关键帧人工标注）"
    hook = " / ".join(first3) if first3 else no_speech

    total_words = sum(len(e.speech) for e in entries)
    duration = timeline.duration_seconds
    wps = round(total_words / duration, 2) if duration > 0 else 0
    speech_entries = [e for e in entries if e.speech]
    rhythm = (
        f"时长 {duration:.1f}s，口播条目 {len(speech_entries)}，"
        f"总字数 {total_words}，语速 {wps} 字/秒"
    )

    hits = sorted({h for e in entries for h in PRODUCT_HINTS if h in e.speech})
    risk = sorted({w for e in entries for w in e.risk_words})
    product = f"口播提及产品相关词：{'、'.join(hits)}" if hits else "口播未直接提及产品词"

    return ContentAnalysis(
        source_url=timeline.source_url,
        hook_first_3s=hook,
        structure=f"时间线条目 {len(entries)} 个（间隔 2s + 场景切换点）",
        rhythm=rhythm,
        expression_style="基于口播文本的表达分析（视觉表达需关键帧人工标注）",
        product_integration=product,
        risk_notes=[f"命中风险词：{'、'.join(risk)}"] if risk else [],
    )


def render_analysis_md(analysis: ContentAnalysis, timeline: VideoTimeline) -> str:
    """生成 content_analysis.md 内容。"""
    lines = [
        "# 商单候选视频内容分析",
        "",
        f"- 来源 URL：{analysis.source_url}",
        f"- 转写文件：{timeline.transcript_file or '（无）'}",
        f"- 关键帧目录：{timeline.keyframe_dir or '（无）'}",
        "",
        "## 前 3 秒钩子",
        "",
        analysis.hook_first_3s,
        "",
        "## 结构",
        "",
        analysis.structure,
        "",
        "## 节奏",
        "",
        analysis.rhythm,
        "",
        "## 表达方式",
        "",
        analysis.expression_style,
        "",
        "## 产品植入",
        "",
        analysis.product_integration,
        "",
        "## 合规风险",
        "",
    ]
    if analysis.risk_notes:
        lines += [f"- {n}" for n in analysis.risk_notes]
    else:
        lines.append("- 口播未命中风险词")
    lines += [
        "",
        "> 可追溯性声明：以上结论仅基于转写文本与关键帧路径；",
        "> 视觉类字段（屏幕字幕/人物动作/场景/镜头/产品露出）未编造，留待人工标注。",
        "",
    ]
    return "\n".join(lines)
