"""creator-style-distiller 输出校验器单元测试（离线，不依赖小红书）。

覆盖：合法输出通过、必填字段缺失、confidence 越界、evidence_timestamps 为空、
枚举/类型错误、禁复制检查（真实欧盈Kelly timeline 作为输入对照）、
evals.json 结构（≥3 真实 eval + ≥1 反例）与反例可执行性。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "skills" / "creator-style-distiller" / "scripts" / "validate_output.py"
EVALS = ROOT / "skills" / "creator-style-distiller" / "evals" / "evals.json"
REAL_TIMELINE = ROOT / "data" / "processed" / "stage_3_top3_video_timelines.json"

# 真实 on_screen_text（欧盈Kelly 第 5 段 38-48s）中的长句，用于构造反例。
VERBATIM_LIFT = "每天早餐都是固定的炒蛋+冰美；作为广州人我真的好想念广州的点心"


def _valid_output() -> dict:
    """构造一个通过全部 schema 检查的最小合法输出（字符串均为转述）。"""
    return {
        "hook_patterns": [
            {"pattern": "前 4 秒移动自拍加大标题卡建立共鸣语境", "evidence": "第 1 段 0-4s",
             "timestamps": [0.0, 4.0]}
        ],
        "narrative_structure": {
            "arc": "时钟时间推进的一日工作叙事",
            "phases": [
                {"name": "晨间准备", "description": "穿搭出门", "time_range_s": [0.0, 18.0]},
                {"name": "工作主线", "description": "通勤后到司办公"},
            ],
        },
        "sentence_rhythm": {"style": "短句口语旁白", "features": ["短句", "口语化"]},
        "voiceover_density": {"mode": "voiceover", "estimated_speech_ratio": 0.7},
        "subtitle_density": {"level": "high", "functions": ["时间戳", "情绪表达"]},
        "shot_rhythm": {"avg_shot_s": 2.4, "pacing": "快切",
                        "shot_types": ["自拍仰拍", "固定机位"]},
        "scene_patterns": [{"scene": "户外城市街道"}, {"scene": "办公室"}],
        "food_integration_patterns": [
            {"pattern": "饮品在多个生活节点复现", "evidence": "18s 与 33.2s",
             "insertion_point_s": 18.0}
        ],
        "commercial_integration_patterns": [
            {"pattern": "自用展示形态出现产品", "evidence": "4-18s 段"}
        ],
        "CTA_patterns": [{"pattern": "结尾字幕卡再见式引导"}],
        "reusable_style_rules": ["用时间戳字幕推进全天叙事", "饮品在生活流节点自然复现"],
        "creator_specific_elements_not_to_copy": ["开场问候黑话", "人格标签人设"],
        "confidence": 0.8,
        "evidence_timestamps": [0.0, 14.0, [148.0, 153.5]],
    }


def _run_validator(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=ROOT,
        check=False,
    )


def _write_json(tmp_path: Path, name: str, data) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_valid_output_passes_without_input(tmp_path: Path) -> None:
    out = _write_json(tmp_path, "out.json", _valid_output())
    result = _run_validator(str(out))
    assert result.returncode == 0, result.stdout
    assert "[PASS]" in result.stdout


def test_missing_required_field_fails(tmp_path: Path) -> None:
    data = _valid_output()
    del data["hook_patterns"]
    out = _write_json(tmp_path, "out.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "hook_patterns" in result.stdout


@pytest.mark.parametrize("bad_confidence", [-0.1, 1.5, "high"])
def test_confidence_out_of_range_fails(tmp_path: Path, bad_confidence) -> None:
    data = _valid_output()
    data["confidence"] = bad_confidence
    out = _write_json(tmp_path, "out.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "confidence" in result.stdout


def test_empty_evidence_timestamps_fails(tmp_path: Path) -> None:
    data = _valid_output()
    data["evidence_timestamps"] = []
    out = _write_json(tmp_path, "out.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "evidence_timestamps" in result.stdout


def test_empty_reusable_rules_fails(tmp_path: Path) -> None:
    data = _valid_output()
    data["reusable_style_rules"] = []
    out = _write_json(tmp_path, "out.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1


def test_bad_enum_fails(tmp_path: Path) -> None:
    data = _valid_output()
    data["voiceover_density"]["mode"] = "podcast"
    out = _write_json(tmp_path, "out.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "voiceover_density.mode" in result.stdout


def test_verbatim_copy_fails_with_real_timeline_input(tmp_path: Path) -> None:
    """输出搬运真实字幕原句（>15 字连续相同）必须判失败。"""
    data = _valid_output()
    data["reusable_style_rules"] = [VERBATIM_LIFT, "用时间戳字幕推进全天叙事"]
    out = _write_json(tmp_path, "out.json", data)
    result = _run_validator(str(out), "--input", str(REAL_TIMELINE))
    assert result.returncode == 1
    assert "禁复制检查失败" in result.stdout


def test_paraphrase_passes_with_real_timeline_input(tmp_path: Path) -> None:
    """转述后的合法输出在真实输入对照下应通过禁复制检查。"""
    out = _write_json(tmp_path, "out.json", _valid_output())
    result = _run_validator(str(out), "--input", str(REAL_TIMELINE))
    assert result.returncode == 0, result.stdout


def test_short_overlap_under_threshold_passes(tmp_path: Path) -> None:
    """不超过 15 字的短重合（如'户外城市街道'场景名）不判复制。"""
    data = _valid_output()
    data["scene_patterns"] = [{"scene": "户外城市街道"}, {"scene": "餐厅"}]
    out = _write_json(tmp_path, "out.json", data)
    result = _run_validator(str(out), "--input", str(REAL_TIMELINE))
    assert result.returncode == 0, result.stdout


def test_missing_output_file_returns_2(tmp_path: Path) -> None:
    result = _run_validator(str(tmp_path / "nonexistent.json"))
    assert result.returncode == 2


def test_evals_json_structure() -> None:
    evals_doc = json.loads(EVALS.read_text(encoding="utf-8"))
    evals = evals_doc["evals"]
    assert len(evals) >= 4, "至少 3 个真实 eval + 1 个反例 eval"
    ids = [e["id"] for e in evals]
    assert len(ids) == len(set(ids))
    real = [e for e in evals if e["type"] == "llm_graded"]
    counter = [e for e in evals if e["type"] == "executable"]
    assert len(real) >= 3 and len(counter) >= 1
    for e in real:
        assert e["expected_output_points"], f"{e['id']} 缺少期望输出要点"
        assert "timelines[0]" in json.dumps(e["input"], ensure_ascii=False)


def test_evals_counter_example_fails_validator(tmp_path: Path) -> None:
    """evals.json 中的反例样本在真实输入对照下必须被判失败。"""
    evals_doc = json.loads(EVALS.read_text(encoding="utf-8"))
    counter = next(e for e in evals_doc["evals"] if e["type"] == "executable")
    assert counter["expected_validator_result"] == "fail"
    out = _write_json(tmp_path, "bad.json", counter["sample_bad_output"])
    result = _run_validator(str(out), "--input", str(REAL_TIMELINE))
    assert result.returncode == 1
    assert "禁复制检查失败" in result.stdout


def test_evals_reference_output_passes_validator(tmp_path: Path) -> None:
    """eval_001 的参考输出在真实输入对照下必须通过全部校验。"""
    evals_doc = json.loads(EVALS.read_text(encoding="utf-8"))
    reference = evals_doc["evals"][0]["reference_output"]
    out = _write_json(tmp_path, "good.json", reference)
    result = _run_validator(str(out), "--input", str(REAL_TIMELINE))
    assert result.returncode == 0, result.stdout
