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
    VideoSegment,
    VideoTimeline,
)

Runner = Callable[..., subprocess.CompletedProcess]

# 食品广告合规风险词（与 Stage 1 合规边界一致）
RISK_WORDS = [
    "减肥", "瘦身", "降糖", "降血糖", "控制血糖", "治疗", "治病", "药用",
    "无糖", "不长胖", "吃了就瘦", "最有效", "百分百", "100%", "第一",
    "燃脂", "瘦脸", "掉秤", "暴瘦",
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
    """优先系统 PATH；否则回退 imageio-ffmpeg 自带静态二进制（CAND-009）。"""
    tool = shutil.which("ffmpeg")
    if tool:
        return tool
    try:
        import imageio_ffmpeg

        return str(imageio_ffmpeg.get_ffmpeg_exe())
    except ImportError:
        return None


FFMPEG_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)")
FFMPEG_VIDEO_RE = re.compile(r"Video:\s*([a-zA-Z0-9]+).*?,\s*(\d{2,5})x(\d{2,5})")
FFMPEG_AUDIO_RE = re.compile(r"Audio:\s*([a-zA-Z0-9]+)")


def probe_video_metadata(
    video_path: str | Path,
    runner: Runner = subprocess.run,
) -> dict:
    """用 `ffmpeg -i` 探测时长/分辨率/编码（无 ffprobe 时的替代）。

    返回 {duration_seconds, resolution, video_codec, audio_codec, ffmpeg_version}；
    无法解析的字段为 None，禁止编造。
    """
    tool = find_ffmpeg()
    if not tool:
        raise FileNotFoundError("ffmpeg 不可用，无法探测视频元数据")
    proc = runner([tool, "-i", str(video_path)], capture_output=True, text=True,
                  encoding="utf-8", errors="replace", timeout=120)
    output = (proc.stderr or "") + (proc.stdout or "")
    meta: dict = {"duration_seconds": None, "resolution": None,
                  "video_codec": None, "audio_codec": None, "ffmpeg_version": ""}
    ver = re.search(r"ffmpeg version\s+(\S+)", output)
    if ver:
        meta["ffmpeg_version"] = ver.group(1)
    dur = FFMPEG_DURATION_RE.search(output)
    if dur:
        h, m, s, frac = dur.groups()
        meta["duration_seconds"] = round(
            int(h) * 3600 + int(m) * 60 + int(s) + int(frac.ljust(3, "0")[:3]) / 1000.0, 3)
    vid = FFMPEG_VIDEO_RE.search(output)
    if vid:
        meta["video_codec"] = vid.group(1)
        meta["resolution"] = f"{vid.group(2)}x{vid.group(3)}"
    aud = FFMPEG_AUDIO_RE.search(output)
    if aud:
        meta["audio_codec"] = aud.group(1)
    return meta


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    """计算文件 SHA-256（用于证据清单，原始文件不入 Git）。"""
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def average_hash(image_path: str | Path, size: int = 8) -> int:
    """PIL 感知均值哈希，用于近似重复帧去除。"""
    from PIL import Image

    with Image.open(image_path) as img:
        pixels = list(img.convert("L").resize((size, size)).getdata())
    avg = sum(pixels) / len(pixels)
    bits = 0
    for p in pixels:
        bits = (bits << 1) | (1 if p >= avg else 0)
    return bits


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def dedupe_keyframes(frame_paths: list[Path], max_distance: int = 5) -> list[Path]:
    """去除近似重复帧（均值哈希汉明距离 ≤ max_distance 视为重复）。"""
    kept: list[Path] = []
    hashes: list[int] = []
    for path in frame_paths:
        try:
            h = average_hash(path)
        except Exception:  # noqa: BLE001 - 单帧损坏不阻塞整体流程
            kept.append(path)
            hashes.append(-1 << 64)
            continue
        if all(hamming_distance(h, prev) > max_distance for prev in hashes):
            kept.append(path)
            hashes.append(h)
    return kept


def format_srt_time(seconds: float) -> str:
    """秒 → SRT 时间格式 HH:MM:SS,mmm。"""
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_srt(segments: list[TranscriptSegment]) -> str:
    """转写片段列表 → SRT 文本。"""
    blocks = []
    for i, seg in enumerate(segments, start=1):
        blocks.append(
            f"{i}\n{format_srt_time(seg.start)} --> {format_srt_time(seg.end)}\n{seg.text}"
        )
    return "\n\n".join(blocks) + "\n"


