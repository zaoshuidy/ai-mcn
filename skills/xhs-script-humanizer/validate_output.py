"""xhs-script-humanizer 输出契约校验器。

校验内容（与 skills/xhs-script-humanizer/SKILL.md 的输出契约一致）：
1. schema 校验：必填字段、字段类型、style_match_score 范围、changes 条目结构
   与规则编号（R1 ~ R8）；
2. 事实保留检查：original_script 中的数字/百分比 token 与品牌名必须出现在
   preserved_facts 中，且在 humanized_script 中逐字保留、未被改变；
3. 评分一致性：possible_fact_drift 非空时 style_match_score 不得大于 0.9。

CLI 用法：
    python skills/xhs-script-humanizer/validate_output.py output.json --brand-term 轻醒

退出码：0 = 校验通过；1 = 校验失败或输入文件不可读。

已知限制：事实保留为"存在性"检查（token 在 humanized 中至少出现一次即视为保留），
不校验出现次数；品牌名按子串匹配，扩展写法（如"轻醒优选"）不会被识别为篡改。
语义级漂移依赖 possible_fact_drift 上报与下游 fact_regression 复检兜底。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

ALLOWED_RULE_IDS = frozenset({"R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"})
MAX_SCORE_WITH_DRIFT = 0.9

SCHEMA_MISSING_FIELD = "SCHEMA_MISSING_FIELD"
SCHEMA_TYPE_ERROR = "SCHEMA_TYPE_ERROR"
SCHEMA_INVALID_RULE_ID = "SCHEMA_INVALID_RULE_ID"
SCHEMA_SCORE_OUT_OF_RANGE = "SCHEMA_SCORE_OUT_OF_RANGE"
FACT_NOT_IN_PRESERVED = "FACT_NOT_IN_PRESERVED"
FACT_CHANGED_IN_HUMANIZED = "FACT_CHANGED_IN_HUMANIZED"
BRAND_NOT_IN_PRESERVED = "BRAND_NOT_IN_PRESERVED"
BRAND_CHANGED_IN_HUMANIZED = "BRAND_CHANGED_IN_HUMANIZED"
SCORE_DRIFT_INCONSISTENT = "SCORE_DRIFT_INCONSISTENT"

REQUIRED_FIELDS = (
    "original_script",
    "humanized_script",
    "changes",
    "preserved_facts",
    "possible_fact_drift",
    "style_match_score",
)

# 数字/百分比 token：支持范围值（22-35岁）与常见中文计量/语境单位。
# 单位集合覆盖 config/brief_rules.yaml fabrication_guard 的计量单位并扩展脚本常见语境。
NUMBER_TOKEN_RE = re.compile(
    r"\d+(?:\.\d+)?"
    r"(?:\s*[-–~到]\s*\d+(?:\.\d+)?)?"
    r"\s*(?:%|％|蔗糖|g|克|mg|毫克|kcal|千卡|大卡|千焦|kJ|KJ|ml|毫升|L|升"
    r"|岁|种|杯|袋|盒|瓶|秒|分钟|小时|元|块|折|天|周|次)?"
)

CHANGE_REQUIRED_KEYS = ("rule", "before", "after", "reason")


@dataclass(frozen=True)
class ValidationError:
    """单条校验错误。code 为机器可读错误码，token 为涉事事实锚点（如有）。"""

    code: str
    message: str
    token: Optional[str] = None


@dataclass(frozen=True)
class ValidationReport:
    """校验报告。errors 为空即通过。"""

    errors: tuple[ValidationError, ...]
    checked_fact_tokens: tuple[str, ...]
    checked_brand_terms: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": [
                {"code": e.code, "message": e.message, "token": e.token} for e in self.errors
            ],
            "checked_fact_tokens": list(self.checked_fact_tokens),
            "checked_brand_terms": list(self.checked_brand_terms),
        }


def _squash(text: str) -> str:
    """去除全部空白字符，用于跨排版的逐字比对。"""
    return re.sub(r"\s+", "", text)


def extract_number_tokens(text: str) -> list[str]:
    """提取文本中的数字/百分比事实锚点 token（去重、保序、去空白）。"""
    tokens: list[str] = []
    for match in NUMBER_TOKEN_RE.finditer(text):
        token = _squash(match.group(0))
        if token and token not in tokens:
            tokens.append(token)
    return tokens


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_str_list(value: Any, field_name: str, errors: list[ValidationError]) -> bool:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(
            ValidationError(SCHEMA_TYPE_ERROR, f"字段 {field_name} 必须为字符串数组")
        )
        return False
    return True


def _validate_changes(value: Any, errors: list[ValidationError]) -> None:
    if not isinstance(value, list):
        errors.append(ValidationError(SCHEMA_TYPE_ERROR, "字段 changes 必须为数组"))
        return
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(
                ValidationError(SCHEMA_TYPE_ERROR, f"changes[{index}] 必须为对象")
            )
            continue
        for key in CHANGE_REQUIRED_KEYS:
            if key not in item:
                errors.append(
                    ValidationError(
                        SCHEMA_MISSING_FIELD, f"changes[{index}] 缺少字段 {key}"
                    )
                )
        rule = item.get("rule")
        if isinstance(rule, str) and rule not in ALLOWED_RULE_IDS:
            errors.append(
                ValidationError(
                    SCHEMA_INVALID_RULE_ID,
                    f"changes[{index}].rule 必须为 R1 ~ R8，实际为 {rule!r}",
                    token=str(rule),
                )
            )
        for key in ("rule", "before", "after", "reason"):
            if key in item and not isinstance(item[key], str):
                errors.append(
                    ValidationError(
                        SCHEMA_TYPE_ERROR, f"changes[{index}].{key} 必须为字符串"
                    )
                )


def validate_output(
    payload: Any, brand_terms: Optional[Sequence[str]] = None
) -> ValidationReport:
    """校验一份 xhs-script-humanizer 输出，返回 ValidationReport。

    brand_terms：品牌名清单（如 ["轻醒"]）。出现在 original_script 中的品牌名
    必须列入 preserved_facts 且在 humanized_script 中逐字保留。
    """
    errors: list[ValidationError] = []
    if not isinstance(payload, dict):
        errors.append(ValidationError(SCHEMA_TYPE_ERROR, "输出必须为 JSON 对象"))
        return ValidationReport(tuple(errors), (), ())

    for field in REQUIRED_FIELDS:
        if field not in payload:
            errors.append(ValidationError(SCHEMA_MISSING_FIELD, f"缺少必填字段 {field}"))

    original = payload.get("original_script")
    humanized = payload.get("humanized_script")
    for name, value in (("original_script", original), ("humanized_script", humanized)):
        if name in payload and (not isinstance(value, str) or not value.strip()):
            errors.append(
                ValidationError(SCHEMA_TYPE_ERROR, f"字段 {name} 必须为非空字符串")
            )

    if "changes" in payload:
        _validate_changes(payload["changes"], errors)
    preserved = payload.get("preserved_facts")
    drift = payload.get("possible_fact_drift")
    preserved_ok = "preserved_facts" not in payload or _validate_str_list(
        preserved, "preserved_facts", errors
    )
    drift_ok = "possible_fact_drift" not in payload or _validate_str_list(
        drift, "possible_fact_drift", errors
    )

    score = payload.get("style_match_score")
    score_ok = True
    if "style_match_score" in payload:
        if not _is_number(score) or not 0 <= score <= 1:
            errors.append(
                ValidationError(
                    SCHEMA_SCORE_OUT_OF_RANGE,
                    "style_match_score 必须为 [0, 1] 区间内的数值",
                )
            )
            score_ok = False

    fact_tokens: tuple[str, ...] = ()
    checked_brands: tuple[str, ...] = ()
    texts_ready = (
        isinstance(original, str)
        and original.strip()
        and isinstance(humanized, str)
        and humanized.strip()
        and preserved_ok
        and isinstance(preserved, list)
    )
    if texts_ready:
        squashed_preserved = [_squash(item) for item in preserved]
        squashed_humanized = _squash(humanized)
        fact_tokens = tuple(extract_number_tokens(original))
        for token in fact_tokens:
            if not any(token in entry for entry in squashed_preserved):
                errors.append(
                    ValidationError(
                        FACT_NOT_IN_PRESERVED,
                        f"事实锚点 {token!r} 未列入 preserved_facts",
                        token=token,
                    )
                )
            if token not in squashed_humanized:
                errors.append(
                    ValidationError(
                        FACT_CHANGED_IN_HUMANIZED,
                        f"事实锚点 {token!r} 在 humanized_script 中被改变或丢失",
                        token=token,
                    )
                )
        brands = [b for b in (brand_terms or []) if _squash(b)]
        checked_brands = tuple(
            b for b in brands if _squash(b) in _squash(original)
        )
        for brand in checked_brands:
            squashed_brand = _squash(brand)
            if not any(squashed_brand in entry for entry in squashed_preserved):
                errors.append(
                    ValidationError(
                        BRAND_NOT_IN_PRESERVED,
                        f"品牌名 {brand!r} 未列入 preserved_facts",
                        token=brand,
                    )
                )
            if squashed_brand not in squashed_humanized:
                errors.append(
                    ValidationError(
                        BRAND_CHANGED_IN_HUMANIZED,
                        f"品牌名 {brand!r} 在 humanized_script 中被改变或丢失",
                        token=brand,
                    )
                )

    if (
        drift_ok
        and isinstance(drift, list)
        and drift
        and score_ok
        and _is_number(score)
        and score > MAX_SCORE_WITH_DRIFT
    ):
        errors.append(
            ValidationError(
                SCORE_DRIFT_INCONSISTENT,
                "possible_fact_drift 非空时 style_match_score 不得大于 "
                f"{MAX_SCORE_WITH_DRIFT}，实际为 {score}",
            )
        )

    return ValidationReport(tuple(errors), fact_tokens, checked_brands)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="xhs-script-humanizer 输出契约校验器")
    parser.add_argument("output_json", help="待校验的输出 JSON 文件路径")
    parser.add_argument(
        "--brand-term",
        dest="brand_terms",
        action="append",
        default=[],
        help="品牌名（可多次传入），如 --brand-term 轻醒",
    )
    args = parser.parse_args(argv)

    path = Path(args.output_json)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {"is_valid": False, "errors": [{"code": "INPUT_UNREADABLE",
                                                 "message": str(exc), "token": None}]},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    report = validate_output(payload, brand_terms=args.brand_terms)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
