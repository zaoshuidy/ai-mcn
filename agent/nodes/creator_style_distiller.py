"""节点：creator_style_distiller（达人风格蒸馏）。

契约
----
输入（读取 state 键）：
- ``style_timelines`` (dict, 可选)：视频时间线数据（含 ``timelines`` 列表）。
  缺省时从默认数据文件 ``data/processed/stage_3_top3_video_timelines.json``
  （Stage 3 Top3 真实视频时间线）读取。
- ``brief_analysis`` (dict)：上游 Brief 分析结果（正式版用于场景对齐，演示版
  仅透传引用，不参与统计）。
输出（写入 state 键）：
- ``style_profile`` (dict)：契约模型 agent.schemas.StyleProfile。
路由语义：
- 无条件流向 script_generator；本节点不参与回退。

实现状态：可运行演示——对真实时间线做确定性统计（主导形式、时长分布、
钩子模式原文摘录）。正式版由"达人风格 Skill"产出完整画像（节奏、口头禅、
镜头语言、字幕风格等），本统计视图可作为其事实底座。
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from agent.schemas import StyleProfile
from agent.state import AgentState

#: 默认风格语料（仓库根/data/processed/stage_3_top3_video_timelines.json）。
DEFAULT_TIMELINES_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "processed" / "stage_3_top3_video_timelines.json"
)


def distill_style(timelines: list[dict[str, Any]], *, source: str) -> dict[str, Any]:
    """从视频时间线列表统计风格画像（纯函数，便于单测）。"""
    durations = [float(t["duration_s"]) for t in timelines if t.get("duration_s") is not None]
    formats = Counter(t.get("primary_format") for t in timelines if t.get("primary_format"))
    profile = StyleProfile(
        reference_videos=[
            {
                "note_id": t.get("note_id", ""),
                "title": t.get("title", ""),
                "duration_s": t.get("duration_s"),
                "primary_format": t.get("primary_format", ""),
            }
            for t in timelines
        ],
        dominant_format=formats.most_common(1)[0][0] if formats else "",
        duration_range_s=[min(durations), max(durations)] if durations else [],
        avg_duration_s=round(sum(durations) / len(durations), 2) if durations else None,
        hook_patterns=[t.get("hook_analysis", "") for t in timelines if t.get("hook_analysis")],
        source=source,
        note="演示级统计画像（基于真实时间线）；完整风格画像由达人风格 Skill 产出",
    )
    return profile.model_dump()


def run(state: AgentState) -> dict[str, Any]:
    """节点入口：state.style_timelines 优先，否则读取默认时间线文件。"""
    payload = state.get("style_timelines")
    if payload is not None:
        return {"style_profile": distill_style(payload.get("timelines", []), source="state")}
    data = json.loads(DEFAULT_TIMELINES_PATH.read_text(encoding="utf-8"))
    rel = DEFAULT_TIMELINES_PATH.relative_to(Path(__file__).resolve().parents[2]).as_posix()
    return {"style_profile": distill_style(data.get("timelines", []), source=rel)}
