"""节点：script_generator（商单脚本生成）。

契约
----
输入（读取 state 键）：
- ``brief_analysis`` (dict)：agent.schemas.BriefAnalysis，提供允许卖点、
  场景、目标人群与内容要求；
- ``style_profile`` (dict)：agent.schemas.StyleProfile，提供达人风格约束；
- ``last_failure`` (dict, 可选)：质检/人工回退时携带的失败详情
  （gate、violations/feedback），修订时必须逐条响应并递增 version。
输出（写入 state 键）：
- ``script`` (dict)：agent.schemas.ScriptDraft，其中 ``text`` 为完整口播/字幕
  文本（下游两个质检节点的扫描对象），``claims_used`` 声明用到的卖点，
  ``target_duration_s`` 为分镜时长一致性校验基准。
路由语义：
- 无条件流向 humanizer；fact_regression / compliance_reviewer 未通过及人工
  拒绝（retry_node=script_generator）均回退到本节点。

实现状态：stub。正式实现依赖 LLM 与"脚本生成 Skill"（结构参考 registry
CAND-016，仅结构思路、禁止复制原文）；本包不内置任何模型调用。
"""

from __future__ import annotations

from typing import Any

from agent.state import AgentState


def run(state: AgentState) -> dict[str, Any]:
    """节点入口（stub）。正式实现须通过 build_agent_graph 的 node_overrides 注入。"""
    raise NotImplementedError(
        "script_generator 为 LLM 节点 stub：请接入脚本生成 Skill / LLM 实现后，"
        "经 build_agent_graph(node_overrides={'script_generator': ...}) 注入；"
        "输入输出契约见本模块 docstring 与 agent.schemas.ScriptDraft"
    )
