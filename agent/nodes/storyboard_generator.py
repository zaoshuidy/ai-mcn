"""节点：storyboard_generator（视频分镜生成）。

契约
----
输入（读取 state 键）：
- ``humanized`` (dict)：agent.schemas.HumanizedScript，分镜的文本基准；
- ``script`` (dict)：agent.schemas.ScriptDraft，``target_duration_s`` 为
  分镜总时长的一致性基准；
- ``style_profile`` (dict)：agent.schemas.StyleProfile，镜头语言参考；
- ``last_failure`` (dict, 可选)：时长不一致回退（gate=storyboard_duration）
  或人工拒绝（retry_node=storyboard_generator）时携带的详情。
输出（写入 state 键）：
- ``storyboard`` (dict)：agent.schemas.Storyboard，``total_duration_s``（缺省按
  各镜头 end_s-start_s 求和）与脚本目标时长差超过 5 秒即被路由回退本节点。
路由语义：
- 时长一致 → human_approval；不一致 → 回退本节点重排（累计超 max_retries 中止）。

实现状态：stub。正式实现依赖 LLM 与"分镜 Skill"（字段结构参考 registry
CAND-015，仅结构参考、禁止复制原文），并须核对拍摄可行性（场地/道具/样品）。
"""

from __future__ import annotations

from typing import Any

from agent.state import AgentState


def run(state: AgentState) -> dict[str, Any]:
    """节点入口（stub）。正式实现须通过 build_agent_graph 的 node_overrides 注入。"""
    raise NotImplementedError(
        "storyboard_generator 为 LLM 节点 stub：请接入分镜 Skill / LLM 实现后，经 "
        "build_agent_graph(node_overrides={'storyboard_generator': ...}) 注入；"
        "输入输出契约见本模块 docstring 与 agent.schemas.Storyboard"
    )
