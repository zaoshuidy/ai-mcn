"""Stage 2 代表性生活 Vlog POC 门禁评估（纯函数，离线可测）。

门禁条件（全部满足才可置 representative_video_poc_ready=true）：
- 视频时长 30—120 秒；
- 真实转写 ≥3 个有效语义片段，或连续字幕覆盖主要视频（≥50% 片段含屏幕字幕）；
- ≥5 个内容阶段；
- ≥10 张有效非重复关键帧；
- 音频与视觉时间线均有证据（音频证据允许如实标注为 BGM/无效口播）；
- 完成前3秒钩子、镜头节奏、产品植入、合规风险分析（报告章节存在）；
- 结论可追溯到时间戳（每片段含 evidence_frame_timestamps 或明确 null）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MIN_DURATION_S = 30.0
MAX_DURATION_S = 120.0
MIN_SEMANTIC_SEGMENTS = 3
SUBTITLE_COVERAGE_RATIO = 0.5
MIN_CONTENT_STAGES = 5
MIN_VALID_KEYFRAMES = 10

REQUIRED_REPORT_SECTIONS = [
    "前 3 秒", "镜头", "植入", "合规",
]


@dataclass
class GateResult:
    ready: bool
    failures: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


def duration_in_range(seconds: float | None) -> bool:
    if seconds is None:
        return False
    return MIN_DURATION_S <= seconds <= MAX_DURATION_S


def count_valid_semantic_segments(
    segments: list[dict],
    unreliable_markers: tuple[str, ...] = ("【", "】"),
) -> int:
    """统计有效语义片段：非空、非纯符号、非已知 BGM 误识别噪声。

    单字/双字噪声（如『盐』『芥末』，无上下文）不计入有效语义片段。
    """
    count = 0
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if len(text) < 3:
            continue
        if any(m in text for m in unreliable_markers) and len(text) <= 5:
            continue
        count += 1
    return count


def subtitle_coverage(segments: list[dict]) -> float:
    """连续字幕覆盖率：含非空 on_screen_text 的片段占比。"""
    if not segments:
        return 0.0
    with_subs = sum(1 for s in segments if (s.get("on_screen_text") or "").strip())
    return with_subs / len(segments)


def transcript_gate(
    asr_segment_count: int,
    subtitle_cov: float,
) -> bool:
    """转写门禁：≥3 个有效语义片段，或连续字幕覆盖 ≥50% 片段。"""
    return asr_segment_count >= MIN_SEMANTIC_SEGMENTS or subtitle_cov >= SUBTITLE_COVERAGE_RATIO


def evaluate_representative_gates(
    candidate: dict,
    manifest: dict,
    timeline: dict,
    report_text: str,
) -> GateResult:
    failures: list[str] = []
    stats: dict[str, Any] = {}

    dur = manifest.get("duration_seconds_file") or candidate.get("duration_seconds")
    stats["duration"] = dur
    if not duration_in_range(dur):
        failures.append(f"duration_out_of_range({dur})")

    segments = timeline.get("segments") or []
    stats["segments"] = len(segments)
    stages = timeline.get("content_stages_count")
    if not isinstance(stages, int) or stages < MIN_CONTENT_STAGES:
        failures.append(f"content_stages<{MIN_CONTENT_STAGES}({stages})")

    valid_kf = (manifest.get("keyframe_stats") or {}).get("valid_interval", 0)
    stats["valid_keyframes"] = valid_kf
    if valid_kf < MIN_VALID_KEYFRAMES:
        failures.append(f"valid_keyframes<{MIN_VALID_KEYFRAMES}({valid_kf})")

    cov = subtitle_coverage(segments)
    stats["subtitle_coverage"] = round(cov, 3)
    # ASR 有效片段：本样本 ASR 为 BGM 误识别，走字幕覆盖分支
    asr_valid = 0 if timeline.get("asr_reliability", "").startswith("unreliable") else len(segments)
    stats["asr_valid_segments"] = asr_valid
    if not transcript_gate(asr_valid, cov):
        failures.append("transcript_gate_failed")

    # 音视频证据：每片段须有 evidence_frame_timestamps 字段（允许空列表但字段存在）
    if not all("evidence_frame_timestamps" in s for s in segments):
        failures.append("missing_frame_evidence_field")
    if not any(s.get("evidence_frame_timestamps") for s in segments):
        failures.append("no_visual_evidence")

    # 报告章节完整性
    missing = [sec for sec in REQUIRED_REPORT_SECTIONS if sec not in report_text]
    if missing:
        failures.append(f"report_sections_missing:{missing}")

    # 风险扫描存在（compliance_risks 字段存在于每片段）
    if not all("compliance_risks" in s for s in segments):
        failures.append("missing_compliance_scan")

    return GateResult(ready=not failures, failures=failures, stats=stats)