def transcribe_with_faster_whisper(
    audio_path: str | Path,
    out_dir: str | Path,
    model_size: str = "base",
) -> tuple[Path, Path]:
    """faster-whisper（CAND-010，MIT）本地转写，生成 transcript.txt / transcript.srt。

    仅在 VideoCaptioner CLI 不可用时作为已登记替代方案；
    模型权重需联网下载，失败时抛 RuntimeError（如实记录，不伪造转写）。
    """
    from faster_whisper import WhisperModel

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        raw_segments, _info = model.transcribe(str(audio_path), language="zh")
        segments = [
            TranscriptSegment(start=round(s.start, 3), end=round(s.end, 3),
                              text=s.text.strip())
            for s in raw_segments
            if s.text.strip()
        ]
    except Exception as exc:  # noqa: BLE001 - 模型下载/推理失败须如实上报
        raise RuntimeError(f"faster-whisper 转写失败: {exc}") from exc
    if not segments:
        raise RuntimeError("faster-whisper 转写结果为空")
    txt = out / "transcript.txt"
    srt = out / "transcript.srt"
    txt.write_text("\n".join(s.text for s in segments), "utf-8")
    srt.write_text(segments_to_srt(segments), "utf-8")
    return txt, srt


def extract_audio(
    video_path: str | Path,
    out_path: str | Path,
    runner: Runner = subprocess.run,
) -> Path:
    """FFmpeg 抽取 16kHz 单声道音频（ASR 输入）。"""
    tool = find_ffmpeg()
    if not tool:
        raise FileNotFoundError("ffmpeg 不可用，无法抽取音频")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = runner(
        [tool, "-y", "-i", str(video_path), "-vn", "-ar", "16000", "-ac", "1",
         str(out)],
        capture_output=True, timeout=600,
    )
    if proc.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        raise RuntimeError("FFmpeg 音频抽取失败")
    return out


COMMERCIAL_HINTS = ["链接", "橱窗", "小黄车", "同款", "旗舰店", "下单", "优惠券", "直播间"]


def build_video_segments(
    segments: list[TranscriptSegment],
    keyframes: list[Keyframe],
) -> list[VideoSegment]:
    """音频（转写）与关键帧证据合并为 12 字段时间线片段。

    合并规则：
    - 每个转写片段对应一个 VideoSegment；
    - evidence_frame_timestamps 取落在 [start, end] 内的真实关键帧时间戳；
    - 视觉类字段一律 None（无视觉模型，禁止编造）；
    - food_or_product 仅口播明确提及 PRODUCT_HINTS 时填写，confidence 降为 0.6；
    - commercial_expression 仅口播明确提及 COMMERCIAL_HINTS 时填写；
    - product_first_appearance 只在全片首个提及产品的片段填写（基于口播证据）。
    """
    frame_times = sorted(k.timestamp for k in keyframes if k.timestamp >= 0)
    results: list[VideoSegment] = []
    first_product_time: Optional[float] = None
    for seg in segments:
        hits = [h for h in PRODUCT_HINTS if h in seg.text]
        if hits and first_product_time is None:
            first_product_time = seg.start
    for seg in segments:
        hits = [h for h in PRODUCT_HINTS if h in seg.text]
        commercial = [h for h in COMMERCIAL_HINTS if h in seg.text]
        evidence = [t for t in frame_times if seg.start <= t < seg.end]
        has_text = bool(seg.text.strip())
        confidence = 0.9 if has_text else 0.0
        if hits:  # 产品判断仅来自口播提及，无视觉证据，降置信度
            confidence = min(confidence, 0.6)
        results.append(VideoSegment(
            start_time=seg.start,
            end_time=seg.end,
            transcript_summary=seg.text,
            food_or_product="、".join(hits) if hits else None,
            product_first_appearance=(
                first_product_time if hits and seg.start == first_product_time else None
            ),
            commercial_expression="、".join(commercial) if commercial else None,
            compliance_risks=detect_risk_words(seg.text),
            evidence_frame_timestamps=evidence,
            confidence=confidence,
        ))
    return results


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
        proc = runner(
            [tool, "-y", "-i", str(video_path),
             "-vf", f"select='gt(scene,0.4)',showinfo,{scale}",
             "-vsync", "vfr", "-q:v", "5", scene_tpl],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=600,
        )
        # showinfo stderr 中的 pts_time 与输出帧顺序一一对应，取真实时间戳
        pts = [float(x) for x in
               re.findall(r"pts_time:([0-9]+(?:\.[0-9]+)?)", proc.stderr or "")]
        for i, f in enumerate(sorted(out.glob("scene_*.jpg"))):
            ts = pts[i] if i < len(pts) else 0.0
            frames.append(Keyframe(timestamp=round(ts, 3), path=str(f),
                                   kind="scene_change"))
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
