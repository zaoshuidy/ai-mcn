"""视频理解数据模型（Stage 2 视频 POC）。

真实性原则：
- 口播（speech）来自转写文件（transcript.srt），可追溯；
- 屏幕字幕/人物动作/场景/镜头类型/产品露出需要视觉标注，POC 阶段无视觉模型，
  默认空字符串，禁止编造；
- 风险词由规则扫描得出，附命中文本。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class VideoAsset(BaseModel):
    """已获取的视频文件（仅存 tmp/，不提交 Git）。"""

    source_url: str
    local_path: str = Field(description="tmp/ 下的本地路径")
    acquired_by: str = Field(description="yt-dlp / xhs-downloader")
    acquired_at: str = ""


class TranscriptSegment(BaseModel):
    """一条转写片段（单位：秒）。"""

    start: float = Field(..., ge=0)
    end: float = Field(..., ge=0)
    text: str


class Keyframe(BaseModel):
    """关键帧（低分辨率，可提交 Git）。"""

    timestamp: float = Field(..., ge=0)
    path: str = Field(description="相对路径")
    kind: str = Field(default="interval", description="interval / scene_change")


class TimelineEntry(BaseModel):
    """时间线条目。"""

    time: float = Field(..., ge=0, description="时间点（秒）")
    speech: str = Field(default="", description="口播（来自转写）")
    screen_subtitle: str = Field(default="", description="屏幕字幕（需视觉标注，POC 留空）")
    person_action: str = Field(default="", description="人物动作（需视觉标注，POC 留空）")
    scene: str = Field(default="", description="场景（需视觉标注，POC 留空）")
    shot_type: str = Field(default="", description="镜头类型（需视觉标注，POC 留空）")
    product_exposure: str = Field(default="", description="产品露出（需视觉标注，POC 留空）")
    risk_words: list[str] = Field(default_factory=list, description="命中的风险词")


class VideoTimeline(BaseModel):
    """video_timeline.json 顶层结构。"""

    source_url: str
    duration_seconds: float = Field(default=0, ge=0)
    transcript_file: str = ""
    keyframe_dir: str = ""
    entries: list[TimelineEntry] = Field(default_factory=list)
    notes: str = ""


class ContentAnalysis(BaseModel):
    """内容分析结论（全部须可追溯到转写/关键帧/URL）。"""

    source_url: str
    hook_first_3s: str = Field(default="", description="前 3 秒钩子（基于转写）")
    structure: str = ""
    rhythm: str = ""
    expression_style: str = ""
    product_integration: str = ""
    risk_notes: list[str] = Field(default_factory=list)


# ---------- Stage 2 真实视频 POC：12 字段时间线 ----------


class VideoSegment(BaseModel):
    """真实视频时间线片段（12 字段 + confidence）。

    真实性原则：
    - 视觉类字段（on_screen_text/scene/person_action/shot_type）无视觉证据时
      必须为 None，禁止根据口播编造画面；
    - food_or_product/product_first_appearance 仅可口播明确提及时填写，并降低 confidence；
    - evidence_frame_timestamps 只记录该时间段内真实抽取的关键帧时间戳。
    """

    start_time: float = Field(..., ge=0)
    end_time: float = Field(..., ge=0)
    transcript_summary: str = Field(default="", description="口播转述（来自转写文本）")
    on_screen_text: Optional[str] = Field(default=None, description="屏幕字幕（需视觉证据）")
    scene: Optional[str] = Field(default=None, description="场景（需视觉证据）")
    person_action: Optional[str] = Field(default=None, description="人物动作（需视觉证据）")
    shot_type: Optional[str] = Field(default=None, description="镜头类型（需视觉证据）")
    food_or_product: Optional[str] = Field(
        default=None, description="食物/产品（口播明确提及或视觉证据）"
    )
    product_first_appearance: Optional[float] = Field(
        default=None, ge=0, description="产品首次出现时间（秒，仅在有证据时填写）"
    )
    commercial_expression: Optional[str] = Field(
        default=None, description="商业表达（口播明确提及购买/链接/同款等）"
    )
    compliance_risks: list[str] = Field(default_factory=list, description="命中的合规风险词")
    evidence_frame_timestamps: list[float] = Field(
        default_factory=list, description="该时段内真实抽取的关键帧时间戳"
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class VideoTimelineV2(BaseModel):
    """提交 Git 的 video_timeline.json 顶层结构（不含完整转写文本）。"""

    note_id: str
    canonical_url: str
    creator_name: str = ""
    title: str = ""
    duration_seconds: float = Field(default=0, ge=0)
    observed_at: str = ""
    source: str = Field(default="page_observed")
    human_verified: bool = False
    segments: list[VideoSegment] = Field(default_factory=list)
    notes: str = ""


class VideoEvidenceManifest(BaseModel):
    """证据清单：视频文件哈希与处理工具链（原始视频不入 Git，仅记录哈希）。"""

    note_id: str
    canonical_url: str
    video_sha256: str = ""
    video_bytes: int = Field(default=0, ge=0)
    duration_seconds: Optional[float] = Field(default=None, ge=0)
    resolution: Optional[str] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    acquired_by: str = ""
    acquired_at: str = ""
    ffmpeg_version: str = ""
    transcription_tool: str = ""
    keyframe_count: int = Field(default=0, ge=0)
    keyframe_dir: str = Field(default="", description="tmp/ 下相对路径，不入 Git")
    transcript_srt_sha256: str = ""
    notes: str = ""
