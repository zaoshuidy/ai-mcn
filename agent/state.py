"""Agent 工作流状态定义（轻醒商单脚本链路）。

本模块是 ``agent/graph.py`` 最小可运行图与 ``agent/nodes/`` 各节点共用的状态契约。
状态采用 ``TypedDict(total=False)``：节点函数接收完整状态、返回需要合并的部分字段
（patch），由图引擎负责合并。该语义与 langgraph 的 state 更新方式对齐，便于后续
迁移（迁移路径见 ``reports/agent_packaging_guide.md``）。

字段分三组：
- 输入：``brief``、``max_retries``；
- 节点产出：``brief_analysis``、``style_profile``、``script``、``humanized``、
  ``fact_result``、``compliance_result``、``storyboard``、``human_decision``、
  ``publish_result``；
- 流程控制（仅图引擎与路由函数写入，业务节点不得写入）：``retry_count``、
  ``status``、``history``、``errors``、``last_failure``。
"""

from __future__ import annotations

from typing import Any, TypedDict

# --- 节点名常量（图的唯一合法节点集合） ---
NODE_BRIEF_ANALYZER = "brief_analyzer"
NODE_CREATOR_STYLE_DISTILLER = "creator_style_distiller"
NODE_SCRIPT_GENERATOR = "script_generator"
NODE_HUMANIZER = "humanizer"
NODE_FACT_REGRESSION = "fact_regression"
NODE_COMPLIANCE_REVIEWER = "compliance_reviewer"
NODE_STORYBOARD_GENERATOR = "storyboard_generator"
NODE_HUMAN_APPROVAL = "human_approval"
NODE_FEISHU_PUBLISHER = "feishu_publisher"

#: 主链路节点顺序（不含回退边），测试与文档以此为单一事实来源。
NODE_ORDER: list[str] = [
    NODE_BRIEF_ANALYZER,
    NODE_CREATOR_STYLE_DISTILLER,
    NODE_SCRIPT_GENERATOR,
    NODE_HUMANIZER,
    NODE_FACT_REGRESSION,
    NODE_COMPLIANCE_REVIEWER,
    NODE_STORYBOARD_GENERATOR,
    NODE_HUMAN_APPROVAL,
    NODE_FEISHU_PUBLISHER,
]

# --- 运行状态取值 ---
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_WAITING_HUMAN = "waiting_human"
STATUS_ABORTED_MAX_RETRIES = "aborted_max_retries"
STATUS_ABORTED_INVALID_ROUTE = "aborted_invalid_human_route"

#: 默认最大累计回退次数（与 agent/policies/approval_rules.yaml 的 max_retries 一致）。
DEFAULT_MAX_RETRIES = 3

#: 人工拒绝后允许回退的目标节点（与 approval_rules.yaml 的 allowed_retry_nodes 一致）。
HUMAN_RETRY_TARGETS: frozenset[str] = frozenset(
    {NODE_SCRIPT_GENERATOR, NODE_HUMANIZER, NODE_STORYBOARD_GENERATOR}
)


class AgentState(TypedDict, total=False):
    """商单脚本 Agent 的完整工作流状态。

    所有字段可选；节点只读取自身契约内的字段、只返回自身负责写入的字段。
    各字段的结构契约见 ``agent/schemas.py`` 与各节点模块 docstring。
    """

    # 输入
    brief: dict[str, Any]
    max_retries: int

    # 节点产出
    brief_analysis: dict[str, Any]
    style_profile: dict[str, Any]
    script: dict[str, Any]
    humanized: dict[str, Any]
    fact_result: dict[str, Any]
    compliance_result: dict[str, Any]
    storyboard: dict[str, Any]
    human_decision: dict[str, Any]
    publish_result: dict[str, Any]

    # 流程控制
    retry_count: int
    status: str
    history: list[str]
    errors: list[dict[str, Any]]
    last_failure: dict[str, Any]


def make_initial_state(
    brief: dict[str, Any] | None = None,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    human_decision: dict[str, Any] | None = None,
) -> AgentState:
    """构造一份合法的初始状态。

    :param brief: 结构化品牌 Brief（如 ``data/processed/qingxing_brief.json`` 的内容）；
        缺省时由 brief_analyzer 节点从默认数据文件读取。
    :param max_retries: 最大累计回退次数，超过即中止。
    :param human_decision: 预先注入的人工审批决定；缺省时流程到达人工审批节点后
        进入 ``waiting_human`` 状态并暂停。
    """
    state: AgentState = {
        "status": STATUS_RUNNING,
        "retry_count": 0,
        "max_retries": max_retries,
        "history": [],
        "errors": [],
    }
    if brief is not None:
        state["brief"] = brief
    if human_decision is not None:
        state["human_decision"] = human_decision
    return state
