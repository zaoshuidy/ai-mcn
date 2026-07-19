"""最小可运行的 Agent 编排图（纯 Python 实现，不依赖 langgraph）。

主链路：
    brief_analyzer → creator_style_distiller → script_generator → humanizer
    → fact_regression → compliance_reviewer → storyboard_generator
    → human_approval → feishu_publisher → END

失败回退（全部由路由函数实现，业务节点不做路由决策）：
    fact_regression 未通过            → script_generator
    compliance_reviewer 未通过        → script_generator
    分镜与脚本目标时长不一致          → storyboard_generator
    人工拒绝                          → human_decision.retry_node 指定的修改节点
    累计回退次数超过 max_retries      → 中止（status=aborted_max_retries）
    人工决定缺少合法 retry_node       → 中止（status=aborted_invalid_human_route）

langgraph 迁移说明
------------------
langgraph 在组件 registry 中为 CAND-017（reference_only，2026-07-19 审查），
作为运行时依赖引入须另行通过组件准入评审，故本包以纯 Python 实现等价语义。
评审通过后按以下对应关系迁移：

    AgentGraph                     → StateGraph(AgentState)
    add_node(name, func)           → builder.add_node(name, func)   # 签名同为 state -> patch
    add_edge(src, dst)             → builder.add_edge(src, dst)
    add_conditional_edges(src, fn) → builder.add_conditional_edges(src, router)
                                     router 由返回 (next, patch) 改为返回 next，
                                     patch 改由节点自身或 Command(goto=..., update=...) 表达
    END                            → langgraph.graph.END
    graph.run(state)               → builder.compile().invoke(state)
    waiting_human 暂停             → interrupt_before=["human_approval"] + checkpointer
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from agent.state import (
    DEFAULT_MAX_RETRIES,
    HUMAN_RETRY_TARGETS,
    NODE_BRIEF_ANALYZER,
    NODE_COMPLIANCE_REVIEWER,
    NODE_CREATOR_STYLE_DISTILLER,
    NODE_FACT_REGRESSION,
    NODE_FEISHU_PUBLISHER,
    NODE_HUMAN_APPROVAL,
    NODE_HUMANIZER,
    NODE_SCRIPT_GENERATOR,
    NODE_STORYBOARD_GENERATOR,
    STATUS_ABORTED_INVALID_ROUTE,
    STATUS_ABORTED_MAX_RETRIES,
    STATUS_COMPLETED,
    STATUS_RUNNING,
    STATUS_WAITING_HUMAN,
    AgentState,
)

#: 终止节点标记（迁移 langgraph 时替换为 langgraph.graph.END）。
END = "__end__"

#: 分镜总时长与脚本目标时长的容差（秒）。
DURATION_TOLERANCE_S = 5.0

#: 节点函数：接收完整状态，返回需要合并的状态 patch（可为 None）。
NodeFunc = Callable[[AgentState], Optional[dict[str, Any]]]

#: 路由函数：接收合并后的状态，返回 (下一节点名或 END, 需要合并的状态 patch)。
Router = Callable[[AgentState], tuple[str, dict[str, Any]]]


class AgentGraph:
    """节点注册 + 状态流转的最小图引擎。

    使用方式：``build_agent_graph()`` 返回按主链路装配好的图；测试可通过
    ``node_overrides`` 注入假节点，或拿到图后用 ``add_node`` 覆盖单个节点。
    """

    def __init__(self, max_steps: int = 100) -> None:
        self.nodes: dict[str, NodeFunc] = {}
        self.routers: dict[str, Router] = {}
        self.entry: Optional[str] = None
        self.max_steps = max_steps

    def add_node(self, name: str, func: NodeFunc) -> None:
        """注册（或覆盖）一个节点。"""
        self.nodes[name] = func

    def set_entry(self, name: str) -> None:
        """设置入口节点。"""
        if name not in self.nodes:
            raise ValueError(f"入口节点未注册: {name}")
        self.entry = name

    def add_edge(self, source: str, target: str) -> None:
        """添加无条件边（target 可为 END）。"""

        def router(_state: AgentState, _target: str = target) -> tuple[str, dict[str, Any]]:
            return _target, {}

        self.routers[source] = router

    def add_conditional_edges(self, source: str, router: Router) -> None:
        """添加条件边：router(state) -> (next_node, state_patch)。"""
        self.routers[source] = router

    def run(self, state: Optional[AgentState] = None) -> AgentState:
        """从入口节点执行到 END，返回最终状态。

        节点抛出的异常（含 stub 的 NotImplementedError）原样向上传播；
        超过 max_steps 视为路由配置错误并抛 RuntimeError。
        """
        if self.entry is None:
            raise ValueError("图未设置入口节点（set_entry）")
        merged: AgentState = {
            "status": STATUS_RUNNING,
            "retry_count": 0,
            "max_retries": DEFAULT_MAX_RETRIES,
            "history": [],
            "errors": [],
        }
        merged.update(state or {})
        node_name = self.entry
        while node_name != END:
            func = self.nodes.get(node_name)
            if func is None:
                raise ValueError(f"未注册的节点: {node_name}")
            update = func(merged)
            if update:
                merged.update(update)
            merged["history"].append(node_name)
            router = self.routers.get(node_name)
            if router is None:
                raise ValueError(f"节点 {node_name} 缺少出边路由")
            node_name, patch = router(merged)
            if patch:
                merged.update(patch)
            if len(merged["history"]) > self.max_steps:
                raise RuntimeError(
                    f"超过 max_steps={self.max_steps}，疑似路由死循环: {merged['history']}"
                )
        if merged.get("status") == STATUS_RUNNING:
            # 到达 END 且未被打上等待/中止标记：主链路完整走完。
            merged["status"] = STATUS_COMPLETED
        return merged


# ---------------------------------------------------------------------------
# 路由函数（主链路的唯一决策点；回退矩阵见 reports/agent_packaging_guide.md）
# ---------------------------------------------------------------------------


def _fallback(
    state: AgentState,
    target: str,
    *,
    gate: str,
    detail: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """回退公共逻辑：累计 retry_count，超限则中止。

    retry_count 统计一次执行内所有闸口的累计回退次数（共享预算），
    与 agent/policies/approval_rules.yaml 的 max_retries 语义一致。
    """
    retry_count = state.get("retry_count", 0) + 1
    failure = {
        "gate": gate,
        "fallback_to": target,
        "retry_count": retry_count,
        "detail": detail,
    }
    patch: dict[str, Any] = {
        "retry_count": retry_count,
        "last_failure": failure,
        "errors": [*state.get("errors", []), failure],
    }
    if retry_count > state.get("max_retries", DEFAULT_MAX_RETRIES):
        patch["status"] = STATUS_ABORTED_MAX_RETRIES
        return END, patch
    return target, patch


def route_after_fact(state: AgentState) -> tuple[str, dict[str, Any]]:
    """事实回检未通过 → 回退 script_generator 修订。"""
    result = state.get("fact_result") or {}
    if result.get("passed"):
        return NODE_COMPLIANCE_REVIEWER, {}
    return _fallback(
        state,
        NODE_SCRIPT_GENERATOR,
        gate=NODE_FACT_REGRESSION,
        detail={"violations": result.get("violations", [])},
    )


def route_after_compliance(state: AgentState) -> tuple[str, dict[str, Any]]:
    """合规审查未通过 → 回退 script_generator 修订。"""
    result = state.get("compliance_result") or {}
    if result.get("passed"):
        return NODE_STORYBOARD_GENERATOR, {}
    return _fallback(
        state,
        NODE_SCRIPT_GENERATOR,
        gate=NODE_COMPLIANCE_REVIEWER,
        detail={"violations": result.get("violations", [])},
    )


def route_after_storyboard(state: AgentState) -> tuple[str, dict[str, Any]]:
    """分镜与脚本目标时长不一致 → 回退 storyboard_generator 重排。"""
    consistent, detail = check_duration_consistency(state.get("script"), state.get("storyboard"))
    if consistent:
        return NODE_HUMAN_APPROVAL, {}
    return _fallback(state, NODE_STORYBOARD_GENERATOR, gate="storyboard_duration", detail=detail)


def route_after_human(state: AgentState) -> tuple[str, dict[str, Any]]:
    """人工审批路由：通过 → 飞书发布；拒绝 → 指定修改节点；等待 → 暂停。"""
    if state.get("status") == STATUS_WAITING_HUMAN:
        return END, {}
    decision = state.get("human_decision") or {}
    if decision.get("approved"):
        return NODE_FEISHU_PUBLISHER, {}
    target = decision.get("retry_node")
    if target not in HUMAN_RETRY_TARGETS:
        error = {
            "gate": NODE_HUMAN_APPROVAL,
            "reason": "invalid_retry_node",
            "retry_node": target,
            "allowed": sorted(HUMAN_RETRY_TARGETS),
        }
        return END, {
            "status": STATUS_ABORTED_INVALID_ROUTE,
            "errors": [*state.get("errors", []), error],
            "last_failure": error,
        }
    return _fallback(
        state,
        target,
        gate=NODE_HUMAN_APPROVAL,
        detail={"feedback": decision.get("feedback", ""), "reviewer": decision.get("reviewer", "")},
    )


def check_duration_consistency(
    script: Optional[dict[str, Any]],
    storyboard: Optional[dict[str, Any]],
    *,
    tolerance_s: float = DURATION_TOLERANCE_S,
) -> tuple[bool, dict[str, Any]]:
    """校验分镜总时长与脚本目标时长是否一致（容差 tolerance_s 秒）。

    分镜总时长优先取 storyboard.total_duration_s，缺省时按各镜头
    (end_s - start_s) 求和。任一时长缺失即判不一致并说明原因。
    """
    if not script or not storyboard:
        return False, {"reason": "missing_script_or_storyboard"}
    target = script.get("target_duration_s")
    total = storyboard.get("total_duration_s")
    if total is None:
        shots = storyboard.get("shots") or []
        if shots:
            total = sum(
                float(shot.get("end_s", 0.0)) - float(shot.get("start_s", 0.0)) for shot in shots
            )
    if target is None or total is None:
        return False, {
            "reason": "missing_duration_fields",
            "script_target_s": target,
            "storyboard_total_s": total,
        }
    diff = abs(float(total) - float(target))
    detail = {
        "reason": "duration_mismatch",
        "script_target_s": float(target),
        "storyboard_total_s": float(total),
        "diff_s": diff,
        "tolerance_s": tolerance_s,
    }
    return diff <= tolerance_s, detail


# ---------------------------------------------------------------------------
# 装配
# ---------------------------------------------------------------------------


def _default_nodes() -> dict[str, NodeFunc]:
    """默认节点实现：规则类节点为可运行演示，LLM/外部系统节点为 stub。"""
    from agent.nodes import (  # 延迟导入，避免与 agent/__init__ 循环
        brief_analyzer,
        compliance_reviewer,
        creator_style_distiller,
        fact_regression,
        feishu_publisher,
        human_approval,
        humanizer,
        script_generator,
        storyboard_generator,
    )

    return {
        NODE_BRIEF_ANALYZER: brief_analyzer.run,
        NODE_CREATOR_STYLE_DISTILLER: creator_style_distiller.run,
        NODE_SCRIPT_GENERATOR: script_generator.run,
        NODE_HUMANIZER: humanizer.run,
        NODE_FACT_REGRESSION: fact_regression.run,
        NODE_COMPLIANCE_REVIEWER: compliance_reviewer.run,
        NODE_STORYBOARD_GENERATOR: storyboard_generator.run,
        NODE_HUMAN_APPROVAL: human_approval.run,
        NODE_FEISHU_PUBLISHER: feishu_publisher.run,
    }


def build_agent_graph(
    node_overrides: Optional[dict[str, NodeFunc]] = None,
    *,
    max_steps: int = 100,
) -> AgentGraph:
    """按主链路装配最小可运行图。

    :param node_overrides: 按节点名覆盖默认实现（测试注入假节点、正式接入
        LLM/Skill 实现的统一入口）。
    :param max_steps: 单次运行允许的最大节点执行次数，超出视为路由死循环。
    """
    graph = AgentGraph(max_steps=max_steps)
    for name, func in {**_default_nodes(), **(node_overrides or {})}.items():
        graph.add_node(name, func)
    graph.set_entry(NODE_BRIEF_ANALYZER)

    graph.add_edge(NODE_BRIEF_ANALYZER, NODE_CREATOR_STYLE_DISTILLER)
    graph.add_edge(NODE_CREATOR_STYLE_DISTILLER, NODE_SCRIPT_GENERATOR)
    graph.add_edge(NODE_SCRIPT_GENERATOR, NODE_HUMANIZER)
    graph.add_edge(NODE_HUMANIZER, NODE_FACT_REGRESSION)
    graph.add_conditional_edges(NODE_FACT_REGRESSION, route_after_fact)
    graph.add_conditional_edges(NODE_COMPLIANCE_REVIEWER, route_after_compliance)
    graph.add_conditional_edges(NODE_STORYBOARD_GENERATOR, route_after_storyboard)
    graph.add_conditional_edges(NODE_HUMAN_APPROVAL, route_after_human)
    graph.add_edge(NODE_FEISHU_PUBLISHER, END)
    return graph


def run_demo() -> AgentState:
    """端到端演示：LLM/外部系统节点替换为确定性假实现，规则节点用真实策略文件。

    不读取 data/ 下任何文件、不访问网络、不需要凭据，可随时复现。
    命令行运行：``python -m agent.graph``。
    """

    def fake_brief_analyzer(_state: AgentState) -> dict[str, Any]:
        return {
            "brief_analysis": {
                "brief_id": "demo",
                "brand_name": "轻醒",
                "product_name": "0蔗糖高蛋白希腊酸奶",
                "allowed_claims": ["高蛋白", "0蔗糖", "饱腹感", "低负担"],
                "scenarios": ["早餐", "运动后", "下午茶"],
                "source": "run_demo_inline",
            }
        }

    def fake_style_distiller(_state: AgentState) -> dict[str, Any]:
        return {"style_profile": {"dominant_format": "voiceover", "source": "run_demo_inline"}}

    def fake_script_generator(state: AgentState) -> dict[str, Any]:
        version = len([n for n in state.get("history", []) if n == NODE_SCRIPT_GENERATOR])
        return {
            "script": {
                "version": version,
                "title": "早八人的省心早餐",
                "text": (
                    "早上来不及做早餐的时候，我会带一杯轻醒希腊酸奶。"
                    "口感浓，挖一勺配麦片就是一顿很省心的早餐。"
                    "下午犯困的时候换蓝莓味，办公室抽屉里常备。"
                ),
                "claims_used": [],
                "target_duration_s": 45.0,
            }
        }

    def fake_humanizer(state: AgentState) -> dict[str, Any]:
        script = state.get("script", {})
        return {
            "humanized": {
                "text": script.get("text", ""),
                "changes": ["演示实现：未做改写"],
                "based_on_version": script.get("version", 1),
            }
        }

    def fake_storyboard_generator(_state: AgentState) -> dict[str, Any]:
        return {
            "storyboard": {
                "shots": [
                    {"index": 0, "start_s": 0.0, "end_s": 10.0, "visual": "晨间厨房"},
                    {"index": 1, "start_s": 10.0, "end_s": 30.0, "visual": "酸奶开盖+麦片"},
                    {"index": 2, "start_s": 30.0, "end_s": 45.0, "visual": "办公室下午茶"},
                ],
                "total_duration_s": 45.0,
            }
        }

    def fake_human_approval(_state: AgentState) -> dict[str, Any]:
        return {"human_decision": {"approved": True, "reviewer": "demo", "feedback": ""}}

    def fake_feishu_publisher(_state: AgentState) -> dict[str, Any]:
        return {
            "publish_result": {"platform": "feishu", "status": "success", "note": "demo 假写入"}
        }

    graph = build_agent_graph(
        {
            NODE_BRIEF_ANALYZER: fake_brief_analyzer,
            NODE_CREATOR_STYLE_DISTILLER: fake_style_distiller,
            NODE_SCRIPT_GENERATOR: fake_script_generator,
            NODE_HUMANIZER: fake_humanizer,
            NODE_STORYBOARD_GENERATOR: fake_storyboard_generator,
            NODE_HUMAN_APPROVAL: fake_human_approval,
            NODE_FEISHU_PUBLISHER: fake_feishu_publisher,
        }
    )
    state = graph.run()
    return state


if __name__ == "__main__":
    final_state = run_demo()
    print("节点执行轨迹:", " -> ".join(final_state["history"]))
    print("最终状态:", final_state["status"])
    print("回退次数:", final_state["retry_count"])
