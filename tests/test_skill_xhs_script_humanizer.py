"""skills/xhs-script-humanizer 的契约与校验器测试（不依赖真实 LLM）。

覆盖：
- Skill 标准目录结构与编排约束（Humanizer 不得为最终节点）；
- validate_output.py 的 schema 校验、事实保留检查、评分一致性检查；
- evals.json 中 3 条正例全部通过、1 条反例（数字/品牌名被篡改）必须判失败。
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills/xhs-script-humanizer"
MODULE_PATH = SKILL_DIR / "scripts" / "validate_output.py"
EVALS_PATH = SKILL_DIR / "evals" / "evals.json"

spec = importlib.util.spec_from_file_location(
    "xhs_script_humanizer_validate_output", MODULE_PATH
)
assert spec is not None and spec.loader is not None
vo = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = vo  # dataclass 处理需要模块已注册
spec.loader.exec_module(vo)

BRAND_TERMS = ["轻醒"]


def make_valid_payload() -> dict:
    return {
        "original_script": "轻醒0蔗糖酸奶，适合22-35岁早餐场景。",
        "humanized_script": "早上赶时间，就喝轻醒的0蔗糖酸奶，22-35岁的我常备。",
        "changes": [
            {"rule": "R1", "before": "适合", "after": "就喝", "reason": "口语化"}
        ],
        "preserved_facts": ["品牌名：轻醒", "0蔗糖", "人群：22-35岁"],
        "possible_fact_drift": [],
        "style_match_score": 0.9,
    }


def load_evals() -> dict:
    return json.loads(EVALS_PATH.read_text(encoding="utf-8"))


class TestSkillStructure:
    def test_required_files_exist(self) -> None:
        for name in (
            "SKILL.md",
            "references/rules.md",
            "references/examples.md",
            "references/output-schema.md",
            "evals/evals.json",
            "scripts/validate_output.py",
        ):
            assert (SKILL_DIR / name).is_file(), f"缺少 {name}"

    def test_skill_md_frontmatter(self) -> None:
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---")
        frontmatter = text.split("---", 2)[1]
        assert "name: xhs-script-humanizer" in frontmatter
        assert "description:" in frontmatter

    def test_skill_md_declares_mandatory_reviews(self) -> None:
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        for keyword in ("fact_regression", "compliance_review", "style_consistency_review"):
            assert keyword in text, f"SKILL.md 缺少复检环节 {keyword}"
        assert "最终节点" in text, "SKILL.md 必须声明 Humanizer 不得为最终节点"

    def test_rules_md_contains_all_rules_and_reviews(self) -> None:
        text = (SKILL_DIR / "references" / "rules.md").read_text(encoding="utf-8")
        for rule_id in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"):
            assert re.search(rf"## {rule_id} ", text), f"rules.md 缺少规则 {rule_id}"
        for keyword in ("fact_regression", "compliance_review", "style_consistency_review"):
            assert keyword in text
        assert "最终节点" in text
        assert "无糖" in text and "0蔗糖" in text, "rules.md 须写明 0蔗糖≠无糖 红线"
        assert "ProductEvidence" in text

    def test_examples_md_has_full_comparison(self) -> None:
        text = (SKILL_DIR / "references" / "examples.md").read_text(encoding="utf-8")
        for keyword in ("original_script", "humanized_script", "changes",
                        "preserved_facts", "possible_fact_drift", "style_match_score"):
            assert keyword in text


class TestExtractNumberTokens:
    def test_range_token_kept_whole(self) -> None:
        assert "22-35岁" in vo.extract_number_tokens("适合22-35岁的都市女性")

    def test_brand_claim_token_and_dedupe(self) -> None:
        tokens = vo.extract_number_tokens("0蔗糖，它0蔗糖，高蛋白")
        assert tokens.count("0蔗糖") == 1

    def test_percent_and_unit_tokens(self) -> None:
        tokens = vo.extract_number_tokens("蛋白质含量3.2g，占比15%")
        assert "3.2g" in tokens
        assert "15%" in tokens


class TestSchemaValidation:
    def test_valid_payload_passes(self) -> None:
        report = vo.validate_output(make_valid_payload(), brand_terms=BRAND_TERMS)
        assert report.is_valid, [e.message for e in report.errors]

    def test_non_dict_payload_rejected(self) -> None:
        report = vo.validate_output(["not", "a", "dict"], brand_terms=BRAND_TERMS)
        assert not report.is_valid
        assert any(e.code == vo.SCHEMA_TYPE_ERROR for e in report.errors)

    def test_missing_required_field(self) -> None:
        payload = make_valid_payload()
        del payload["humanized_script"]
        report = vo.validate_output(payload, brand_terms=BRAND_TERMS)
        assert not report.is_valid
        assert any(e.code == vo.SCHEMA_MISSING_FIELD for e in report.errors)

    def test_score_out_of_range(self) -> None:
        payload = make_valid_payload()
        payload["style_match_score"] = 1.5
        report = vo.validate_output(payload, brand_terms=BRAND_TERMS)
        assert any(e.code == vo.SCHEMA_SCORE_OUT_OF_RANGE for e in report.errors)

    def test_bool_score_rejected(self) -> None:
        payload = make_valid_payload()
        payload["style_match_score"] = True
        report = vo.validate_output(payload, brand_terms=BRAND_TERMS)
        assert any(e.code == vo.SCHEMA_SCORE_OUT_OF_RANGE for e in report.errors)

    def test_invalid_rule_id(self) -> None:
        payload = make_valid_payload()
        payload["changes"][0]["rule"] = "R9"
        report = vo.validate_output(payload, brand_terms=BRAND_TERMS)
        assert any(e.code == vo.SCHEMA_INVALID_RULE_ID for e in report.errors)

    def test_change_entry_missing_key(self) -> None:
        payload = make_valid_payload()
        del payload["changes"][0]["reason"]
        report = vo.validate_output(payload, brand_terms=BRAND_TERMS)
        assert any(e.code == vo.SCHEMA_MISSING_FIELD for e in report.errors)


class TestFactPreservation:
    def test_number_changed_in_humanized(self) -> None:
        payload = make_valid_payload()
        payload["humanized_script"] = payload["humanized_script"].replace(
            "22-35岁", "25-35岁"
        )
        report = vo.validate_output(payload, brand_terms=BRAND_TERMS)
        assert not report.is_valid
        assert any(
            e.code == vo.FACT_CHANGED_IN_HUMANIZED and e.token == "22-35岁"
            for e in report.errors
        )

    def test_number_not_listed_in_preserved_facts(self) -> None:
        payload = make_valid_payload()
        payload["preserved_facts"] = ["品牌名：轻醒", "0蔗糖"]
        report = vo.validate_output(payload, brand_terms=BRAND_TERMS)
        assert any(
            e.code == vo.FACT_NOT_IN_PRESERVED and e.token == "22-35岁"
            for e in report.errors
        )

    def test_zero_sugar_rewritten_as_sugar_free_blocked(self) -> None:
        payload = make_valid_payload()
        payload["humanized_script"] = payload["humanized_script"].replace(
            "0蔗糖", "无糖"
        )
        payload["preserved_facts"] = ["品牌名：轻醒", "无糖", "人群：22-35岁"]
        report = vo.validate_output(payload, brand_terms=BRAND_TERMS)
        assert not report.is_valid
        assert any(
            e.code == vo.FACT_CHANGED_IN_HUMANIZED and e.token == "0蔗糖"
            for e in report.errors
        )

    def test_brand_removed_in_humanized(self) -> None:
        payload = make_valid_payload()
        payload["humanized_script"] = payload["humanized_script"].replace(
            "轻醒", "这款"
        )
        report = vo.validate_output(payload, brand_terms=BRAND_TERMS)
        assert any(e.code == vo.BRAND_CHANGED_IN_HUMANIZED for e in report.errors)

    def test_brand_not_listed_in_preserved_facts(self) -> None:
        payload = make_valid_payload()
        payload["preserved_facts"] = ["0蔗糖", "人群：22-35岁"]
        report = vo.validate_output(payload, brand_terms=BRAND_TERMS)
        assert any(
            e.code == vo.BRAND_NOT_IN_PRESERVED and e.token == "轻醒"
            for e in report.errors
        )

    def test_whitespace_difference_tolerated(self) -> None:
        payload = make_valid_payload()
        payload["humanized_script"] = "早上赶时间，就喝轻醒的 0蔗糖 酸奶，22-35岁 的我常备。"
        report = vo.validate_output(payload, brand_terms=BRAND_TERMS)
        assert report.is_valid, [e.message for e in report.errors]


class TestScoreDriftConsistency:
    def test_drift_with_high_score_rejected(self) -> None:
        payload = make_valid_payload()
        payload["possible_fact_drift"] = ["低负担改写为怕负担重"]
        payload["style_match_score"] = 0.95
        report = vo.validate_output(payload, brand_terms=BRAND_TERMS)
        assert any(e.code == vo.SCORE_DRIFT_INCONSISTENT for e in report.errors)

    def test_drift_with_boundary_score_allowed(self) -> None:
        payload = make_valid_payload()
        payload["possible_fact_drift"] = ["低负担改写为怕负担重"]
        payload["style_match_score"] = 0.9
        report = vo.validate_output(payload, brand_terms=BRAND_TERMS)
        assert report.is_valid, [e.message for e in report.errors]

    def test_no_drift_high_score_allowed(self) -> None:
        payload = make_valid_payload()
        payload["style_match_score"] = 0.98
        report = vo.validate_output(payload, brand_terms=BRAND_TERMS)
        assert report.is_valid, [e.message for e in report.errors]


class TestEvalsJson:
    def test_evals_count_and_kinds(self) -> None:
        data = load_evals()
        evals = data["evals"]
        assert len(evals) == 4
        positives = [e for e in evals if e["kind"] == "positive"]
        counterexamples = [e for e in evals if e["kind"] == "counterexample"]
        assert len(positives) == 3
        assert len(counterexamples) == 1
        assert len({e["id"] for e in evals}) == 4

    def test_positive_evals_all_pass(self) -> None:
        data = load_evals()
        for item in data["evals"]:
            if item["kind"] != "positive":
                continue
            report = vo.validate_output(
                item["expected_output"], brand_terms=data["brand_terms"]
            )
            assert report.is_valid, (
                f"{item['id']} 未通过校验: "
                f"{[e.message for e in report.errors]}"
            )

    def test_positive_evals_preserve_original_verbatim(self) -> None:
        data = load_evals()
        for item in data["evals"]:
            if item["kind"] != "positive":
                continue
            assert item["expected_output"]["original_script"] == (
                item["input"]["original_script"]
            )
            assert item["expected_output"]["preserved_facts"]

    def test_counterexample_rejected_with_expected_codes(self) -> None:
        data = load_evals()
        counterexample = next(
            e for e in data["evals"] if e["kind"] == "counterexample"
        )
        report = vo.validate_output(
            counterexample["output"], brand_terms=data["brand_terms"]
        )
        assert not report.is_valid, "数字/品牌名被篡改的反例必须判失败"
        codes = {e.code for e in report.errors}
        for expected_code in counterexample["expected_error_codes"]:
            assert expected_code in codes, f"反例未命中预期错误码 {expected_code}"

    def test_counterexample_flags_sugar_free_tampering(self) -> None:
        data = load_evals()
        counterexample = next(
            e for e in data["evals"] if e["kind"] == "counterexample"
        )
        report = vo.validate_output(
            counterexample["output"], brand_terms=data["brand_terms"]
        )
        assert any(
            e.code == vo.FACT_CHANGED_IN_HUMANIZED and e.token == "0蔗糖"
            for e in report.errors
        )


class TestExamplesMdConsistency:
    def test_examples_md_output_block_passes_validation(self) -> None:
        text = (SKILL_DIR / "references" / "examples.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```json\n(.*?)```", text, flags=re.DOTALL)
        assert len(blocks) >= 2, "examples.md 应包含输入与输出两个 JSON 块"
        output_payload = json.loads(blocks[1])
        report = vo.validate_output(output_payload, brand_terms=BRAND_TERMS)
        assert report.is_valid, [e.message for e in report.errors]


class TestCli:
    def test_cli_valid_exit_zero(self, tmp_path: Path, capsys) -> None:
        path = tmp_path / "ok.json"
        path.write_text(
            json.dumps(make_valid_payload(), ensure_ascii=False), encoding="utf-8"
        )
        exit_code = vo.main([str(path), "--brand-term", "轻醒"])
        assert exit_code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["is_valid"]

    def test_cli_tampered_exit_one(self, tmp_path: Path, capsys) -> None:
        payload = make_valid_payload()
        payload["humanized_script"] = payload["humanized_script"].replace(
            "0蔗糖", "无糖"
        )
        path = tmp_path / "bad.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        exit_code = vo.main([str(path), "--brand-term", "轻醒"])
        assert exit_code == 1
        out = json.loads(capsys.readouterr().out)
        assert not out["is_valid"]

    def test_cli_unreadable_file_exit_one(self, tmp_path: Path, capsys) -> None:
        path = tmp_path / "missing.json"
        assert vo.main([str(path)]) == 1
        capsys.readouterr()
