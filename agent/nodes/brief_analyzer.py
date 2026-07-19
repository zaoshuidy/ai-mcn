"""节点：brief_analyzer（Brief 分析）。

契约
----
输入（读取 state 键）：
- ``brief`` (dict, 可选)：结构化品牌 Brief。缺省时从默认数据文件
  ``data/processed/qingxing_brief.json``（Stage 1 已验收的真实 Brief）读取。
输出（写入 state 键）：
- ``brief_analysis`` (dict)：契约模型 agent.schemas.BriefAnalysis。
路由语义：
- 无条件流向 creator_style_distiller；本节点不参与回退。

实现状态：可运行演示（纯本地文件读取，无 LLM）。正式版可在此叠加 LLM 摘要，
但 blockers（阻塞级缺失信息）必须原样透传，不得由模型增删。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.schemas import BriefAnalysis
from agent.state import AgentState

#: 默认 Brief 数据文件（仓库根/data/processed/qingxing_brief.json）。
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BRIEF_PATH = _REPO_ROOT / "data" / "processed" / "qingxing_brief.json"


def analyze_brief(brief: dict[str, Any], *, source: str) -> dict[str, Any]:
    """把结构化 Brief 压缩为下游节点消费的编排视图（纯函数，便于单测）。"""
    selling_points = brief.get("selling_points", [])
    analysis = BriefAnalysis(
        brief_id=brief.get("brief_id", ""),
        brand_name=brief.get("brand", {}).get("brand_name") or brief.get("brand_name", ""),
        product_name=brief.get("brand", {}).get("product_name") or brief.get("product_name", ""),
        allowed_claims=[p.get("claim", "") for p in selling_points if p.get("claim")],
        claim_types={p.get("claim", ""): p.get("claim_type", "") for p in selling_points},
        scenarios=[s.get("name", "") for s in brief.get("usage_scenarios", [])],
        target_audience=brief.get("target_audience", {}),
        content_requirements=brief.get("content_requirements", []),
        compliance_categories=[r.get("category", "") for r in brief.get("compliance_rules", [])],
        blockers=[
            m.get("field", "")
            for m in brief.get("missing_information", [])
            if m.get("blocks_next_stage")
        ],
        source=source,
    )
    return analysis.model_dump()


def run(state: AgentState) -> dict[str, Any]:
    """节点入口：state.brief 优先，否则读取默认 Brief 文件。"""
    brief = state.get("brief")
    if brief is not None:
        return {"brief_analysis": analyze_brief(brief, source="state.brief")}
    payload = json.loads(DEFAULT_BRIEF_PATH.read_text(encoding="utf-8"))
    rel = DEFAULT_BRIEF_PATH.relative_to(Path(__file__).resolve().parents[2]).as_posix()
    return {"brief_analysis": analyze_brief(payload, source=rel)}
