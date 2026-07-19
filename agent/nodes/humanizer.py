"""节点：humanizer（中文人味化处理）。

契约
----
输入（读取 state 键）：
- ``script`` (dict)：agent.schemas.ScriptDraft，待处理草稿；
- ``style_profile`` (dict)：agent.schemas.StyleProfile，保持达人口吻一致；
- ``last_failure`` (dict, 可选)：人工拒绝（retry_node=humanizer）时携带的
  feedback，修订时必须逐条响应。
输出（写入 state 键）：
- ``humanized`` (dict)：agent.schemas.HumanizedScript，``text`` 为处理后全文，
  ``changes`` 记录相对草稿的修改点（供人工审批与事实回检追溯）。
路由语义：
- 无条件流向 fact_regression；人工拒绝（retry_node=humanizer）可回退本节点。
- 人味化处理不得改变草稿的事实与合规语义——质检在人味化之后执行，
  防止"改写引入违禁表达"。

实现状态：stub。规则思路参考 registry CAND-013 / CAND-014（仅参考、禁止
复制原文），正式实现依赖 LLM 与自研中文自然化规则。
"""

from __future__ import annotations

from typing import Any

from agent.state import AgentState


def run(state: AgentState) -> dict[str, Any]:
    """节点入口（stub）。正式实现须通过 build_agent_graph 的 node_overrides 注入。"""
    raise NotImplementedError(
        "humanizer 为 LLM 节点 stub：请接入中文人味化实现后，经 "
        "build_agent_graph(node_overrides={'humanizer': ...}) 注入；"
        "输入输出契约见本模块 docstring 与 agent.schemas.HumanizedScript"
    )
