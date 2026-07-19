"""节点：feishu_publisher（飞书文档写入）。

契约
----
输入（读取 state 键）：
- ``brief_analysis`` / ``script`` / ``humanized`` / ``fact_result`` /
  ``compliance_result`` / ``storyboard`` / ``human_decision`` (dict)：
  经人工审批通过的完整交付物；
输出（写入 state 键）：
- ``publish_result`` (dict)：agent.schemas.PublishResult。
路由语义：
- 主链路终点，完成后流向 END（status=completed）。
- 仅在 human_approval 通过后可到达；审批通过前禁止任何对外写入动作。

实现状态：stub。正式实现属 Stage 12 范围，须满足：
- 凭据仅从环境变量读取（FEISHU_APP_ID / FEISHU_APP_SECRET /
  FEISHU_FOLDER_TOKEN / FEISHU_DOCUMENT_ID，见 .env.example），
  严禁硬编码、严禁提交 .env 与任何 Token/Cookie；
- 写入内容必须携带 fact_result / compliance_result 摘要与人工审批记录，
  保证交付物可追溯；
- 网络失败如实返回 status=failed，不得伪造成功。
"""

from __future__ import annotations

from typing import Any

from agent.state import AgentState


def run(state: AgentState) -> dict[str, Any]:
    """节点入口（stub）。正式实现须通过 build_agent_graph 的 node_overrides 注入。"""
    raise NotImplementedError(
        "feishu_publisher 为外部系统节点 stub：飞书写入属 Stage 12，须凭据齐全后实现，"
        "经 build_agent_graph(node_overrides={'feishu_publisher': ...}) 注入；"
        "凭据只读环境变量，禁止硬编码；契约见 agent.schemas.PublishResult"
    )
