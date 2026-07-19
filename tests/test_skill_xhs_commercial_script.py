"""xhs-commercial-script Skill 结构、eval 与输出校验器测试。

覆盖：
- Skill 目录结构与文档契约（SKILL.md / references / evals / scripts）
- evals.json：3 个真实正例（voiceover/subtitle/hybrid）+ 1 个反例
- validate_output.py：正例全通过、反例仅卖点-证据覆盖失败、时长偏差 >30% 判失败、
  达人原句复制检查、形态载体检查、CLI 退出码
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "xhs-commercial-script"
EVAL_PATH = SKILL_DIR / "evals" / "evals.json"
VALIDATOR_PATH = SKILL_DIR / "scripts" / "validate_output.py"
TIMELINES_PATH = ROOT / "data" / "processed" / "stage_3_top3_video_timelines.json"

REQUIRED_FILES = [
    "SKILL.md",
    "references/rules.md",
    "references/examples.md",
    "references/output-schema.md",
    "evals/evals.json",
    "scripts/validate_output.py",
]

POSITIVE_EVAL_IDS = [
    "eval-001-voiceover-breakfast",
    "eval-002-subtitle-afternoon-tea",
    "eval-003-hybrid-post-workout",
]
COUNTEREVAL_ID = "eval-004-counterexample-unmapped-claim"
ALL_CHECK_LABELS = {
    "schema_valid",
    "internal_consistency",
    "format_requirements",
    "claim_evidence_coverage",
    "duration_deviation",
    "verbatim_copy_check",
}

_spec = importlib.util.spec_from_file_location(
    "xhs_commercial_script_validate_output", VALIDATOR_PATH
)
validate_output = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = validate_output
_spec.loader.exec_module(validate_output)


@pytest.fixture(scope="module")
def evals_data() -> dict:
    return json.loads(EVAL_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def timelines_data() -> dict:
    return json.loads(TIMELINES_PATH.read_text(encoding="utf-8"))


def _get_eval(evals_data: dict, eval_id: str) -> dict:
    for item in evals_data["evals"]:
        if item["id"] == eval_id:
            return item
    raise AssertionError(f"eval 不存在: {eval_id}")


def _run_validate(item: dict, timelines: dict) -> list[tuple[str, bool, str]]:
    return validate_output.validate(
        item["candidate_output"], generation_input=item["input"], timelines=timelines
    )


@pytest.mark.parametrize("rel_path", REQUIRED_FILES)
def test_skill_file_exists(rel_path: str) -> None:
    assert (SKILL_DIR / rel_path).is_file(), f"Skill 文件缺失: {rel_path}"


def test_skill_md_frontmatter() -> None:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---"), "SKILL.md 缺少 frontmatter"
    frontmatter = text.split("---", 2)[1]
    assert "name: xhs-commercial-script" in frontmatter
    assert "description:" in frontmatter


def test_skill_md_supports_three_formats() -> None:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    for fmt in ("voiceover", "subtitle", "hybrid"):
        assert fmt in text, f"SKILL.md 未覆盖形态: {fmt}"


def test_skill_md_lists_required_output_fields() -> None:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    for field in (
        "title_options",
        "selected_title",
        "hook",
        "full_script",
        "product_first_appearance",
        "integration_sentence",
        "CTA",
        "estimated_duration",
        "claim_evidence_map",
        "style_evidence_map",
        "unresolved_questions",
    ):
        assert field in text, f"SKILL.md 未声明输出字段: {field}"


def test_rules_reference_real_evidence() -> None:
    text = (SKILL_DIR / "references" / "rules.md").read_text(encoding="utf-8")
    for needle in (
        "欧盈Kelly",
        "小季没烦恼",
        "6989ab01000000001a0360c5",
        "6a58b7ea000000001101a7bb",
        "6a59b5ac00000000100295fe",
        "stage_3_top3_video_timelines.json",
        "不得直接复制达人原句",
        "ProductEvidence",
        "需求场景",
        "贯穿",
    ):
        assert needle in text, f"rules.md 缺少关键内容: {needle}"


def test_evals_json_structure(evals_data: dict) -> None:
    evals = evals_data["evals"]
    assert len(evals) == 4, "evals 必须为 3 正例 + 1 反例"
    ids = [e["id"] for e in evals]
    assert len(set(ids)) == 4, "eval id 不得重复"
    positives = [e for e in evals if e["type"] == "positive"]
    negatives = [e for e in evals if e["type"] == "negative"]
    assert len(positives) == 3 and len(negatives) == 1
    formats = {e["input"]["format"] for e in positives}
    assert formats == {"voiceover", "subtitle", "hybrid"}, "正例必须覆盖三种形态"
    negative = negatives[0]
    assert negative["expect"]["valid"] is False
    assert "claim_evidence_coverage" in negative["expect"]["failed_checks"]
    for item in evals:
        for key in ("brand_brief", "product_evidence", "creator_style_profile"):
            assert key in item["input"], f"{item['id']} 输入缺少 {key}"
        assert "target_duration" in item["input"] and "content_scene" in item["input"]


def test_evals_fixture_note_declares_placeholders(evals_data: dict) -> None:
    note = evals_data.get("fixture_note", "")
    assert "占位" in note, "evals.json 必须声明 product_evidence 为演示占位"
    assert "qingxing_brief.json" in note


@pytest.mark.parametrize("eval_id", POSITIVE_EVAL_IDS)
def test_positive_evals_pass(evals_data: dict, timelines_data: dict, eval_id: str) -> None:
    item = _get_eval(evals_data, eval_id)
    results = _run_validate(item, timelines_data)
    assert {label for label, _, _ in results} == ALL_CHECK_LABELS
    failed = [(label, detail) for label, ok, detail in results if not ok]
    assert not failed, f"{eval_id} 应全部通过，实际失败: {failed}"


def test_counterexample_fails_only_on_claim_coverage(
    evals_data: dict, timelines_data: dict
) -> None:
    item = _get_eval(evals_data, COUNTEREVAL_ID)
    results = _run_validate(item, timelines_data)
    result_map = {label: ok for label, ok, _ in results}
    assert result_map["claim_evidence_coverage"] is False, "反例必须在卖点-证据覆盖上失败"
    for label, ok in result_map.items():
        if label != "claim_evidence_coverage":
            assert ok, f"反例的 {label} 不应失败（失败原因应可精确归因）"
    detail = next(d for label, ok, d in results if label == "claim_evidence_coverage")
    assert "低负担" in detail, "失败详情应指出未映射的卖点"


def test_examples_md_embedded_example_valid(timelines_data: dict) -> None:
    text = (SKILL_DIR / "references" / "examples.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)```", text, re.DOTALL)
    assert len(blocks) >= 2, "examples.md 应包含输入与输出两个 JSON 块"
    parsed = [json.loads(b) for b in blocks]
    gen_input = next(b for b in parsed if "brand_brief" in b)
    output = next(b for b in parsed if "full_script" in b)
    results = validate_output.validate(
        output, generation_input=gen_input, timelines=timelines_data
    )
    failed = [(label, detail) for label, ok, detail in results if not ok]
    assert not failed, f"examples.md 示例应通过校验，实际失败: {failed}"


def test_duration_deviation_over_30_percent_fails(
    evals_data: dict, timelines_data: dict
) -> None:
    item = _get_eval(evals_data, "eval-001-voiceover-breakfast")
    bad_output = copy.deepcopy(item["candidate_output"])
    bad_output["estimated_duration"] = 30.0  # target=60，偏差 50%
    results = validate_output.validate(
        bad_output, generation_input=item["input"], timelines=timelines_data
    )
    result_map = {label: ok for label, ok, _ in results}
    assert result_map["duration_deviation"] is False


def test_duration_within_30_percent_passes(evals_data: dict, timelines_data: dict) -> None:
    item = _get_eval(evals_data, "eval-001-voiceover-breakfast")
    ok_output = copy.deepcopy(item["candidate_output"])
    ok_output["estimated_duration"] = 45.0  # target=60，偏差 25%
    results = validate_output.validate(
        ok_output, generation_input=item["input"], timelines=timelines_data
    )
    result_map = {label: ok for label, ok, _ in results}
    assert result_map["duration_deviation"] is True


def test_verbatim_copy_of_creator_sentence_fails(
    evals_data: dict, timelines_data: dict
) -> None:
    item = _get_eval(evals_data, "eval-001-voiceover-breakfast")
    bad_output = copy.deepcopy(item["candidate_output"])
    # 注入真实达人笔记标题（出自真实时间线语料）
    creator_title = timelines_data["timelines"][0]["title"]
    bad_output["full_script"][-1]["voiceover"] += "，" + creator_title
    results = validate_output.validate(
        bad_output, generation_input=item["input"], timelines=timelines_data
    )
    result_map = {label: ok for label, ok, _ in results}
    assert result_map["verbatim_copy_check"] is False, "复制达人原句必须判失败"


def test_subtitle_format_requires_on_screen_text(
    evals_data: dict, timelines_data: dict
) -> None:
    item = _get_eval(evals_data, "eval-002-subtitle-afternoon-tea")
    bad_output = copy.deepcopy(item["candidate_output"])
    bad_output["full_script"][0]["on_screen_text"] = None
    results = validate_output.validate(
        bad_output, generation_input=item["input"], timelines=timelines_data
    )
    result_map = {label: ok for label, ok, _ in results}
    assert result_map["format_requirements"] is False


def test_cli_exit_codes(evals_data: dict, tmp_path: Path) -> None:
    positive = _get_eval(evals_data, "eval-001-voiceover-breakfast")
    negative = _get_eval(evals_data, COUNTEREVAL_ID)

    def run_cli(item: dict) -> subprocess.CompletedProcess[str]:
        out_path = tmp_path / f"{item['id']}-out.json"
        in_path = tmp_path / f"{item['id']}-in.json"
        out_path.write_text(
            json.dumps(item["candidate_output"], ensure_ascii=False), encoding="utf-8"
        )
        in_path.write_text(
            json.dumps(item["input"], ensure_ascii=False), encoding="utf-8"
        )
        return subprocess.run(
            [
                sys.executable,
                str(VALIDATOR_PATH),
                str(out_path),
                "--input",
                str(in_path),
                "--timelines",
                str(TIMELINES_PATH),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    ok_run = run_cli(positive)
    assert ok_run.returncode == 0, f"正例 CLI 应退出 0:\n{ok_run.stdout}\n{ok_run.stderr}"
    assert "[PASS] claim_evidence_coverage" in ok_run.stdout

    bad_run = run_cli(negative)
    assert bad_run.returncode == 1, f"反例 CLI 应退出 1:\n{bad_run.stdout}\n{bad_run.stderr}"
    assert "[FAIL] claim_evidence_coverage" in bad_run.stdout


def test_real_timelines_fixture_intact(timelines_data: dict) -> None:
    """真实证据资产可读且结构未变（3 条时间线）。"""
    timelines = timelines_data["timelines"]
    assert len(timelines) == 3
    note_ids = {t["note_id"] for t in timelines}
    assert note_ids == {
        "6989ab01000000001a0360c5",
        "6a58b7ea000000001101a7bb",
        "6a59b5ac00000000100295fe",
    }
