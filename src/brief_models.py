"""品牌 Brief 结构化数据模型（Pydantic）。

Stage 1 核心模型。所有模型输出必须经 brief_validator 业务规则校验后
方可作为后续阶段输入；模型本身不保证业务合规。

模型分两层：
- 标准结构（新）：BrandInfo / ProductVariant / UsageScenario /
  ComplianceRule / MissingInformation 及 BrandBrief 新字段，供下游 Agent 消费；
- 兼容字段（旧）：brand_name / product_name / flavors / scenarios / platform /
  content_goal / compliance / missing_info，保证 Stage 1 首版数据与测试可读。
迁移函数 upgrade_legacy_brief 可将仅有旧字段的数据升级为完整结构。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ClaimType(str, Enum):
    """卖点声明的证据等级。

    - confirmed：有包装、检测报告等品牌方提供依据的事实声明；
    - brand_claim：品牌方主张但暂未提供依据，引用时必须保留"品牌方宣称"语境；
    - subjective_experience：主观体验类描述，不得表述为客观功效；
    - unverified：未经验证，不得扩展、不得表述为功效。
    """

    CONFIRMED = "confirmed"
    BRAND_CLAIM = "brand_claim"
    SUBJECTIVE_EXPERIENCE = "subjective_experience"
    UNVERIFIED = "unverified"


class SellingPoint(BaseModel):
    """单个卖点及其证据状态。"""

    claim: str = Field(..., description="卖点原文，如 0蔗糖、高蛋白")
    claim_type: ClaimType = Field(..., description="证据等级")
    evidence: Optional[str] = Field(default=None, description="依据来源（包装/检测报告等）")
    note: Optional[str] = Field(default=None, description="使用限制说明")
    forbidden_interpretations: list[str] = Field(
        default_factory=list, description="禁止的解释方向，如 0蔗糖→无糖"
    )


class BrandInfo(BaseModel):
    """品牌与投放基础信息（平台与内容形式拆分）。"""

    brand_name: str = Field(..., description="品牌名")
    product_name: str = Field(..., description="产品名")
    product_category: str = Field(default="", description="产品类目")
    platform: str = Field(default="", description="投放平台，如 小红书")
    content_format: str = Field(default="", description="内容形式，如 短视频")
    campaign_goal: str = Field(default="", description="投放/内容目标")


class ProductVariant(BaseModel):
    """产品口味/规格变体。"""

    name: str = Field(..., description="口味或规格名")
    confirmed: bool = Field(default=False, description="是否来自品牌方确认信息")
    source: str = Field(default="", description="信息来源，如 brand_brief")


class UsageScenario(BaseModel):
    """使用场景（结构化、可排序）。"""

    name: str = Field(..., description="场景名，如 早餐")
    priority: int = Field(..., description="优先级，越小越优先")
    natural_integration_reason: str = Field(default="", description="自然植入理由")
    shooting_feasibility: str = Field(default="", description="拍摄可行性说明")


class ComplianceRule(BaseModel):
    """单条合规规则。"""

    category: str = Field(..., description="规则类别，如 减肥功效承诺")
    prohibited_expressions: list[str] = Field(default_factory=list, description="禁止表述")
    restricted_expressions: list[str] = Field(default_factory=list, description="限制表述")
    reason: str = Field(default="", description="合规依据")
    replacement_guidance: str = Field(default="", description="替代表述建议")
    severity: str = Field(default="high", description="high / medium / low")


class MissingInformation(BaseModel):
    """缺失信息项（标准结构）。"""

    field: str = Field(..., description="缺失字段")
    importance: str = Field(default="medium", description="high / medium / low")
    reason: str = Field(default="", description="为何需要该信息")
    recommended_action: str = Field(default="", description="建议补充动作")
    blocks_next_stage: bool = Field(
        default=False, description="是否阻塞 Stage 2 最终达人定案"
    )
    warn_if_missing: bool = Field(
        default=False, description="缺失时是否生成 warning（计入评分）"
    )


class MissingInfoItem(BaseModel):
    """缺失信息项（兼容旧结构）。"""

    field: str = Field(..., description="缺失字段")
    question: str = Field(..., description="需向品牌方确认的问题")
    impact: str = Field(..., description="对后续阶段的影响")
    severity: str = Field(default="medium", description="high / medium / low")


class TargetAudience(BaseModel):
    """目标人群。"""

    age_range: str = Field(..., description="年龄段原文，如 22-35岁")
    age_min: Optional[int] = Field(default=None, description="年龄下限（须与原文一致）")
    age_max: Optional[int] = Field(default=None, description="年龄上限（须与原文一致）")
    gender: str = Field(..., description="性别取向描述")
    city_scope: str = Field(default="城市", description="城市范围")
    interests: list[str] = Field(default_factory=list, description="兴趣标签，如 健身/控糖")
    lifestyle: list[str] = Field(default_factory=list, description="生活方式标签")

    @model_validator(mode="after")
    def _check_age_bounds(self) -> "TargetAudience":
        if self.age_min is not None and self.age_min < 0:
            raise ValueError("age_min 必须大于等于 0")
        if (
            self.age_min is not None
            and self.age_max is not None
            and self.age_max <= self.age_min
        ):
            raise ValueError("age_max 必须大于 age_min")
        return self


class ComplianceBoundary(BaseModel):
    """合规边界（兼容旧结构）。"""

    prohibited_claims: list[str] = Field(
        default_factory=list, description="禁止承诺的功效，如 减肥/降糖"
    )
    rules: list[str] = Field(default_factory=list, description="其他合规要求")
    audience_interest_not_product_claim: list[str] = Field(
        default_factory=list,
        description="仅可作为人群兴趣标签、不得转为产品功效的词，如 控糖",
    )


class CreatorSearchProfile(BaseModel):
    """达人搜索画像（Stage 2 输入）。"""

    content_categories: list[str] = Field(default_factory=list, description="内容赛道")
    search_keywords: list[str] = Field(default_factory=list, description="建议搜索关键词")
    audience_match: list[str] = Field(default_factory=list, description="达人粉丝画像要求")
    excluded_creator_types: list[str] = Field(default_factory=list, description="排除的达人类型")
    style_requirements: list[str] = Field(default_factory=list, description="风格要求")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BrandBrief(BaseModel):
    """结构化品牌 Brief 顶层模型（标准结构 + 兼容字段）。"""

    brief_id: str = Field(..., description="Brief 标识")
    version: str = Field(default="2.0", description="数据契约版本")
    brand: Optional[BrandInfo] = Field(default=None, description="品牌与投放基础信息")
    product_variants: list[ProductVariant] = Field(
        default_factory=list, description="产品口味/规格变体"
    )
    selling_points: list[SellingPoint] = Field(default_factory=list, description="卖点清单")
    target_audience: TargetAudience
    usage_scenarios: list[UsageScenario] = Field(
        default_factory=list, description="结构化使用场景"
    )
    compliance_rules: list[ComplianceRule] = Field(
        default_factory=list, description="合规规则清单"
    )
    creator_search_profile: CreatorSearchProfile = Field(
        default_factory=CreatorSearchProfile, description="达人搜索画像"
    )
    missing_information: list[MissingInformation] = Field(
        default_factory=list, description="缺失信息（标准结构）"
    )
    source_text: str = Field(default="", description="原始 Brief 全文")
    source_type: str = Field(default="brand_brief_markdown", description="来源类型")
    source_file: str = Field(default="", description="原始 Brief 文件相对路径")
    created_at: str = Field(default_factory=_utc_now_iso, description="结构化时间")
    validation_status: str = Field(
        default="pending", description="ready / ready_with_warnings / blocked / invalid / pending"
    )
    human_verified: bool = Field(default=False, description="是否经人工确认")

    # ---- 兼容旧字段（保留以支持 Stage 1 首版数据与测试） ----
    brand_name: str = Field(default="", description="[兼容] 品牌名")
    product_name: str = Field(default="", description="[兼容] 产品名")
    product_category: str = Field(default="", description="[兼容] 产品类目")
    flavors: list[str] = Field(default_factory=list, description="[兼容] 口味")
    scenarios: list[str] = Field(default_factory=list, description="[兼容] 使用场景")
    platform: str = Field(default="", description="[兼容] 投放平台原文")
    content_goal: str = Field(default="", description="[兼容] 内容目标")
    content_requirements: list[str] = Field(default_factory=list, description="[兼容] 内容要求")
    compliance: ComplianceBoundary = Field(
        default_factory=ComplianceBoundary, description="[兼容] 合规边界"
    )
    missing_info: list[MissingInfoItem] = Field(
        default_factory=list, description="[兼容] 缺失信息"
    )
    structured_by: str = Field(default="rule_based_parser", description="结构化方式")


def split_platform_text(text: str) -> tuple[str, str]:
    """将"小红书短视频"类原文拆分为（平台， 内容形式）。"""
    for fmt in ("短视频", "图文", "直播", "长视频"):
        if text.endswith(fmt) and len(text) > len(fmt):
            return text[: -len(fmt)], fmt
    return text, ""


def upgrade_legacy_brief(brief: BrandBrief) -> BrandBrief:
    """将仅有兼容旧字段的 BrandBrief 升级为完整标准结构（原地补齐并返回）。"""
    if brief.brand is None:
        platform, content_format = split_platform_text(brief.platform)
        brief.brand = BrandInfo(
            brand_name=brief.brand_name,
            product_name=brief.product_name,
            product_category=brief.product_category,
            platform=platform,
            content_format=content_format,
            campaign_goal=brief.content_goal,
        )
    if not brief.product_variants and brief.flavors:
        brief.product_variants = [
            ProductVariant(name=f, confirmed=True, source="brand_brief") for f in brief.flavors
        ]
    if not brief.usage_scenarios and brief.scenarios:
        brief.usage_scenarios = [
            UsageScenario(name=name, priority=index + 1)
            for index, name in enumerate(brief.scenarios)
        ]
    if not brief.missing_information and brief.missing_info:
        brief.missing_information = [
            MissingInformation(
                field=item.field,
                importance=item.severity,
                reason=item.impact,
                recommended_action=item.question,
                blocks_next_stage=False,
            )
            for item in brief.missing_info
        ]
    return brief
