"""视频理解数据模型（Stage 2 视频 POC）。

真实性原则：
- 口播（speech）来自转写文件（transcript.srt），可追溯；
- 屏幕字幕/人物动作/场景/镜头类型/产品露出需要视觉标注，POC 阶段无视觉模型，
  默认空字符串，禁止编造；
- 风险词由规则扫描得出，附命中文本。
"""

from __future__ import annotations

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
