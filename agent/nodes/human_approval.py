"""节点：human_approval（人工审批）。

契约
----
输入（读取 state 键）：
- ``script`` / ``humanized`` / ``fact_result`` / ``compliance_result`` /
  ``storyboard`` (dict)：呈交人工审阅的交付物（本节点不修改）；
- ``human_decision`` (dict, 可选)：agent.schemas.HumanDecision。审批是外部
  人工动作——调用方在运行前注入，或在流程暂停后把决定补进状态再重跑。
输出（写入 state 键）：
- 无人工决定时写入 ``status = waiting_human``（图路由据此暂停于 END）；
- 已有人工决定时不写任何字段，由路由读取决定分流。
路由语义（由 agent.graph.route_after_human 实现）：
- approved=True              → feishu_publisher；
- approved=False             → human_decision.retry_node 指定的修改节点
  （仅允许 script_generator / humanizer / storyboard_generator，
  见 agent/policies/approval_rules.yaml），非法取值以无效路由中止；
- 无决定                     → 暂停（status=waiting_human）。

实现状态：可运行演示（纯状态判断，无 IO）。正式版可对接飞书审批/看板按钮等
交互入口，但"无决定不自动通过"的规则不得改变（auto_approve=false）。
"""

from __future__ import annotations

from typing import Any

from agent.state import STATUS_WAITING_HUMAN, AgentState


def run(state: AgentState) -> dict[str, Any]:
    """节点入口：无 human_decision 时进入等待人工状态。"""
    if state.get("human_decision") is None:
        return {"status": STATUS_WAITING_HUMAN}
    return {}
