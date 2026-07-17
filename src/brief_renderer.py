"""品牌 Brief 人工可读摘要渲染器。

将 BrandBrief 模型渲染为 Markdown 摘要，供项目总控与人工执行者审阅。
"""

from __future__ import annotations

from .brief_models import BrandBrief, ClaimType
from .brief_validator import ValidationReport, ValidationResult

CLAIM_TYPE_LABELS = {
    ClaimType.CONFIRMED: "已确认（有依据）",
    ClaimType.BRAND_CLAIM: "品牌方宣称（待依据）",
    ClaimType.SUBJECTIVE_EXPERIENCE: "主观体验",
    ClaimType.UNVERIFIED: "未经验证",
}

SEVERITY_LABELS = {"high": "高", "medium": "中", "low": "低"}


def render_claim_type_label(claim_type: ClaimType) -> str:
    """返回证据等级的中文标签。"""
    return CLAIM_TYPE_LABELS[claim_type]


def render_summary(
    brief: BrandBrief,
    validation: ValidationResult | None = None,
    report: ValidationReport | None = None,
) -> str:
    """渲染人工可读摘要（Markdown）。

    validation 为业务规则校验结果（兼容接口）；
    report 为 0-100 分验证报告（含 Stage 2 放行判断）。
    """
    lines: list[str] = []
    lines.append(f"# 品牌 Brief 结构化摘要：{brief.brand_name}")
    lines.append("")
    lines.append(f"- Brief ID：{brief.brief_id}")
    lines.append(f"- 来源文件：{brief.source_file}")
    lines.append(f"- 结构化方式：{brief.structured_by}")
    lines.append(f"- 人工确认：{'是' if brief.human_verified else '否（待人工执行者确认）'}")
    lines.append("")

    lines.append("## 1. 品牌与产品")
    lines.append("")
    lines.append(f"- 品牌：{brief.brand_name}")
    lines.append(f"- 产品：{brief.product_name}")
    lines.append(f"- 类目：{brief.product_category}")
    lines.append(f"- 口味：{'、'.join(brief.flavors)}")
    lines.append("")

    lines.append("## 2. 卖点与证据状态")
    lines.append("")
    lines.append("| 卖点 | 证据等级 | 依据 | 禁止解释方向 |")
    lines.append("| -- | -- | -- | -- |")
    for point in brief.selling_points:
        forbidden = "、".join(point.forbidden_interpretations) or "—"
        evidence = point.evidence or "未提供"
        label = render_claim_type_label(point.claim_type)
        lines.append(f"| {point.claim} | {label} | {evidence} | {forbidden} |")
    lines.append("")

    lines.append("## 3. 目标人群")
    lines.append("")
    audience = brief.target_audience
    lines.append(f"- 年龄：{audience.age_range}")
    lines.append(f"- 性别：{audience.gender}")
    lines.append(f"- 范围：{audience.city_scope}")
    lines.append(f"- 兴趣标签：{'、'.join(audience.interests)}")
    lines.append(f"- 生活方式：{'、'.join(audience.lifestyle) or '—'}")
    lines.append("")

    lines.append("## 4. 使用场景与内容目标")
    lines.append("")
    lines.append(f"- 使用场景：{'、'.join(brief.scenarios)}")
    lines.append(f"- 投放平台：{brief.platform}")
    if brief.brand is not None:
        lines.append(f"- 平台（标准拆分）：{brief.brand.platform}")
        lines.append(f"- 内容形式（标准拆分）：{brief.brand.content_format}")
    lines.append(f"- 内容目标：{brief.content_goal}")
    lines.append(f"- 内容要求：{'；'.join(brief.content_requirements)}")
    lines.append("")

    lines.append("## 5. 合规边界")
    lines.append("")
    lines.append(f"- 禁止承诺：{'、'.join(brief.compliance.prohibited_claims)}")
    if brief.compliance.audience_interest_not_product_claim:
        tags = "、".join(brief.compliance.audience_interest_not_product_claim)
        lines.append(f"- 仅为人群兴趣标签（不得转为产品功效）：{tags}")
    for rule in brief.compliance.rules:
        if rule:
            lines.append(f"- {rule}")
    lines.append("")

    lines.append("## 6. 缺失信息清单（需品牌方补充）")
    lines.append("")
    lines.append("| 缺失项 | 优先级 | 需确认问题 | 影响 |")
    lines.append("| -- | -- | -- | -- |")
    for item in brief.missing_info:
        lines.append(
            f"| {item.field} | {SEVERITY_LABELS.get(item.severity, item.severity)} "
            f"| {item.question} | {item.impact} |"
        )
    lines.append("")

    lines.append("## 7. 达人搜索画像（Stage 2 输入）")
    lines.append("")
    profile = brief.creator_search_profile
    lines.append(f"- 内容赛道：{'、'.join(profile.content_categories)}")
    lines.append(f"- 建议搜索关键词：{'、'.join(profile.search_keywords)}")
    lines.append(f"- 达人粉丝画像要求：{'；'.join(profile.audience_match)}")
    lines.append(f"- 排除达人类型：{'、'.join(profile.excluded_creator_types)}")
    lines.append(f"- 风格要求：{'、'.join(profile.style_requirements)}")
    lines.append("")

    if validation is not None:
        lines.append("## 8. 业务规则校验结果")
        lines.append("")
        status = "通过（无 error）" if validation.is_valid else "未通过"
        lines.append(f"- 结论：{status}")
        lines.append(f"- error：{len(validation.errors)}；warning：{len(validation.warnings)}")
        for issue in validation.issues:
            lines.append(f"- [{issue.severity}] {issue.code}: {issue.message}")
        lines.append("")

    if report is not None:
        lines.append("## 9. 验证分数与 Stage 2 放行判断")
        lines.append("")
        lines.append(f"- 当前验证分数：{report.score} 分")
        lines.append(f"- 验证状态：{report.status}")
        research_text = "是" if report.stage_2_research_ready else "否"
        final_text = "是" if report.stage_2_final_selection_ready else "否"
        lines.append(f"- Stage 2 候选调研是否可开始：{research_text}")
        lines.append(f"- Stage 2 最终达人定案是否可开始：{final_text}")
        if report.blockers:
            lines.append("- 核心阻塞项：")
            for issue in report.blockers:
                lines.append(f"  - {issue.message}")
        else:
            lines.append("- 核心阻塞项：无")
        blocking_missing = [m.field for m in brief.missing_information if m.blocks_next_stage]
        if blocking_missing:
            lines.append(f"- 阻塞最终定案的待补信息：{'、'.join(blocking_missing)}")
        high_missing = [m.field for m in brief.missing_information if m.importance == "high"]
        if high_missing:
            lines.append(f"- 高优先级待补信息：{'、'.join(high_missing)}")
        lines.append(f"- 通过的规则：{'、'.join(report.passed_rules)}")
        lines.append("")

    return "\n".join(lines)
