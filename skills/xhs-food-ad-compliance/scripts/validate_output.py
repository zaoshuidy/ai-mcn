"""xhs-food-ad-compliance 审核报告校验器。

校验合规审核报告 JSON 是否符合 references/output-schema.md：
1) 七个必填字段（risk_level / violations / evidence_mapping / required_changes /
   optional_changes / passed / human_review_required）与字段类型；
2) risk_level 枚举（none/low/medium/high/critical，以 output-schema.md 为准）；
3) violations[].rule_id 白名单（FAC-001~FAC-010，另放行 rules.md 附注定义的
   BRAND-CUSTOM，与 output-schema.md 的 pattern 一致）；
4) 一致性约束（SKILL.md 第 6 节 / output-schema.md「一致性约束」小节）：
   - 存在 severity=critical/high 的 violation 时 passed 必须为 false；
   - evidence_mapping 中存在 blocked 时 passed 必须为 false 且
     human_review_required 必须为 true；
   - 存在 brand_claim_context 时 human_review_required 必须为 true；
   - passed=false 时 required_changes 非空；
   - violations 非空时 risk_level 不得为 none；存在 critical 时 risk_level
     必须为 critical；
   - required_changes[].violation_rule_id 必须能在 violations.rule_id 中找到；
5) 引用回填检查：报告含 source_text 字段时，violations[].matched_text 必须是
   source_text 的子串（违规引用须能在被审原文中出现）。

独立运行：
    python skills/xhs-food-ad-compliance/scripts/validate_output.py <report.json>

退出码：0 = 通过；1 = 校验失败；2 = 用法/文件错误。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# risk_level 枚举以 references/output-schema.md 为准（含 none）。
RISK_LEVELS = ("none", "low", "medium", "high", "critical")
SEVERITIES = ("low", "medium", "high", "critical")
# 命中即不得通过的严重级。
BLOCKING_SEVERITIES = ("high", "critical")
CLAIM_TYPES = ("confirmed", "brand_claim", "subjective_experience", "unverified")
MAPPING_STATUSES = ("supported", "brand_claim_context", "subjective_only", "blocked")

# 与 output-schema.md 中 rule_id 的 pattern 保持一致。
RULE_ID_RE = re.compile(r"^(FAC-0(0[1-9]|10)|BRAND-CUSTOM)$")

REQUIRED_TOP_FIELDS = {
    "risk_level": str,
    "violations": list,
    "evidence_mapping": list,
    "required_changes": list,
    "optional_changes": list,
    "passed": bool,
    "human_review_required": bool,
}

VIOLATION_KEYS = ("rule_id", "rule_name", "severity", "matched_text",
                  "location", "issue", "suggestion")
MAPPING_KEYS = ("claim_in_script", "matched_product_claim", "claim_type", "status", "note")
REQUIRED_CHANGE_KEYS = ("violation_rule_id", "original", "replacement", "reason")
OPTIONAL_CHANGE_KEYS = ("original", "suggestion", "reason")


def _check_string_keys(
    errors: list[str], field: str, item: dict, keys: tuple[str, ...]
) -> None:
    """检查 object 中若干 key 存在且为 string。"""
    for key in keys:
        if key not in item:
            errors.append(f"{field}.{key}: 缺少必填字段")
        elif not isinstance(item[key], str):
            errors.append(f"{field}.{key}: 应为 string")


def validate_output(data: Any) -> list[str]:
    """校验审核报告对象，返回错误信息列表（空列表 = 通过）。"""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["顶层必须是 JSON object"]

    # --- 七个必填字段与类型 ---
    for field, expected in REQUIRED_TOP_FIELDS.items():
        if field not in data:
            errors.append(f"缺少必填字段: {field}")
        elif not isinstance(data[field], expected):
            errors.append(f"{field}: 类型错误，应为 {expected.__name__}")
    if errors:
        return errors

    # --- risk_level 枚举 ---
    if data["risk_level"] not in RISK_LEVELS:
        errors.append(f"risk_level: 应为枚举 {'/'.join(RISK_LEVELS)}")

    violations = data["violations"]
    mapping = data["evidence_mapping"]
    required_changes = data["required_changes"]
    optional_changes = data["optional_changes"]
    passed = data["passed"]
    human_review = data["human_review_required"]

    # --- violations ---
    violation_rule_ids: list[str] = []
    for i, item in enumerate(violations):
        field = f"violations[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{field}: 应为 object")
            continue
        _check_string_keys(errors, field, item, VIOLATION_KEYS)
        rule_id = item.get("rule_id")
        if isinstance(rule_id, str):
            if not RULE_ID_RE.match(rule_id):
                errors.append(
                    f"{field}.rule_id: 「{rule_id}」不在规则库白名单"
                    "（FAC-001~FAC-010 或 BRAND-CUSTOM）"
                )
            else:
                violation_rule_ids.append(rule_id)
        severity = item.get("severity")
        if isinstance(severity, str) and severity not in SEVERITIES:
            errors.append(f"{field}.severity: 应为枚举 {'/'.join(SEVERITIES)}")
        matched = item.get("matched_text")
        if isinstance(matched, str) and not matched.strip():
            errors.append(f"{field}.matched_text: 不允许为空字符串")

    # --- evidence_mapping ---
    for i, item in enumerate(mapping):
        field = f"evidence_mapping[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{field}: 应为 object")
            continue
        for key in MAPPING_KEYS:
            if key not in item:
                errors.append(f"{field}.{key}: 缺少必填字段")
        claim_in_script = item.get("claim_in_script")
        if "claim_in_script" in item and (
            not isinstance(claim_in_script, str) or not claim_in_script.strip()
        ):
            errors.append(f"{field}.claim_in_script: 应为非空 string")
        matched_claim = item.get("matched_product_claim")
        if "matched_product_claim" in item and (
            matched_claim is not None and not isinstance(matched_claim, str)
        ):
            errors.append(f"{field}.matched_product_claim: 应为 string 或 null")
        claim_type = item.get("claim_type")
        if "claim_type" in item and (
            claim_type is not None and claim_type not in CLAIM_TYPES
        ):
            errors.append(
                f"{field}.claim_type: 应为枚举 {'/'.join(CLAIM_TYPES)} 或 null"
            )
        status = item.get("status")
        if "status" in item and status not in MAPPING_STATUSES:
            errors.append(f"{field}.status: 应为枚举 {'/'.join(MAPPING_STATUSES)}")
        if "note" in item and not isinstance(item.get("note"), str):
            errors.append(f"{field}.note: 应为 string")

    # --- required_changes ---
    for i, item in enumerate(required_changes):
        field = f"required_changes[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{field}: 应为 object")
            continue
        _check_string_keys(errors, field, item, REQUIRED_CHANGE_KEYS)
        original = item.get("original")
        if isinstance(original, str) and not original.strip():
            errors.append(f"{field}.original: 不允许为空字符串")
        rule_id = item.get("violation_rule_id")
        if isinstance(rule_id, str) and rule_id not in violation_rule_ids:
            errors.append(
                f"{field}.violation_rule_id: 「{rule_id}」在 violations.rule_id 中无对应项"
            )

    # --- optional_changes ---
    for i, item in enumerate(optional_changes):
        field = f"optional_changes[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{field}: 应为 object")
            continue
        _check_string_keys(errors, field, item, OPTIONAL_CHANGE_KEYS)

    # --- 一致性约束 ---
    severities = [v.get("severity") for v in violations if isinstance(v, dict)]
    statuses = [m.get("status") for m in mapping if isinstance(m, dict)]

    if violations and data["risk_level"] == "none":
        errors.append("一致性: violations 非空时 risk_level 不得为 none")
    if "critical" in severities and data["risk_level"] != "critical":
        errors.append("一致性: 存在 severity=critical 时 risk_level 必须为 critical")

    if passed is True:
        if any(s in BLOCKING_SEVERITIES for s in severities):
            errors.append(
                "一致性: 存在 severity=critical/high 的 violation 时 passed 必须为 false"
            )
        if "blocked" in statuses:
            errors.append("一致性: evidence_mapping 存在 blocked 时 passed 必须为 false")
    if passed is False and not required_changes:
        errors.append("一致性: passed=false 时 required_changes 不得为空")

    if human_review is False:
        if "brand_claim_context" in statuses:
            errors.append(
                "一致性: 存在 brand_claim_context 时 human_review_required 必须为 true"
            )
        if "blocked" in statuses:
            errors.append("一致性: 存在 blocked 时 human_review_required 必须为 true")

    # --- source_text 引用回填检查 ---
    source_text = data.get("source_text")
    if source_text is not None:
        if not isinstance(source_text, str):
            errors.append("source_text: 应为 string（被审原文）")
        else:
            for i, item in enumerate(violations):
                if not isinstance(item, dict):
                    continue
                matched = item.get("matched_text")
                if isinstance(matched, str) and matched and matched not in source_text:
                    errors.append(
                        f"violations[{i}].matched_text: 引用片段未在 source_text 中"
                        f"出现: 「{matched[:30]}」"
                    )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="校验 xhs-food-ad-compliance 审核报告 JSON 是否符合 output-schema。"
    )
    parser.add_argument("report", help="待校验的审核报告 JSON 文件路径")
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    if not report_path.is_file():
        print(f"[FAIL] 报告文件不存在: {report_path}")
        return 2
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"[FAIL] 报告文件无法解析为 JSON: {exc}")
        return 2

    errors = validate_output(data)
    if errors:
        for line in errors:
            print(f"[FAIL] {line}")
        print(f"\n校验未通过：{len(errors)} 个问题。")
        return 1
    print("[PASS] 审核报告符合 xhs-food-ad-compliance output-schema 与一致性约束。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
