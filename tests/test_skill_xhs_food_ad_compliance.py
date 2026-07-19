"""xhs-food-ad-compliance 审核报告校验器单元测试（离线，不依赖小红书）。

正例：references/examples.md 示例 1 违规报告（结构合法、passed=false，应通过校验器）
与示例 2 全合规报告（passed=true）。
负例：必填字段缺失/类型错误、risk_level 与 severity 枚举越界、rule_id 越界、
critical/high 却 passed=true、blocked 却 passed=true、brand_claim_context 却
human_review_required=false、passed=false 却 required_changes 为空、
matched_text 未在 source_text 中出现、risk_level 与 violations 不一致、
required_changes 引用不存在的 rule_id、文件缺失/非法 JSON。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "skills" / "xhs-food-ad-compliance" / "scripts" / "validate_output.py"

# examples.md 示例 1 的被审原文（用于 source_text 引用回填检查）。
SOURCE_TEXT = (
    "标题：控糖期最健康的早餐，无糖酸奶真的绝了\n"
    "字幕1：打工人早餐不知道吃啥的姐妹看过来\n"
    "字幕2：最近挖到轻醒这款无糖希腊酸奶，0糖0负担\n"
    "字幕3：每杯15g蛋白质，喝一杯扛饿一上午\n"
    "字幕4：不升糖，控糖期放心喝，还能养胃\n"
    "字幕5：喝它不怕胖，小肚子都平了\n"
    "字幕6：比其他酸奶配料干净多了，完胜便利店\n"
    "话题标签：#早餐 #减肥餐 #控糖饮食"
)


def _violation(
    rule_id: str = "FAC-003",
    severity: str = "high",
    matched_text: str = "喝它不怕胖",
) -> dict:
    return {
        "rule_id": rule_id,
        "rule_name": "禁止减肥/燃脂/掉秤等减重功效",
        "severity": severity,
        "matched_text": matched_text,
        "location": "字幕5",
        "issue": "减重功效表述",
        "suggestion": "删除",
    }


def _minimal_passed_report() -> dict:
    """最小合法全合规报告（passed=true，无违规、无映射）。"""
    return {
        "risk_level": "none",
        "violations": [],
        "evidence_mapping": [],
        "required_changes": [],
        "optional_changes": [],
        "passed": True,
        "human_review_required": False,
    }


def _example1_violation_report() -> dict:
    """references/examples.md 示例 1 的违规审核报告（passed=false，结构合法）。"""
    return {
        "risk_level": "critical",
        "violations": [
            {"rule_id": "FAC-001", "rule_name": "0蔗糖不得表述为无糖", "severity": "high",
             "matched_text": "无糖酸奶真的绝了", "location": "标题",
             "issue": "ProductEvidence 仅有「0蔗糖」（brand_claim），标题升级为「无糖」",
             "suggestion": "改为「0蔗糖酸奶」或删除糖分表述"},
            {"rule_id": "FAC-001", "rule_name": "0蔗糖不得表述为无糖", "severity": "high",
             "matched_text": "无糖希腊酸奶，0糖0负担", "location": "字幕2",
             "issue": "「无糖」「0糖」均属 0蔗糖→无糖 的禁止解释",
             "suggestion": "改为「0蔗糖希腊酸奶」"},
            {"rule_id": "FAC-009", "rule_name": "unverified 卖点不得表述为事实（低负担类）",
             "severity": "high", "matched_text": "0负担", "location": "字幕2",
             "issue": "「低负担」claim_type=unverified，且命中 forbidden_interpretations",
             "suggestion": "删除「0负担」"},
            {"rule_id": "FAC-002", "rule_name": "无证据不得标注营养数值", "severity": "high",
             "matched_text": "每杯15g蛋白质", "location": "字幕3",
             "issue": "ProductEvidence 无 confirmed 营养数据，不得标注具体克数",
             "suggestion": "删除「15g」，改为「高蛋白」定性表述"},
            {"rule_id": "FAC-007", "rule_name": "主观体验不得表述为客观功效",
             "severity": "medium", "matched_text": "喝一杯扛饿一上午", "location": "字幕3",
             "issue": "饱腹感为 subjective_experience，此处量化为普遍功效",
             "suggestion": "改为个人体验表达，或删除"},
            {"rule_id": "FAC-004", "rule_name": "禁止降糖/控糖功效承诺", "severity": "high",
             "matched_text": "不升糖，控糖期放心喝", "location": "字幕4",
             "issue": "「不升糖」为血糖功效承诺",
             "suggestion": "整句删除"},
            {"rule_id": "FAC-005", "rule_name": "禁止医疗效果", "severity": "critical",
             "matched_text": "还能养胃", "location": "字幕4",
             "issue": "「养胃」属医疗效果暗示",
             "suggestion": "删除「还能养胃」"},
            {"rule_id": "FAC-003", "rule_name": "禁止减肥/燃脂/掉秤等减重功效",
             "severity": "high", "matched_text": "喝它不怕胖，小肚子都平了",
             "location": "字幕5", "issue": "减重功效的明示/暗示表达",
             "suggestion": "整句删除"},
            {"rule_id": "FAC-010", "rule_name": "禁止贬低竞品", "severity": "medium",
             "matched_text": "比其他酸奶配料干净多了，完胜便利店", "location": "字幕6",
             "issue": "「完胜」构成对其他生产经营者的贬低性对比",
             "suggestion": "删除对比，仅保留自身特点描述"},
            {"rule_id": "FAC-006", "rule_name": "禁止绝对化表达", "severity": "medium",
             "matched_text": "最健康的早餐", "location": "标题",
             "issue": "「最健康」为指向产品的绝对化用语",
             "suggestion": "改为具体场景描述"},
            {"rule_id": "FAC-003", "rule_name": "禁止减肥/燃脂/掉秤等减重功效",
             "severity": "high", "matched_text": "#减肥餐", "location": "话题标签",
             "issue": "话题标签同样属于广告文本，#减肥餐 暗示减重功效",
             "suggestion": "删除该标签"},
        ],
        "evidence_mapping": [
            {"claim_in_script": "无糖 / 0糖", "matched_product_claim": "0蔗糖",
             "claim_type": "brand_claim", "status": "blocked",
             "note": "命中 forbidden_interpretations（无糖）"},
            {"claim_in_script": "每杯15g蛋白质", "matched_product_claim": "高蛋白",
             "claim_type": "brand_claim", "status": "blocked",
             "note": "brand_claim 不得升级为事实并标注数值"},
            {"claim_in_script": "扛饿一上午", "matched_product_claim": "饱腹感",
             "claim_type": "subjective_experience", "status": "subjective_only",
             "note": "仅允许个人体验语境"},
            {"claim_in_script": "0负担", "matched_product_claim": "低负担",
             "claim_type": "unverified", "status": "blocked",
             "note": "unverified 不得表述为事实"},
            {"claim_in_script": "不升糖 / 养胃 / 不怕胖", "matched_product_claim": None,
             "claim_type": None, "status": "blocked",
             "note": "ProductEvidence 中无任何对应卖点"},
        ],
        "required_changes": [
            {"violation_rule_id": "FAC-001",
             "original": "标题：控糖期最健康的早餐，无糖酸奶真的绝了",
             "replacement": "标题：打工人的快手早餐，0蔗糖酸奶真的绝了",
             "reason": "FAC-001 无糖→0蔗糖；FAC-006 删除绝对化「最健康」"},
            {"violation_rule_id": "FAC-001",
             "original": "字幕2：最近挖到轻醒这款无糖希腊酸奶，0糖0负担",
             "replacement": "字幕2：最近挖到轻醒这款0蔗糖希腊酸奶",
             "reason": "FAC-001 无糖/0糖→0蔗糖；FAC-009 删除「0负担」"},
            {"violation_rule_id": "FAC-002",
             "original": "字幕3：每杯15g蛋白质，喝一杯扛饿一上午",
             "replacement": "字幕3：高蛋白的一杯，我吃完到中午都不太想零食",
             "reason": "FAC-002 删除无证据数值；FAC-007 改个人体验语境"},
            {"violation_rule_id": "FAC-004",
             "original": "字幕4：不升糖，控糖期放心喝，还能养胃",
             "replacement": "删除",
             "reason": "FAC-004 血糖功效承诺；FAC-005 医疗效果暗示"},
            {"violation_rule_id": "FAC-003",
             "original": "字幕5：喝它不怕胖，小肚子都平了",
             "replacement": "删除",
             "reason": "FAC-003 减重功效"},
            {"violation_rule_id": "FAC-010",
             "original": "字幕6：比其他酸奶配料干净多了，完胜便利店",
             "replacement": "字幕6：配料表很干净，早餐来一杯很清爽",
             "reason": "FAC-010 删除竞品贬低"},
            {"violation_rule_id": "FAC-003",
             "original": "话题标签：#早餐 #减肥餐 #控糖饮食",
             "replacement": "话题标签：#早餐 #快手早餐 #打工人早餐",
             "reason": "FAC-003 删除 #减肥餐"},
        ],
        "optional_changes": [
            {"original": "话题标签 #控糖饮食",
             "suggestion": "「控糖」作为人群兴趣标签可保留，建议人工复核语境",
             "reason": "轻醒 brief 契约：控糖仅可作为人群兴趣标签"},
            {"original": "字幕1：打工人早餐不知道吃啥的姐妹看过来",
             "suggestion": "无违规；人群标签放此处远离产品卖点句",
             "reason": "预防性提示"},
        ],
        "passed": False,
        "human_review_required": True,
    }


def _example2_passed_report() -> dict:
    """references/examples.md 示例 2 的全合规报告（passed=true）。"""
    return {
        "risk_level": "none",
        "violations": [],
        "evidence_mapping": [
            {"claim_in_script": "0蔗糖", "matched_product_claim": "0蔗糖",
             "claim_type": "brand_claim", "status": "brand_claim_context",
             "note": "可提及，未升级为无糖、未加数值"},
            {"claim_in_script": "高蛋白", "matched_product_claim": "高蛋白",
             "claim_type": "brand_claim", "status": "brand_claim_context",
             "note": "定性表述，无数值"},
            {"claim_in_script": "我吃完到中午都不太想零食",
             "matched_product_claim": "饱腹感",
             "claim_type": "subjective_experience", "status": "subjective_only",
             "note": "个人体验语境，符合要求"},
        ],
        "required_changes": [],
        "optional_changes": [
            {"original": "0蔗糖 / 高蛋白（brand_claim）",
             "suggestion": "品牌方提供依据后可升级为 confirmed",
             "reason": "当前依据待品牌方提供"},
        ],
        "passed": True,
        "human_review_required": True,
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


# ---------- 正例 ----------


def test_example1_violation_report_passes_validator(tmp_path: Path) -> None:
    """examples.md 违规报告结构合法（passed=false 是审核结论，不影响校验通过）。"""
    out = _write_json(tmp_path, "report.json", _example1_violation_report())
    result = _run_validator(str(out))
    assert result.returncode == 0, result.stdout
    assert "[PASS]" in result.stdout


def test_example2_compliant_report_passes_validator(tmp_path: Path) -> None:
    """examples.md 全合规报告（passed=true，brand_claim_context 致人工复核）。"""
    out = _write_json(tmp_path, "report.json", _example2_passed_report())
    result = _run_validator(str(out))
    assert result.returncode == 0, result.stdout


def test_example1_with_source_text_all_quotes_verified(tmp_path: Path) -> None:
    """违规报告附带 source_text 时，全部 matched_text 均能在原文中找到。"""
    data = _example1_violation_report()
    data["source_text"] = SOURCE_TEXT
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 0, result.stdout


# ---------- 必填字段与类型 ----------


@pytest.mark.parametrize("field", [
    "risk_level", "violations", "evidence_mapping", "required_changes",
    "optional_changes", "passed", "human_review_required",
])
def test_missing_required_field_fails(tmp_path: Path, field: str) -> None:
    data = _minimal_passed_report()
    del data[field]
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert field in result.stdout


@pytest.mark.parametrize("field,bad_value", [
    ("violations", {"rule_id": "FAC-001"}),
    ("passed", "true"),
    ("human_review_required", 1),
    ("risk_level", 3),
])
def test_top_field_wrong_type_fails(tmp_path: Path, field: str, bad_value) -> None:
    data = _minimal_passed_report()
    data[field] = bad_value
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert field in result.stdout


# ---------- 枚举 ----------


@pytest.mark.parametrize("bad_level", ["fatal", "NONE", "moderate"])
def test_invalid_risk_level_fails(tmp_path: Path, bad_level: str) -> None:
    data = _minimal_passed_report()
    data["risk_level"] = bad_level
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "risk_level" in result.stdout


def test_invalid_severity_fails(tmp_path: Path) -> None:
    data = _example1_violation_report()
    data["violations"][0]["severity"] = "fatal"
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "severity" in result.stdout


def test_invalid_mapping_status_fails(tmp_path: Path) -> None:
    data = _example2_passed_report()
    data["evidence_mapping"][0]["status"] = "unknown_status"
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "status" in result.stdout


# ---------- rule_id 白名单 ----------


@pytest.mark.parametrize("bad_rule_id", [
    "FAC-000", "FAC-011", "FAC-100", "FAC-1", "fac-003", "XYZ-001",
])
def test_rule_id_out_of_range_fails(tmp_path: Path, bad_rule_id: str) -> None:
    data = _example1_violation_report()
    data["violations"][0]["rule_id"] = bad_rule_id
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "rule_id" in result.stdout


def test_brand_custom_rule_id_allowed(tmp_path: Path) -> None:
    """rules.md 附注定义的品牌方自定义规则 ID 应放行。"""
    data = _example1_violation_report()
    data["violations"][0]["rule_id"] = "BRAND-CUSTOM"
    data["required_changes"][0]["violation_rule_id"] = "BRAND-CUSTOM"
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 0, result.stdout


# ---------- 一致性约束：passed ----------


def test_critical_violation_but_passed_true_fails(tmp_path: Path) -> None:
    data = _example1_violation_report()
    data["passed"] = True
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "passed" in result.stdout


def test_high_violation_but_passed_true_fails(tmp_path: Path) -> None:
    """仅含 high（无 critical、无 blocked）时 passed=true 同样失败。"""
    data = _minimal_passed_report()
    data["risk_level"] = "high"
    data["violations"] = [_violation(severity="high")]
    data["passed"] = True
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "passed" in result.stdout


def test_blocked_but_passed_true_fails(tmp_path: Path) -> None:
    data = _minimal_passed_report()
    data["evidence_mapping"] = [
        {"claim_in_script": "0糖", "matched_product_claim": "0蔗糖",
         "claim_type": "brand_claim", "status": "blocked", "note": "禁止解释"}
    ]
    data["passed"] = True
    data["human_review_required"] = True
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "blocked" in result.stdout


def test_passed_false_but_required_changes_empty_fails(tmp_path: Path) -> None:
    data = _minimal_passed_report()
    data["passed"] = False
    data["human_review_required"] = True
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "required_changes" in result.stdout


# ---------- 一致性约束：human_review_required ----------


def test_brand_claim_context_but_human_review_false_fails(tmp_path: Path) -> None:
    data = _example2_passed_report()
    data["human_review_required"] = False
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "human_review_required" in result.stdout


def test_blocked_but_human_review_false_fails(tmp_path: Path) -> None:
    data = _example1_violation_report()
    data["human_review_required"] = False
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "human_review_required" in result.stdout


# ---------- 一致性约束：risk_level 与引用 ----------


def test_risk_level_none_with_violations_fails(tmp_path: Path) -> None:
    data = _example1_violation_report()
    data["risk_level"] = "none"
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "risk_level" in result.stdout


def test_critical_violation_but_risk_level_not_critical_fails(tmp_path: Path) -> None:
    data = _example1_violation_report()
    data["risk_level"] = "high"
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "risk_level" in result.stdout


def test_required_changes_unknown_rule_id_fails(tmp_path: Path) -> None:
    data = _example1_violation_report()
    data["required_changes"][0]["violation_rule_id"] = "FAC-008"
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "violation_rule_id" in result.stdout


# ---------- source_text 引用回填 ----------


def test_matched_text_not_in_source_text_fails(tmp_path: Path) -> None:
    data = _example1_violation_report()
    data["source_text"] = SOURCE_TEXT
    data["violations"][0]["matched_text"] = "原文中根本不存在的引用片段"
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "source_text" in result.stdout


# ---------- 嵌套对象字段缺失 ----------


def test_violation_missing_required_key_fails(tmp_path: Path) -> None:
    data = _example1_violation_report()
    del data["violations"][0]["matched_text"]
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "matched_text" in result.stdout


def test_evidence_mapping_missing_required_key_fails(tmp_path: Path) -> None:
    data = _example2_passed_report()
    del data["evidence_mapping"][0]["status"]
    out = _write_json(tmp_path, "report.json", data)
    result = _run_validator(str(out))
    assert result.returncode == 1
    assert "status" in result.stdout


# ---------- 用法/文件错误 ----------


def test_missing_report_file_returns_2(tmp_path: Path) -> None:
    result = _run_validator(str(tmp_path / "nonexistent.json"))
    assert result.returncode == 2


def test_invalid_json_returns_2(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    result = _run_validator(str(bad))
    assert result.returncode == 2



# ---------- evals.json 回放（3 真实 + 1 反例） ----------


EVALS_PATH = (
    ROOT / "skills" / "xhs-food-ad-compliance" / "evals" / "evals.json"
)


def _load_evals() -> dict:
    return json.loads(EVALS_PATH.read_text(encoding="utf-8"))


def test_evals_file_structure() -> None:
    data = _load_evals()
    assert data["skill"] == "xhs-food-ad-compliance"
    evals = data["evals"]
    assert len(evals) == 4, "应为 3 真实 eval + 1 反例"
    types = [e["type"] for e in evals]
    assert types.count("positive") == 3
    assert types.count("counter_example") == 1
    assert len({e["id"] for e in evals}) == 4
    for e in evals:
        assert {"id", "name", "type", "source", "report", "expect"} <= set(e)
        assert "validator_exit_code" in e["expect"]


def test_evals_real_qingxing_report_matches_source() -> None:
    """eval_003 内嵌报告必须与真实产物 outputs/qingxing/compliance_report.json 一致。"""
    data = _load_evals()
    eval_003 = next(e for e in data["evals"] if e["id"] == "eval_003")
    real = json.loads(
        (ROOT / "outputs" / "qingxing" / "compliance_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert eval_003["report"] == real


@pytest.mark.parametrize(
    "eval_case",
    _load_evals()["evals"],
    ids=lambda e: e["id"],
)
def test_eval_replay(eval_case, tmp_path: Path) -> None:
    out = _write_json(tmp_path, "report.json", eval_case["report"])
    result = _run_validator(str(out))
    expected_code = eval_case["expect"]["validator_exit_code"]
    assert result.returncode == expected_code, (
        f"{eval_case['id']} 期望退出码 {expected_code}，实际 {result.returncode}: "
        f"{result.stdout}"
    )
    for keyword in eval_case["expect"].get("expected_failure_keywords", []):
        assert keyword in result.stdout
