"""agent/ 各节点的输入输出契约（Pydantic v2）。

契约用途：
1. 文档化每个节点读写的 state 字段（与 ``agent/nodes/`` 各模块 docstring 一一对应）；
2. 节点实现内部可用 ``model_validate`` 对输入做自校验；
3. 测试与演示可用模型构造合法的假数据。

本模块只定义契约，不执行任何 LLM 调用、网络或文件 IO。
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class BriefAnalysis(BaseModel):
    """brief_analyzer 输出：品牌 Brief 的编排视图。

    仅保留下游节点需要的字段，不复制 Brief 全文；合规细则以
    ``agent/policies/`` 下的策略文件为准。
    """

    brief_id: str = Field(default="", description="Brief 标识")
    brand_name: str = Field(default="", description="品牌名")
    product_name: str = Field(default="", description="产品名")
    allowed_claims: list[str] = Field(default_factory=list, description="允许使用的卖点")
    claim_types: dict[str, str] = Field(
        default_factory=dict, description="卖点 -> 证据等级（confirmed/brand_claim/...）"
    )
    scenarios: list[str] = Field(default_factory=list, description="使用场景（按优先级）")
    target_audience: dict[str, Any] = Field(default_factory=dict, description="目标人群")
    content_requirements: list[str] = Field(default_factory=list, description="内容要求")
    compliance_categories: list[str] = Field(default_factory=list, description="合规类目")
    blockers: list[str] = Field(
        default_factory=list, description="阻塞级缺失信息（blocks_next_stage=true）"
    )
    source: str = Field(default="", description="数据来源（state 注入或文件路径）")


class StyleProfile(BaseModel):
    """creator_style_distiller 输出：达人风格画像。

    演示实现基于 Stage 3 Top3 真实视频时间线统计；正式版由风格 Skill 产出。
    """

    reference_videos: list[dict[str, Any]] = Field(
        default_factory=list, description="参考视频清单（note_id/title/duration/format）"
    )
    dominant_format: str = Field(default="", description="主导形式（voiceover/subtitle）")
    duration_range_s: list[float] = Field(default_factory=list, description="时长范围 [min, max]")
    avg_duration_s: Optional[float] = Field(default=None, description="平均时长（秒）")
    hook_patterns: list[str] = Field(default_factory=list, description="开头钩子模式摘要")
    source: str = Field(default="", description="数据来源")
    note: str = Field(default="", description="画像说明与局限")


class ScriptSegment(BaseModel):
    """脚本的一个段落（口播或字幕单元）。"""

    index: int = Field(..., description="段落序号（从 0 开始）")
    purpose: str = Field(default="", description="段落功能，如 hook/痛点/产品露出/cta")
    text: str = Field(default="", description="口播或字幕文本")
    duration_s: Optional[float] = Field(default=None, description="预估时长（秒）")
    on_screen_text: str = Field(default="", description="屏幕字幕（与口播分离时）")


class ScriptDraft(BaseModel):
    """script_generator 输出：脚本草稿。

    ``text`` 为完整口播/字幕拼接文本，是 fact_regression 与 compliance_reviewer
    规则演示实现的扫描对象；``claims_used`` 声明草稿用到的卖点，供事实回检核对。
    """

    version: int = Field(default=1, description="草稿版本号，每次回退重修 +1")
    title: str = Field(default="", description="笔记标题候选")
    hook: str = Field(default="", description="开头钩子")
    segments: list[ScriptSegment] = Field(default_factory=list, description="分段脚本")
    cta: str = Field(default="", description="结尾引导")
    text: str = Field(default="", description="完整文本（segments 拼接或独立维护）")
    claims_used: list[str] = Field(default_factory=list, description="使用的卖点清单")
    target_duration_s: float = Field(default=60.0, description="目标视频时长（秒）")


class HumanizedScript(BaseModel):
    """humanizer 输出：人味化处理后的脚本。"""

    text: str = Field(default="", description="处理后的完整文本")
    changes: list[str] = Field(default_factory=list, description="相对草稿的修改点说明")
    based_on_version: int = Field(default=1, description="基于的脚本草稿版本号")


class CheckViolation(BaseModel):
    """质检违规项（事实回检与合规审查共用）。"""

    code: str = Field(..., description="违规代码，如 banned_expression")
    category: str = Field(default="", description="所属类目（对应策略文件 category）")
    expression: str = Field(default="", description="命中的表达")
    severity: str = Field(default="", description="严重度（high/medium/low）")
    detail: str = Field(default="", description="违规说明")
    suggestion: str = Field(default="", description="修改建议")


class FactCheckResult(BaseModel):
    """fact_regression 输出：事实回检结果。

    passed=False 时图路由回退 script_generator；violations 必须逐条可在
    状态 errors 中追溯。
    """

    passed: bool = Field(..., description="是否通过")
    violations: list[CheckViolation] = Field(default_factory=list, description="违规项")
    checker: str = Field(default="", description="检查器标识（如 rule_based_demo）")
    checked_text_source: str = Field(default="", description="被检文本来源（humanized/script）")


class ComplianceResult(BaseModel):
    """compliance_reviewer 输出：合规审查结果。

    violations 为阻断项（passed=False 时回退 script_generator）；warnings 为
    受限提示项，不阻断流程但应随交付物一并呈交人工。
    """

    passed: bool = Field(..., description="是否通过")
    violations: list[CheckViolation] = Field(default_factory=list, description="阻断项")
    warnings: list[CheckViolation] = Field(default_factory=list, description="提示项")
    checker: str = Field(default="", description="检查器标识")
    policy_version: str = Field(default="", description="使用的策略文件版本")


class StoryboardShot(BaseModel):
    """分镜表中的一个镜头。"""

    index: int = Field(..., description="镜头序号（从 0 开始）")
    start_s: float = Field(..., description="开始时间（秒）")
    end_s: float = Field(..., description="结束时间（秒）")
    visual: str = Field(default="", description="画面描述")
    subtitle: str = Field(default="", description="屏幕字幕")
    voiceover: str = Field(default="", description="口播内容")
    props: list[str] = Field(default_factory=list, description="道具/场景")


class Storyboard(BaseModel):
    """storyboard_generator 输出：分镜表。

    图路由用 ``total_duration_s``（缺省时按 shots 的 end_s-start_s 求和）与
    ScriptDraft.target_duration_s 做一致性校验，不一致则回退本节点。
    """

    shots: list[StoryboardShot] = Field(default_factory=list, description="镜头列表")
    total_duration_s: Optional[float] = Field(default=None, description="分镜总时长（秒）")
    note: str = Field(default="", description="拍摄可行性说明")


class HumanDecision(BaseModel):
    """human_approval 输入：人工审批决定。

    approved=False 时 retry_node 必须是
    script_generator / humanizer / storyboard_generator 之一（见
    agent/policies/approval_rules.yaml），否则流程以无效路由中止。
    """

    approved: bool = Field(..., description="是否通过")
    retry_node: Optional[str] = Field(default=None, description="拒绝时指定的回退节点")
    feedback: str = Field(default="", description="审批意见（拒绝时必填）")
    reviewer: str = Field(default="", description="审批人")
    decided_at: str = Field(default="", description="审批时间（ISO 8601）")


class PublishResult(BaseModel):
    """feishu_publisher 输出：飞书写入结果。

    本包内节点为 stub；正式实现须从环境变量读取凭据，严禁硬编码或提交。
    """

    platform: str = Field(default="feishu", description="交付平台")
    status: str = Field(default="", description="写入结果（success/failed）")
    document_url: str = Field(default="", description="文档链接")
    document_id: str = Field(default="", description="文档 ID")
    published_at: str = Field(default="", description="写入时间（ISO 8601）")
    note: str = Field(default="", description="备注")
