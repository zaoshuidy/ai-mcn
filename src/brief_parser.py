"""品牌 Brief 解析器（规则版）。

将固定格式的自然语言 Brief（如 data/raw/qingxing_brief.md）解析为
BrandBrief 结构化模型。本解析器为确定性规则实现，不依赖真实 LLM，
保证离线可测试；后续接入 LLM 时以 prompts/brief_analyzer.md 为契约，
输出仍须通过同一 Pydantic 模型与业务规则校验。
"""

from __future__ import annotations

import re
from pathlib import Path

from .brief_models import (
    BrandBrief,
    ClaimType,
    ComplianceBoundary,
    CreatorSearchProfile,
    MissingInfoItem,
    SellingPoint,
    TargetAudience,
)

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


def _parse_interests(audience_text: str) -> list[str]:
    match = re.search(r"关注([^。]+)", audience_text)
    if not match:
        return []
    raw = match.group(1)
    raw = raw.replace("和", "、")
    return [p.strip() for p in re.split(r"[、，,]", raw) if p.strip()]


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
    prohibited: list[str] = []
    for match in re.finditer(r"不能承诺([^；;。\n]+)", text):
        prohibited.append(match.group(1).strip())
    return prohibited


def _parse_brand_name(raw_text: str) -> str:
    """提取品牌名：优先取「」内内容，否则取标签后文本。"""
    bracketed = re.search(r"「([^」]+)」", raw_text)
    if bracketed:
        return bracketed.group(1).strip()
    return _extract_after_label(raw_text, "品牌")


def parse_brief(raw_text: str, *, brief_id: str, source_file: str = "") -> BrandBrief:
    """解析固定格式自然语言 Brief 为 BrandBrief 模型。"""
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
        brand_name=brand_name,
        product_name=product_text.split("，")[0] if product_text else "",
        product_category="食品/乳制品",
        flavors=_parse_flavors(product_text),
        selling_points=selling_points,
        scenarios=_parse_scenarios(raw_text),
        target_audience=TargetAudience(
            age_range=_parse_age_range(audience_text),
            gender="女性",
            city_scope="城市",
            interests=interests,
            lifestyle=lifestyle,
        ),
        platform=_extract_after_label(raw_text, "投放平台"),
        content_goal=_extract_after_label(raw_text, "内容目标"),
        content_requirements=[
            "自然种草，不要硬广",
            "符合原博主创作风格",
            "脚本必须适合真实达人拍摄",
        ],
        compliance=compliance,
        source_file=source_file,
        structured_by="rule_based_parser",
        human_verified=False,
    )
    return brief


def attach_missing_info(brief: BrandBrief, rules: dict) -> BrandBrief:
    """按规则文件中的 missing_info_checks 生成缺失信息清单。

    规则版实现：凡品牌方未在 Brief 中提供依据的受保护数据，均记为缺失。
    """
    checks = rules.get("brief_rules", {}).get("missing_info_checks", [])
    questions = {
        "营养成分数据（蛋白质/糖/热量）": "请提供营养成分表（蛋白质g/100g、糖含量、热量）",
        "卖点依据（包装/检测报告）": "请提供0蔗糖、高蛋白卖点的包装标识或检测报告依据",
        "投放预算与达人量级": "请确认投放预算范围与计划合作达人量级",
        "投放时间与排期": "请确认投放时间窗口与发布排期要求",
        "是否提供产品样品": "是否为达人提供产品样品用于拍摄",
        "是否有限定口味主推": "原味/蓝莓/黄桃是否有主推优先级",
    }
    items = [
        MissingInfoItem(
            field=check["field"],
            question=questions.get(check["field"], f"请补充：{check['field']}"),
            impact=check["impact"],
            severity=check["severity"],
        )
        for check in checks
    ]
    brief.missing_info = items
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
    """从文件解析 Brief，并补齐缺失信息与达人搜索画像。"""
    path = Path(path)
    raw_text = path.read_text(encoding="utf-8")
    brief = parse_brief(raw_text, brief_id=brief_id, source_file=str(path))
    attach_missing_info(brief, rules)
    build_creator_search_profile(brief)
    return brief
