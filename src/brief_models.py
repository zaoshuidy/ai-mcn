"""品牌 Brief 结构化数据模型（Pydantic）。

Stage 1 核心模型。所有模型输出必须经 brief_validator 业务规则校验后
方可作为后续阶段输入；模型本身不保证业务合规。
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


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


class TargetAudience(BaseModel):
    """目标人群。"""

    age_range: str = Field(..., description="年龄段，如 22-35岁")
    gender: str = Field(..., description="性别取向描述")
    city_scope: str = Field(default="城市", description="城市范围")
    interests: list[str] = Field(default_factory=list, description="兴趣标签，如 健身/控糖")
    lifestyle: list[str] = Field(default_factory=list, description="生活方式标签")


class ComplianceBoundary(BaseModel):
    """合规边界。"""

    prohibited_claims: list[str] = Field(
        default_factory=list, description="禁止承诺的功效，如 减肥/降糖"
    )
    rules: list[str] = Field(default_factory=list, description="其他合规要求")
    audience_interest_not_product_claim: list[str] = Field(
        default_factory=list,
        description="仅可作为人群兴趣标签、不得转为产品功效的词，如 控糖",
    )


class MissingInfoItem(BaseModel):
    """缺失信息项。"""

    field: str = Field(..., description="缺失字段")
    question: str = Field(..., description="需向品牌方确认的问题")
    impact: str = Field(..., description="对后续阶段的影响")
    severity: str = Field(default="medium", description="high / medium / low")


class CreatorSearchProfile(BaseModel):
    """达人搜索画像（Stage 2 输入）。"""

    content_categories: list[str] = Field(default_factory=list, description="内容赛道")
    search_keywords: list[str] = Field(default_factory=list, description="建议搜索关键词")
    audience_match: list[str] = Field(default_factory=list, description="达人粉丝画像要求")
    excluded_creator_types: list[str] = Field(default_factory=list, description="排除的达人类型")
    style_requirements: list[str] = Field(default_factory=list, description="风格要求")


class BrandBrief(BaseModel):
    """结构化品牌 Brief 顶层模型。"""

    brief_id: str = Field(..., description="Brief 标识")
    brand_name: str = Field(..., description="品牌名")
    product_name: str = Field(..., description="产品名")
    product_category: str = Field(default="", description="产品类目")
    flavors: list[str] = Field(default_factory=list, description="口味")
    selling_points: list[SellingPoint] = Field(default_factory=list, description="卖点清单")
    scenarios: list[str] = Field(default_factory=list, description="使用场景")
    target_audience: TargetAudience
    platform: str = Field(..., description="投放平台")
    content_goal: str = Field(default="", description="内容目标")
    content_requirements: list[str] = Field(default_factory=list, description="内容要求")
    compliance: ComplianceBoundary = Field(default_factory=ComplianceBoundary)
    missing_info: list[MissingInfoItem] = Field(default_factory=list, description="缺失信息")
    creator_search_profile: CreatorSearchProfile = Field(
        default_factory=CreatorSearchProfile, description="达人搜索画像"
    )
    source_file: str = Field(default="", description="原始 Brief 文件路径")
    structured_by: str = Field(default="rule_based_parser", description="结构化方式")
    human_verified: bool = Field(default=False, description="是否经人工确认")
