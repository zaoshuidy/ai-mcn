"""品牌 Brief 业务规则校验器与验证报告。

按 config/brief_rules.yaml 对 BrandBrief 模型执行业务规则校验，
承载合规边界：卖点证据等级、禁止解释方向、人群兴趣标签与产品功效隔离、
禁止臆造营养/检测数据、缺失信息识别、年龄一致性、合规规则清单扫描。

build_validation_report 输出 0-100 分验证报告与 Stage 2 放行判断：
- stage_2_research_ready：候选达人调研是否可开始；
- stage_2_final_selection_ready：最终达人定案是否可开始。

评分约定：初始 100 分；error -20/项；blocker -15/项；
warning 按权重 high -8 / medium -4 / low -2；最低 0 分。
缺失信息默认不扣分，而是通过 blocks_next_stage 直接门控下游阶段；
仅 warn_if_missing=True 的字段缺失时生成 low 级 warning 计入评分。
出现真实性/合规硬伤（虚构数据、无证据 confirmed、禁止解释、
功效承诺等）时，总分强制封顶 79。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .brief_models import BrandBrief, ClaimType

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_BLOCKER = "blocker"

# 真实性/合规硬伤：命中即强制封顶 79 分
CAP_79_CODES = {
    "PROHIBITED_CLAIM_AS_SELLING_POINT",  # 减肥/降糖等功效承诺成为卖点
    "COMPLIANCE_RULE_VIOLATION",  # 命中合规规则禁止表述（含疾病治疗）
    "FABRICATED_NUTRITION_DATA",  # 虚构营养数值
    "CONFIRMED_WITHOUT_EVIDENCE",  # 无证据却 confirmed
    "UNVERIFIED_CONFIRMED",  # 无依据自定义卖点 confirmed
    "FORBIDDEN_INTERPRETATION",  # 0蔗糖→无糖 / 低负担→不长胖
}

WARNING_DEDUCTION = {"high": 8, "medium": 4, "low": 2}

# 最终达人定案必须补齐的商务信息
FINAL_SELECTION_REQUIRED = ["营养成分表", "0蔗糖依据", "高蛋白依据", "产品价格", "购买渠道"]


@dataclass
class Issue:
    """单条校验问题。"""

    severity: str  # error / warning / blocker
    code: str
    message: str
    weight: str = "medium"  # warning 计分权重：high / medium / low


@dataclass
class ValidationResult:
    """规则校验结果（兼容 Stage 1 首版接口）。"""

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


@dataclass
class ValidationReport:
    """0-100 分验证报告与 Stage 2 放行判断。"""

    status: str  # ready / ready_with_warnings / blocked / invalid
    score: int
    errors: list[Issue]
    warnings: list[Issue]
    blockers: list[Issue]
    passed_rules: list[str]
    stage_2_research_ready: bool
    stage_2_final_selection_ready: bool


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
    for rule in claim_rules:
        for forbidden in rule.get("forbidden_interpretations", []):
            if not forbidden:
                continue
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


def check_age_consistency(brief: BrandBrief) -> list[Issue]:
    """检查年龄上下限与原始 Brief 年龄段一致（不得擅自扩展）。"""
    audience = brief.target_audience
    match = re.search(r"(\d+)\s*[-~—]\s*(\d+)", audience.age_range or "")
    if not match or audience.age_min is None or audience.age_max is None:
        return []
    if int(match.group(1)) != audience.age_min or int(match.group(2)) != audience.age_max:
        return [
            Issue(
                SEVERITY_ERROR,
                "AGE_RANGE_MISMATCH",
                f"年龄上下限 {audience.age_min}-{audience.age_max} 与原文 "
                f"「{audience.age_range}」不一致，不得擅自扩展",
            )
        ]
    return []


def check_compliance_rules(brief: BrandBrief) -> list[Issue]:
    """用合规规则清单扫描卖点与内容目标中的禁止表述。"""
    issues: list[Issue] = []
    texts = [p.claim + (p.note or "") for p in brief.selling_points]
    if brief.content_goal:
        texts.append(brief.content_goal)
    for rule in brief.compliance_rules:
        for expression in rule.prohibited_expressions:
            if not expression:
                continue
            for text in texts:
                if expression in text:
                    issues.append(
                        Issue(
                            SEVERITY_ERROR,
                            "COMPLIANCE_RULE_VIOLATION",
                            f"命中合规规则「{rule.category}」禁止表述「{expression}」",
                        )
                    )
    return issues


def check_prohibited_selling_points(brief: BrandBrief) -> list[Issue]:
    """检查禁止承诺功效（如减肥/降糖）未被用作产品卖点。"""
    issues: list[Issue] = []
    for point in brief.selling_points:
        for prohibited in brief.compliance.prohibited_claims:
            if prohibited and prohibited in point.claim:
                issues.append(
                    Issue(
                        SEVERITY_ERROR,
                        "PROHIBITED_CLAIM_AS_SELLING_POINT",
                        f"禁止承诺功效「{prohibited}」被用作卖点「{point.claim}」",
                    )
                )
    return issues


def check_missing_info(brief: BrandBrief) -> list[Issue]:
    """检查缺失信息识别是否执行。"""
    if not brief.missing_info and not brief.missing_information:
        return [
            Issue(
                SEVERITY_WARNING,
                "NO_MISSING_INFO",
                "缺失信息清单为空，需确认是否已识别",
                weight="medium",
            )
        ]
    return []


def check_core_fields(brief: BrandBrief) -> list[Issue]:
    """核心字段缺失即阻塞 Stage 2（品牌/产品/受众/平台/内容形式）。"""
    issues: list[Issue] = []
    checks = {
        "品牌名称": brief.brand_name or (brief.brand.brand_name if brief.brand else ""),
        "产品名称": brief.product_name or (brief.brand.product_name if brief.brand else ""),
        "目标受众": brief.target_audience.age_range if brief.target_audience else "",
        "平台": (brief.brand.platform if brief.brand else "") or brief.platform,
        "内容形式": brief.brand.content_format if brief.brand else "",
    }
    for name, value in checks.items():
        if not value:
            issues.append(
                Issue(SEVERITY_BLOCKER, "CORE_FIELD_MISSING", f"核心字段缺失: {name}")
            )
    return issues


def validate_brief(brief: BrandBrief, rules: dict) -> ValidationResult:
    """执行全部业务规则校验（兼容接口）。"""
    result = ValidationResult()
    result.issues.extend(check_required_sections(brief, rules))
    result.issues.extend(check_claim_types(brief, rules))
    result.issues.extend(check_forbidden_interpretations(brief, rules))
    result.issues.extend(check_audience_interest_isolation(brief, rules))
    result.issues.extend(check_fabrication_guard(brief, rules))
    result.issues.extend(check_age_consistency(brief))
    result.issues.extend(check_compliance_rules(brief))
    result.issues.extend(check_prohibited_selling_points(brief))
    result.issues.extend(check_missing_info(brief))
    return result


RULE_CHECK_NAMES = [
    ("required_sections", "必需栏目完整性"),
    ("claim_types", "卖点证据等级"),
    ("forbidden_interpretations", "禁止解释方向"),
    ("interest_isolation", "人群兴趣与产品功效隔离"),
    ("fabrication_guard", "臆造数据拦截"),
    ("age_consistency", "年龄一致性"),
    ("compliance_rules", "合规规则清单扫描"),
    ("prohibited_selling_points", "禁止承诺功效隔离"),
]


def build_validation_report(
    brief: BrandBrief, rules: dict, result: ValidationResult | None = None
) -> ValidationReport:
    """生成 0-100 分验证报告与 Stage 2 放行判断。"""
    result = result or validate_brief(brief, rules)
    errors = result.errors
    blockers = check_core_fields(brief)
    warnings = list(result.warnings)

    for item in brief.missing_information:
        if item.warn_if_missing:
            warnings.append(
                Issue(
                    SEVERITY_WARNING,
                    "MISSING_INFO_WARNING",
                    f"待补信息（不阻塞候选调研）：{item.field}",
                    weight="low",
                )
            )

    error_codes = {i.code for i in errors}
    # 按检查函数逐项判定通过情况
    check_functions = {
        "required_sections": check_required_sections(brief, rules),
        "claim_types": check_claim_types(brief, rules),
        "forbidden_interpretations": check_forbidden_interpretations(brief, rules),
        "interest_isolation": check_audience_interest_isolation(brief, rules),
        "fabrication_guard": check_fabrication_guard(brief, rules),
        "age_consistency": check_age_consistency(brief),
        "compliance_rules": check_compliance_rules(brief),
        "prohibited_selling_points": check_prohibited_selling_points(brief),
    }
    passed_rules = [
        label
        for name, label in RULE_CHECK_NAMES
        if not any(i.severity == SEVERITY_ERROR for i in check_functions[name])
    ]

    score = 100
    score -= 20 * len(errors)
    score -= 15 * len(blockers)
    score -= sum(WARNING_DEDUCTION.get(w.weight, 4) for w in warnings)
    score = max(0, score)
    if error_codes & CAP_79_CODES:
        score = min(score, 79)

    if errors:
        status = "invalid"
    elif blockers:
        status = "blocked"
    elif warnings:
        status = "ready_with_warnings"
    else:
        status = "ready"

    research_ready = score >= 90 and not blockers and not errors
    missing_fields = {item.field for item in brief.missing_information}
    final_ready = research_ready and all(
        required not in missing_fields for required in FINAL_SELECTION_REQUIRED
    )

    return ValidationReport(
        status=status,
        score=score,
        errors=errors,
        warnings=warnings,
        blockers=blockers,
        passed_rules=passed_rules,
        stage_2_research_ready=research_ready,
        stage_2_final_selection_ready=final_ready,
    )
