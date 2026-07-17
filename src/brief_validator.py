"""品牌 Brief 业务规则校验器。

按 config/brief_rules.yaml 对 BrandBrief 模型执行业务规则校验，
承载合规边界：卖点证据等级、禁止解释方向、人群兴趣标签与产品功效隔离、
禁止臆造营养/检测数据、缺失信息识别。

校验不修改模型，只输出 Issue 清单；存在 error 级 Issue 即视为不通过。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .brief_models import BrandBrief, ClaimType

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


@dataclass
class Issue:
    """单条校验问题。"""

    severity: str  # error / warning
    code: str
    message: str


@dataclass
class ValidationResult:
    """校验结果。"""

    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == SEVERITY_WARNING]

    @property
    def is_valid(self) -> bool:
        return not self.errors


def load_rules(path: str | Path) -> dict:
    """加载业务规则文件。"""
    with Path(path).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _numeric_pattern(rules: dict) -> re.Pattern[str]:
    pattern = rules.get("brief_rules", {}).get("fabrication_guard", {}).get(
        "numeric_pattern", r"\d+(\.\d+)?\s*(g|克|mg|毫克|kcal|千卡|大卡|千焦|kJ|%)"
    )
    return re.compile(pattern)


def check_required_sections(brief: BrandBrief, rules: dict) -> list[Issue]:
    """检查必需栏目是否填写。"""
    issues: list[Issue] = []
    required = rules.get("brief_rules", {}).get("required_sections", [])
    for section in required:
        value = getattr(brief, section, None)
        empty = value is None or value == "" or value == []
        if section == "compliance" and value is not None:
            empty = not value.prohibited_claims
        if empty:
            issues.append(Issue(SEVERITY_ERROR, "MISSING_SECTION", f"必需栏目为空: {section}"))
    return issues


def check_claim_types(brief: BrandBrief, rules: dict) -> list[Issue]:
    """检查卖点证据等级是否符合规则。"""
    issues: list[Issue] = []
    claim_rules = {r["claim"]: r for r in rules.get("brief_rules", {}).get("claim_rules", [])}
    for point in brief.selling_points:
        rule = claim_rules.get(point.claim)
        if rule is None:
            if point.claim_type == ClaimType.CONFIRMED and not point.evidence:
                issues.append(
                    Issue(
                        SEVERITY_ERROR,
                        "UNVERIFIED_CONFIRMED",
                        f"卖点「{point.claim}」无依据却标记为 confirmed",
                    )
                )
            continue
        required_type = rule.get("required_type")
        allowed_types = rule.get("allowed_types", [])
        if required_type and point.claim_type.value != required_type:
            issues.append(
                Issue(
                    SEVERITY_ERROR,
                    "CLAIM_TYPE_MISMATCH",
                    f"卖点「{point.claim}」应为 {required_type}，实际为 {point.claim_type.value}",
                )
            )
        if allowed_types and point.claim_type.value not in allowed_types:
            issues.append(
                Issue(
                    SEVERITY_ERROR,
                    "CLAIM_TYPE_NOT_ALLOWED",
                    f"卖点「{point.claim}」证据等级 {point.claim_type.value} "
                    f"不在允许范围 {allowed_types}",
                )
            )
        if point.claim_type == ClaimType.CONFIRMED and not point.evidence:
            issues.append(
                Issue(
                    SEVERITY_ERROR,
                    "CONFIRMED_WITHOUT_EVIDENCE",
                    f"卖点「{point.claim}」标记为 confirmed "
                    f"但缺少{rule.get('evidence_required', '依据')}",
                )
            )
    return issues


def check_forbidden_interpretations(brief: BrandBrief, rules: dict) -> list[Issue]:
    """检查禁止解释方向（如 0蔗糖→无糖、低负担→不长胖）。"""
    issues: list[Issue] = []
    claim_rules = rules.get("brief_rules", {}).get("claim_rules", [])
    full_text = brief.model_dump_json()
    for rule in claim_rules:
        for forbidden in rule.get("forbidden_interpretations", []):
            if forbidden and forbidden in full_text:
                # 出现在禁止清单字段中是允许的（用于记录边界），出现在其他字段是违规
                for point in brief.selling_points:
                    if point.claim != rule["claim"] and forbidden in (
                        point.claim + (point.note or "") + (point.evidence or "")
                    ):
                        issues.append(
                            Issue(
                                SEVERITY_ERROR,
                                "FORBIDDEN_INTERPRETATION",
                                f"卖点「{point.claim}」含禁止解释「{forbidden}」",
                            )
                        )
                if brief.content_goal and forbidden in brief.content_goal:
                    issues.append(
                        Issue(
                            SEVERITY_ERROR,
                            "FORBIDDEN_INTERPRETATION",
                            f"内容目标含禁止解释「{forbidden}」",
                        )
                    )
    return issues


def check_audience_interest_isolation(brief: BrandBrief, rules: dict) -> list[Issue]:
    """检查人群兴趣标签未被转换为产品功效（如 控糖→降糖）。"""
    issues: list[Issue] = []
    interest_rules = rules.get("brief_rules", {}).get("audience_interest_rules", [])
    claim_texts = [p.claim + (p.note or "") for p in brief.selling_points]
    for rule in interest_rules:
        interest = rule["interest"]
        if interest not in brief.target_audience.interests:
            continue
        for forbidden in rule.get("forbidden_product_claims", []):
            for text in claim_texts:
                if forbidden in text:
                    issues.append(
                        Issue(
                            SEVERITY_ERROR,
                            "INTEREST_AS_PRODUCT_CLAIM",
                            f"人群兴趣「{interest}」被转换为产品功效「{forbidden}」",
                        )
                    )
        # 兴趣标签本身不应成为产品卖点
        for point in brief.selling_points:
            if point.claim == interest:
                issues.append(
                    Issue(
                        SEVERITY_ERROR,
                        "INTEREST_AS_SELLING_POINT",
                        f"人群兴趣标签「{interest}」不得作为产品卖点",
                    )
                )
    return issues


def check_fabrication_guard(brief: BrandBrief, rules: dict) -> list[Issue]:
    """检查是否臆造营养/检测数据（品牌方未提供依据时）。"""
    issues: list[Issue] = []
    pattern = _numeric_pattern(rules)
    for point in brief.selling_points:
        # 有依据的 confirmed 声明允许含数值；其余一律视为臆造风险
        if point.claim_type == ClaimType.CONFIRMED and point.evidence:
            continue
        for text in (point.claim, point.note or "", point.evidence or ""):
            if pattern.search(text):
                issues.append(
                    Issue(
                        SEVERITY_ERROR,
                        "FABRICATED_NUTRITION_DATA",
                        f"卖点「{point.claim}」含未经品牌方提供的数值「{text}」",
                    )
                )
    return issues


def check_missing_info(brief: BrandBrief) -> list[Issue]:
    """检查缺失信息识别是否执行。"""
    if not brief.missing_info:
        return [Issue(SEVERITY_WARNING, "NO_MISSING_INFO", "缺失信息清单为空，需确认是否已识别")]
    return []


def validate_brief(brief: BrandBrief, rules: dict) -> ValidationResult:
    """执行全部业务规则校验。"""
    result = ValidationResult()
    result.issues.extend(check_required_sections(brief, rules))
    result.issues.extend(check_claim_types(brief, rules))
    result.issues.extend(check_forbidden_interpretations(brief, rules))
    result.issues.extend(check_audience_interest_isolation(brief, rules))
    result.issues.extend(check_fabrication_guard(brief, rules))
    result.issues.extend(check_missing_info(brief))
    return result
