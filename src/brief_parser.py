"""品牌 Brief 解析器（规则版）。

将固定格式的自然语言 Brief（如 data/raw/qingxing_brief.md）解析为
BrandBrief 结构化模型（标准结构 + 兼容旧字段）。

本解析器为确定性规则实现，不依赖真实 LLM，保证离线可测试；
后续接入 LLM 时以 prompts/brief_analyzer.md 为契约，输出仍须通过
同一 Pydantic 模型与业务规则校验。
"""

from __future__ import annotations

import re
from pathlib import Path

from .brief_models import (
    BrandBrief,
    BrandInfo,
    ClaimType,
    ComplianceBoundary,
    ComplianceRule,
    CreatorSearchProfile,
    MissingInfoItem,
    MissingInformation,
    ProductVariant,
    SellingPoint,
    TargetAudience,
    UsageScenario,
    split_platform_text,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# 卖点证据等级默认映射（与 config/brief_rules.yaml 的 claim_rules 保持一致；
# 解析器只负责"初步归类"，最终由 validator 按规则文件复核）。
DEFAULT_CLAIM_TYPE_MAP: dict[str, ClaimType] = {
    "0蔗糖": ClaimType.BRAND_CLAIM,
    "高蛋白": ClaimType.BRAND_CLAIM,
    "饱腹感": ClaimType.SUBJECTIVE_EXPERIENCE,
    "低负担": ClaimType.UNVERIFIED,
}

DEFAULT_FORBIDDEN_INTERPRETATIONS: dict[str, list[str]] = {
    "0蔗糖": ["无糖"],
    "饱腹感": ["减重", "抑制食欲"],
    "低负担": ["不长胖", "零负担", "减肥"],
}

# 仅可作为人群兴趣标签、不得转为产品功效的词
INTEREST_ONLY_TAGS = ["控糖"]

# 场景优先级与植入/拍摄说明（策划推理，非产品功效声明）
SCENARIO_PROFILES: dict[str, tuple[int, str, str]] = {
    "早餐": (
        1,
        "Brief 将早餐列为核心使用场景，希腊酸奶作为早餐选择符合目标人群认知",
        "居家厨房或办公室即可拍摄，道具简单",
    ),
    "运动后": (
        2,
        "目标人群含健身标签，运动后加餐场景与产品形态契合（功效表述以品牌方依据为准）",
        "健身房或居家场景，需提前确认场地拍摄许可",
    ),
    "下午茶": (
        3,
        "办公室下午茶场景贴合上班族人群，多口味利于内容呈现",
        "办公桌场景，布置简单",
    ),
}

# 食品类商单默认合规规则清单（与任务书一致，可由 brief 内容扩展）
DEFAULT_COMPLIANCE_RULES: list[ComplianceRule] = [
    ComplianceRule(
        category="减肥功效承诺",
        prohibited_expressions=["减肥", "瘦身", "减重", "燃脂"],
        restricted_expressions=[],
        reason="食品广告不得宣传减肥功效（广告法及食品类目规范）",
        replacement_guidance="改为口感、场景或生活方式描述",
        severity="high",
    ),
    ComplianceRule(
        category="降糖或血糖功效",
        prohibited_expressions=["降糖", "降血糖", "控制血糖", "调节血糖"],
        restricted_expressions=["控糖"],
        reason="普通食品不得宣称血糖相关功效；控糖仅可作为人群兴趣标签",
        replacement_guidance="控糖仅出现在人群画像，不进入产品卖点",
        severity="high",
    ),
    ComplianceRule(
        category="疾病治疗",
        prohibited_expressions=["治疗", "治愈", "预防疾病", "药用", "疗效"],
        restricted_expressions=[],
        reason="食品广告不得涉及疾病治疗功能",
        replacement_guidance="删除疾病相关表述",
        severity="high",
    ),
    ComplianceRule(
        category="绝对化用语",
        prohibited_expressions=["最健康", "第一品牌", "100%", "完全无负担", "绝对"],
        restricted_expressions=["最", "第一"],
        reason="广告法禁止绝对化用语",
        replacement_guidance="改为可验证的具体描述",
        severity="medium",
    ),
    ComplianceRule(
        category="未证实营养数据",
        prohibited_expressions=[],
        restricted_expressions=["蛋白质克数", "糖含量", "热量数值"],
        reason="无品牌方依据时不得标注任何营养数值",
        replacement_guidance="数值仅可来自品牌方营养成分表或检测报告",
        severity="high",
    ),
    ComplianceRule(
        category="夸大主观体验",
        prohibited_expressions=["吃了必饱", "一整天不饿"],
        restricted_expressions=["饱腹感", "低负担"],
        reason="主观体验不得表述为客观功效",
        replacement_guidance="使用个人体验语境，如「我觉得」「对我来说」",
        severity="medium",
    ),
    ComplianceRule(
        category="不适当竞品贬低",
        prohibited_expressions=["比其他品牌好", "碾压", "吊打", "完胜"],
        restricted_expressions=[],
        reason="广告不得贬低其他生产经营者的商品",
        replacement_guidance="只描述本产品特点，不做竞品对比",
        severity="medium",
    ),
]


def _extract_after_label(text: str, label: str) -> str:
    """提取"标签：内容。"中标签后的内容（到句号或换行截止）。"""
    match = re.search(rf"{re.escape(label)}[：:]\s*([^\n。]+)", text)
    return match.group(1).strip() if match else ""


def _split_items(text: str) -> list[str]:
    """按中文/英文顿号、逗号、和 分隔列表项。"""
    parts = re.split(r"[、，,和]", text)
    return [p.strip() for p in parts if p.strip()]


def _parse_flavors(product_text: str) -> list[str]:
    match = re.search(r"口味包含([^。]+)", product_text)
    return _split_items(match.group(1)) if match else []


def _parse_scenarios(text: str) -> list[str]:
    match = re.search(r"适合([^。]+)", text)
    return _split_items(match.group(1)) if match else []


def _parse_age_range(text: str) -> str:
    match = re.search(r"(\d+\s*[-~—]\s*\d+\s*岁)", text)
    return match.group(1).replace(" ", "") if match else ""


def _parse_age_bounds(age_range: str) -> tuple[int | None, int | None]:
    match = re.search(r"(\d+)\s*[-~—]\s*(\d+)", age_range)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _parse_interests(audience_text: str) -> list[str]:
    match = re.search(r"关注([^。]+)", audience_text)
    if not match:
        return []
    raw = match.group(1).replace("和", "、")
    return [p.strip() for p in re.split(r"[、，,]", raw) if p.strip()]


def _parse_brand_name(raw_text: str) -> str:
    """提取品牌名：优先取「」内内容，否则取标签后文本。"""
    bracketed = re.search(r"「([^」]+)」", raw_text)
    if bracketed:
        return bracketed.group(1).strip()
    return _extract_after_label(raw_text, "品牌")


def _relative_source_file(path: Path) -> str:
    """返回相对仓库根目录的 POSIX 风格路径；不在仓库内则仅返回文件名。"""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_selling_points(text: str) -> list[SellingPoint]:
    """从卖点描述文本解析卖点清单并初步归类证据等级。"""
    match = re.search(r"主要卖点[：:]\s*([^\n]+)", text)
    if not match:
        return []
    points_text = match.group(1)
    points: list[SellingPoint] = []
    for raw_point in _split_items(points_text.split("，适合")[0]):
        point = raw_point.strip("。 ")
        if not point:
            continue
        claim_type = DEFAULT_CLAIM_TYPE_MAP.get(point, ClaimType.UNVERIFIED)
        points.append(
            SellingPoint(
                claim=point,
                claim_type=claim_type,
                evidence=None,
                forbidden_interpretations=DEFAULT_FORBIDDEN_INTERPRETATIONS.get(point, []),
            )
        )
    return points


def parse_prohibited_claims(text: str) -> list[str]:
    """从合规要求段落提取禁止承诺项。"""
    return [m.group(1).strip() for m in re.finditer(r"不能承诺([^；;。\n]+)", text)]


def _build_usage_scenarios(scenario_names: list[str]) -> list[UsageScenario]:
    """将场景名列表升级为结构化 UsageScenario（含优先级与可行性）。"""
    scenarios: list[UsageScenario] = []
    for index, name in enumerate(scenario_names):
        priority, reason, feasibility = SCENARIO_PROFILES.get(
            name, (index + 1, "", "")
        )
        scenarios.append(
            UsageScenario(
                name=name,
                priority=priority,
                natural_integration_reason=reason,
                shooting_feasibility=feasibility,
            )
        )
    return scenarios


def parse_brief(raw_text: str, *, brief_id: str, source_file: str = "") -> BrandBrief:
    """解析固定格式自然语言 Brief 为 BrandBrief 模型（标准结构 + 兼容字段）。"""
    brand_name = _parse_brand_name(raw_text)
    product_text = _extract_after_label(raw_text, "产品")
    audience_text = _extract_after_label(raw_text, "目标人群")
    selling_points = parse_selling_points(raw_text)

    # 产品名中嵌入的声明型卖点（如 0蔗糖）也需纳入卖点清单并归类
    existing_claims = {p.claim for p in selling_points}
    for claim, claim_type in DEFAULT_CLAIM_TYPE_MAP.items():
        if claim not in existing_claims and claim in product_text:
            selling_points.append(
                SellingPoint(
                    claim=claim,
                    claim_type=claim_type,
                    evidence=None,
                    forbidden_interpretations=DEFAULT_FORBIDDEN_INTERPRETATIONS.get(claim, []),
                    note="提取自产品名称，依据待品牌方提供",
                )
            )

    interests = _parse_interests(audience_text)
    lifestyle = [t for t in interests if "生活" in t or "效率" in t]
    age_range = _parse_age_range(audience_text)
    age_min, age_max = _parse_age_bounds(age_range)

    platform_text = _extract_after_label(raw_text, "投放平台")
    platform, content_format = split_platform_text(platform_text)
    content_goal = _extract_after_label(raw_text, "内容目标")
    product_name = product_text.split("，")[0] if product_text else ""
    flavors = _parse_flavors(product_text)
    scenario_names = _parse_scenarios(raw_text)

    compliance = ComplianceBoundary(
        prohibited_claims=parse_prohibited_claims(raw_text),
        rules=[
            line.strip("- ；;。")
            for line in raw_text.splitlines()
            if line.strip().startswith("-")
        ],
        audience_interest_not_product_claim=[t for t in interests if t in INTEREST_ONLY_TAGS],
    )

    brief = BrandBrief(
        brief_id=brief_id,
        version="2.0",
        brand=BrandInfo(
            brand_name=brand_name,
            product_name=product_name,
            product_category="食品/乳制品",
            platform=platform,
            content_format=content_format,
            campaign_goal=content_goal,
        ),
        product_variants=[
            ProductVariant(name=f, confirmed=True, source="brand_brief") for f in flavors
        ],
        selling_points=selling_points,
        target_audience=TargetAudience(
            age_range=age_range,
            age_min=age_min,
            age_max=age_max,
            gender="女性",
            city_scope="城市",
            interests=interests,
            lifestyle=lifestyle,
        ),
        usage_scenarios=_build_usage_scenarios(scenario_names),
        compliance_rules=list(DEFAULT_COMPLIANCE_RULES),
        source_text=raw_text,
        source_type="brand_brief_markdown",
        source_file=source_file,
        # ---- 兼容旧字段 ----
        brand_name=brand_name,
        product_name=product_name,
        product_category="食品/乳制品",
        flavors=flavors,
        scenarios=scenario_names,
        platform=platform_text,
        content_goal=content_goal,
        content_requirements=[
            "自然种草，不要硬广",
            "符合原博主创作风格",
            "脚本必须适合真实达人拍摄",
        ],
        compliance=compliance,
        structured_by="rule_based_parser",
        human_verified=False,
    )
    return brief


def attach_missing_info(brief: BrandBrief, rules: dict) -> BrandBrief:
    """按规则文件中的 missing_info_checks 生成缺失信息清单。

    同时填充标准结构 missing_information 与兼容结构 missing_info。
    规则版实现：凡品牌方未在 Brief 中提供的信息项，均记为缺失。
    """
    checks = rules.get("brief_rules", {}).get("missing_info_checks", [])
    standard_items = [
        MissingInformation(
            field=check["field"],
            importance=check.get("importance", "medium"),
            reason=check.get("reason", ""),
            recommended_action=check.get("recommended_action", ""),
            blocks_next_stage=check.get("blocks_next_stage", False),
            warn_if_missing=check.get("warn_if_missing", False),
        )
        for check in checks
    ]
    brief.missing_information = standard_items
    brief.missing_info = [
        MissingInfoItem(
            field=item.field,
            question=item.recommended_action or f"请补充：{item.field}",
            impact=item.reason,
            severity=item.importance if item.importance in {"high", "medium", "low"} else "medium",
        )
        for item in standard_items
    ]
    return brief


def build_creator_search_profile(brief: BrandBrief) -> CreatorSearchProfile:
    """根据结构化 Brief 生成达人搜索画像（Stage 2 输入）。"""
    profile = CreatorSearchProfile(
        content_categories=["健身饮食", "轻食", "控糖饮食", "上班族生活", "早餐"],
        search_keywords=[
            "上班族早餐",
            "健身女孩饮食",
            "运动后加餐",
            "办公室下午茶",
            "控糖饮食记录",
            "轻食一日三餐",
            "高蛋白早餐",
            "打工人冰箱常备",
        ],
        audience_match=["22-35岁城市女性为主", "关注健身/控糖/轻食", "粉丝画像与目标人群重合"],
        excluded_creator_types=[
            "品牌官方号",
            "纯店铺号",
            "搬运号",
            "长期停更账号",
            "硬广占比极高账号",
            "主要内容为医疗或疾病建议的账号",
        ],
        style_requirements=["自然种草风格", "非硬广", "适合真实达人日常拍摄"],
    )
    brief.creator_search_profile = profile
    return brief


def parse_brief_file(path: str | Path, rules: dict, *, brief_id: str) -> BrandBrief:
    """从文件解析 Brief，并补齐缺失信息与达人搜索画像。

    source_file 一律记录为相对仓库根目录的 POSIX 路径，禁止绝对路径。
    """
    path = Path(path)
    raw_text = path.read_text(encoding="utf-8")
    brief = parse_brief(raw_text, brief_id=brief_id, source_file=_relative_source_file(path))
    attach_missing_info(brief, rules)
    build_creator_search_profile(brief)
    return brief
