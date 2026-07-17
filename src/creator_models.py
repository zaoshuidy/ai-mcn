"""达人采集数据模型（Stage 2 统一 Schema）。

真实性分层原则：
- 页面观察值（page_observed）：来自达人主页/笔记页面的直接观察，记录采集时间；
- 工具返回值（tool_returned）：来自采集工具的原始返回；
- AI 推测值（ai_inferred）：必须带 evidence 与 confidence，不得写成事实；
- 人工确认值（human_verified）：人工执行者核验后的结论；
- unknown：无法确认，使用 null，不得编造。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class DataSourceType(str, Enum):
    """字段来源类型。"""

    PAGE_OBSERVED = "page_observed"
    TOOL_RETURNED = "tool_returned"
    AI_INFERRED = "ai_inferred"
    HUMAN_VERIFIED = "human_verified"
    UNKNOWN = "unknown"


class SelectionStatus(str, Enum):
    """候选状态。POC 阶段只允许 poc_candidate，不代表最终名单。"""

    POC_CANDIDATE = "poc_candidate"
    RESEARCH_CANDIDATE = "research_candidate"
    FINAL_CANDIDATE = "final_candidate"
    EXCLUDED = "excluded"


class CreatorIdentity(BaseModel):
    """达人身份与主页信息。敏感或不可靠字段允许为空。"""

    creator_id: str = Field(..., description="平台用户 ID（不得虚构）")
    nickname: str = Field(..., description="昵称")
    profile_url: str = Field(..., description="主页链接（不得补全不存在的链接）")
    platform: str = Field(default="小红书")
    bio: Optional[str] = Field(default=None, description="简介")
    followers: Optional[int] = Field(default=None, ge=0, description="粉丝数（页面观察值）")
    likes_and_collects: Optional[int] = Field(
        default=None, ge=0, description="获赞与收藏数（页面观察值）"
    )
    location: Optional[str] = Field(default=None, description="所在地（不可靠，允许为空）")
    verified_type: Optional[str] = Field(default=None, description="认证类型")
    followers_source: DataSourceType = Field(
        default=DataSourceType.UNKNOWN, description="粉丝数字段来源"
    )
    followers_observed_at: Optional[str] = Field(default=None, description="粉丝数采集时间")


class CreatorPost(BaseModel):
    """达人单条笔记。"""

    post_id: str = Field(..., description="笔记 ID")
    title: str = Field(default="", description="标题")
    url: str = Field(..., description="笔记链接")
    publish_time: Optional[str] = Field(default=None, description="发布时间")
    content_type: str = Field(default="video", description="video / image_text")
    text_excerpt: Optional[str] = Field(default=None, description="正文摘要")
    likes: Optional[int] = Field(default=None, ge=0)
    collects: Optional[int] = Field(default=None, ge=0)
    comments: Optional[int] = Field(default=None, ge=0)
    keywords: list[str] = Field(default_factory=list, description="命中关键词")
    source_query: str = Field(default="", description="来源搜索词")
    evidence_screenshot: Optional[str] = Field(
        default=None, description="证据截图相对路径（screenshots/ 下）"
    )
    metrics_observed_at: Optional[str] = Field(default=None, description="互动数据采集时间")


class AudienceInference(BaseModel):
    """受众画像推测。全部字段为 AI 推测，必须带证据与置信度。"""

    gender_tendency: Optional[str] = Field(default=None, description="性别倾向（推测）")
    age_tendency: Optional[str] = Field(default=None, description="年龄倾向（推测）")
    interests: list[str] = Field(default_factory=list, description="兴趣标签（推测）")
    evidence: list[str] = Field(..., description="推测依据（笔记标题/简介等）")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度 0-1")
    source_type: DataSourceType = Field(default=DataSourceType.AI_INFERRED)

    @model_validator(mode="after")
    def _check_inference_integrity(self) -> "AudienceInference":
        if self.source_type != DataSourceType.AI_INFERRED:
            raise ValueError("受众画像必须标记为 ai_inferred，不得写成平台官方数据")
        has_claim = bool(self.gender_tendency or self.age_tendency or self.interests)
        if has_claim and not self.evidence:
            raise ValueError("存在推测结论时 evidence 不得为空")
        if not has_claim and self.confidence > 0:
            raise ValueError("无推测结论时 confidence 必须为 0")
        return self


class CreatorCandidate(BaseModel):
    """候选达人（POC/调研阶段）。"""

    creator: CreatorIdentity
    content_categories: list[str] = Field(default_factory=list, description="内容赛道")
    audience_inference: Optional[AudienceInference] = Field(default=None)
    representative_posts: list[CreatorPost] = Field(default_factory=list)
    commercial_signals: list[str] = Field(
        default_factory=list, description="商单信号（如历史食品合作），须注明依据"
    )
    risk_signals: list[str] = Field(default_factory=list, description="风险信号")
    collection_source: str = Field(..., description="采集方式，如 manual_search / tool_name")
    collected_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="采集时间",
    )
    data_freshness: str = Field(default="unknown", description="数据时效说明")
    human_verified: bool = Field(default=False, description="是否经人工核验")
    selection_status: SelectionStatus = Field(default=SelectionStatus.POC_CANDIDATE)

    @model_validator(mode="after")
    def _check_poc_constraints(self) -> "CreatorCandidate":
        if self.selection_status == SelectionStatus.POC_CANDIDATE and self.human_verified:
            raise ValueError("POC 候选不得标记为 human_verified，需先经人工审核升级状态")
        return self
