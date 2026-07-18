"""代表性 Vlog POC 门禁测试（不依赖真实小红书，全部离线运行）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.representative_poc import (
    MIN_CONTENT_STAGES,
    MIN_VALID_KEYFRAMES,
    count_valid_semantic_segments,
    duration_in_range,
    evaluate_representative_gates,
    subtitle_coverage,
    transcript_gate,
)

ROOT = Path(__file__).resolve().parent.parent
CANDIDATE = ROOT / "data/processed/xhs_representative_video_candidate.json"
MANIFEST = ROOT / "data/processed/xhs_representative_video_manifest.json"
TIMELINE = ROOT / "data/processed/xhs_representative_video_timeline.json"
REPORT = ROOT / "reports/stage_2_representative_video_analysis.md"


# ---------- 时长区间 ----------


@pytest.mark.parametrize(("sec", "ok"), [
    (29.9, False), (30.0, True), (71.7, True), (120.0, True), (120.1, False),
    (None, False), (0, False),
])
def test_duration_in_range(sec, ok) -> None:
    assert duration_in_range(sec) is ok


# ---------- 有效语义片段 ----------


def test_count_valid_semantic_segments_filters_noise() -> None:
    segs = [
        {"text": "【忍耐】"},        # BGM 误识别噪声
        {"text": "盐"},              # 单字噪声
        {"text": "今天早餐吃酸汤面"},  # 有效
        {"text": "虾滑加胡萝卜粒玉米"},  # 有效
        {"text": ""},               # 空
        {"text": "搅拌均匀即可"},     # 有效
    ]
    assert count_valid_semantic_segments(segs) == 3


def test_count_valid_semantic_segments_empty() -> None:
    assert count_valid_semantic_segments([]) == 0


# ---------- 字幕覆盖 ----------


def test_subtitle_coverage() -> None:
    segs = [
        {"on_screen_text": "搅拌均匀"},
        {"on_screen_text": None},
        {"on_screen_text": "上锅蒸熟"},
        {"on_screen_text": ""},
    ]
    assert subtitle_coverage(segs) == pytest.approx(0.5)
    assert subtitle_coverage([]) == 0.0


# ---------- 转写门禁（或分支） ----------


def test_transcript_gate_or_branch() -> None:
    assert transcript_gate(3, 0.0) is True       # ASR 有效片段分支
    assert transcript_gate(0, 0.6) is True       # 字幕覆盖分支
    assert transcript_gate(2, 0.4) is False      # 两支都不满足
    assert transcript_gate(0, 0.49) is False


# ---------- 综合门禁 ----------


def _good_inputs():
    candidate = {"duration_seconds": 71.7}
    manifest = {
        "duration_seconds_file": 71.714,
        "keyframe_stats": {"valid_interval": MIN_VALID_KEYFRAMES},
    }
    timeline = {
        "content_stages_count": MIN_CONTENT_STAGES,
        "asr_reliability": "unreliable_bgm_mistranscription",
        "segments": [
            {"on_screen_text": "步骤字幕", "evidence_frame_timestamps": [0.0],
             "compliance_risks": []}
            for _ in range(6)
        ],
    }
    report = "前 3 秒钩子 镜头节奏 植入分析 合规风险"
    return candidate, manifest, timeline, report


def test_gate_pass_on_good_inputs() -> None:
    c, m, t, r = _good_inputs()
    result = evaluate_representative_gates(c, m, t, r)
    assert result.ready, result.failures


def test_gate_fail_short_video() -> None:
    c, m, t, r = _good_inputs()
    m["duration_seconds_file"] = 12.0
    c["duration_seconds"] = 12.0
    result = evaluate_representative_gates(c, m, t, r)
    assert not result.ready
    assert any("duration" in f for f in result.failures)


def test_gate_fail_few_stages() -> None:
    c, m, t, r = _good_inputs()
    t["content_stages_count"] = 3
    result = evaluate_representative_gates(c, m, t, r)
    assert not result.ready
    assert any("content_stages" in f for f in result.failures)


def test_gate_fail_few_keyframes() -> None:
    c, m, t, r = _good_inputs()
    m["keyframe_stats"]["valid_interval"] = 5
    result = evaluate_representative_gates(c, m, t, r)
    assert not result.ready
    assert any("valid_keyframes" in f for f in result.failures)


def test_gate_fail_no_subtitle_no_asr() -> None:
    c, m, t, r = _good_inputs()
    for seg in t["segments"]:
        seg["on_screen_text"] = None
    result = evaluate_representative_gates(c, m, t, r)
    assert not result.ready
    assert "transcript_gate_failed" in result.failures


def test_gate_fail_missing_report_sections() -> None:
    c, m, t, r = _good_inputs()
    result = evaluate_representative_gates(c, m, t, "只有钩子分析")
    assert not result.ready
    assert any("report_sections_missing" in f for f in result.failures)


def test_gate_fail_no_visual_evidence() -> None:
    c, m, t, r = _good_inputs()
    for seg in t["segments"]:
        seg["evidence_frame_timestamps"] = []
    result = evaluate_representative_gates(c, m, t, r)
    assert not result.ready
    assert "no_visual_evidence" in result.failures


def test_gate_fail_missing_compliance_scan() -> None:
    c, m, t, r = _good_inputs()
    for seg in t["segments"]:
        del seg["compliance_risks"]
    result = evaluate_representative_gates(c, m, t, r)
    assert not result.ready
    assert "missing_compliance_scan" in result.failures


# ---------- 真实产物核验（离线读文件，不触网） ----------


@pytest.mark.skipif(not CANDIDATE.is_file(), reason="代表性候选尚未生成")
def test_real_candidate_contract() -> None:
    c = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    assert c["note_type"] == "video"
    assert duration_in_range(c["duration_seconds"])
    assert c["usage_scope"] == "stage_2_representative_poc"
    assert c["human_verified"] is False
    assert "xsec_token" not in CANDIDATE.read_text(encoding="utf-8")
    assert c["canonical_url"].endswith(c["note_id"])


@pytest.mark.skipif(
    not all(p.is_file() for p in (CANDIDATE, MANIFEST, TIMELINE, REPORT)),
    reason="代表性 POC 产物尚未生成",
)
def test_real_representative_gate_ready() -> None:
    result = evaluate_representative_gates(
        json.loads(CANDIDATE.read_text(encoding="utf-8")),
        json.loads(MANIFEST.read_text(encoding="utf-8")),
        json.loads(TIMELINE.read_text(encoding="utf-8")),
        REPORT.read_text(encoding="utf-8"),
    )
    assert result.ready, result.failures
    assert result.stats["valid_keyframes"] >= MIN_VALID_KEYFRAMES
    assert result.stats["segments"] >= MIN_CONTENT_STAGES
