"""Agent 编排图测试（纯离线，不依赖 LLM / langgraph / 外部凭据）。

覆盖任务要求的五类路由语义：节点顺序、fact/compliance 失败回退
script_generator、分镜时长不一致回退 storyboard_generator、人工拒绝路由、
最大重试上限；另覆盖规则演示节点（基于真实策略文件）与本地数据演示节点。
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

import pytest

from agent.graph import build_agent_graph, check_duration_consistency, run_demo
from agent.nodes import (
    brief_analyzer,
    compliance_reviewer,
    creator_style_distiller,
    fact_regression,
)
from agent.state import (
    HUMAN_RETRY_TARGETS,
    NODE_BRIEF_ANALYZER,
    NODE_COMPLIANCE_REVIEWER,
    NODE_CREATOR_STYLE_DISTILLER,
    NODE_FACT_REGRESSION,
    NODE_FEISHU_PUBLISHER,
    NODE_HUMAN_APPROVAL,
    NODE_HUMANIZER,
    NODE_ORDER,
    NODE_SCRIPT_GENERATOR,
    NODE_STORYBOARD_GENERATOR,
    STATUS_ABORTED_INVALID_ROUTE,
    STATUS_ABORTED_MAX_RETRIES,
    STATUS_COMPLETED,
    STATUS_WAITING_HUMAN,
    AgentState,
    make_initial_state,
)

NodeFunc = Callable[[AgentState], Optional[dict[str, Any]]]


def make_overrides(
    *,
    fact_failures: int = 0,
    compliance_failures: int = 0,
    storyboard_mismatches: int = 0,
    human_decisions: Optional[list[dict[str, Any]]] = None,
    override_human: bool = True,
) -> tuple[dict[str, NodeFunc], dict[str, int]]:
    """构造一组确定性假节点（LLM/审批/发布位），返回 (overrides, 调用计数)。"""
    calls = {"fact": 0, "compliance": 0, "storyboard": 0, "human": 0, "publisher": 0}

    def fake_brief_analyzer(_state: AgentState) -> dict[str, Any]:
        return {"brief_analysis": {"brand_name": "轻醒", "allowed_claims": []}}

    def fake_style_distiller(_state: AgentState) -> dict[str, Any]:
        return {"style_profile": {"dominant_format": "voiceover"}}

    def fake_script_generator(_state: AgentState) -> dict[str, Any]:
        return {
            "script": {"text": "一杯酸奶的早餐日常。", "claims_used": [], "target_duration_s": 60.0}
        }

    def fake_humanizer(state: AgentState) -> dict[str, Any]:
        return {"humanized": {"text": state.get("script", {}).get("text", ""), "changes": []}}

    def fake_fact_regression(_state: AgentState) -> dict[str, Any]:
        calls["fact"] += 1
        passed = calls["fact"] > fact_failures
        return {
            "fact_result": {"passed": passed, "violations": [] if passed else [{"code": "fake"}]}
        }

    def fake_compliance_reviewer(_state: AgentState) -> dict[str, Any]:
        calls["compliance"] += 1
        passed = calls["compliance"] > compliance_failures
        return {
            "compliance_result": {
                "passed": passed,
                "violations": [] if passed else [{"code": "fake"}],
            }
        }

    def fake_storyboard_generator(_state: AgentState) -> dict[str, Any]:
        calls["storyboard"] += 1
        mismatch = calls["storyboard"] <= storyboard_mismatches
        return {"storyboard": {"shots": [], "total_duration_s": 75.0 if mismatch else 60.0}}

    def fake_human_approval(_state: AgentState) -> dict[str, Any]:
        calls["human"] += 1
        decisions = human_decisions if human_decisions is not None else [{"approved": True}]
        return {"human_decision": decisions[min(calls["human"], len(decisions)) - 1]}

    def fake_feishu_publisher(_state: AgentState) -> dict[str, Any]:
        calls["publisher"] += 1
        return {"publish_result": {"platform": "feishu", "status": "success"}}

    overrides: dict[str, NodeFunc] = {
        NODE_BRIEF_ANALYZER: fake_brief_analyzer,
        NODE_CREATOR_STYLE_DISTILLER: fake_style_distiller,
        NODE_SCRIPT_GENERATOR: fake_script_generator,
        NODE_HUMANIZER: fake_humanizer,
        NODE_FACT_REGRESSION: fake_fact_regression,
        NODE_COMPLIANCE_REVIEWER: fake_compliance_reviewer,
        NODE_STORYBOARD_GENERATOR: fake_storyboard_generator,
        NODE_FEISHU_PUBLISHER: fake_feishu_publisher,
    }
    if override_human:
        overrides[NODE_HUMAN_APPROVAL] = fake_human_approval
    return overrides, calls


class TestGraphAssembly:
    def test_default_graph_registers_all_nodes_in_order(self) -> None:
        graph = build_agent_graph()
        assert list(graph.nodes) == NODE_ORDER
        assert graph.entry == NODE_BRIEF_ANALYZER

    def test_every_node_has_an_outgoing_route(self) -> None:
        graph = build_agent_graph()
        assert set(graph.routers) == set(NODE_ORDER)

    def test_human_retry_targets_match_policy(self) -> None:
        assert HUMAN_RETRY_TARGETS == frozenset(
            {NODE_SCRIPT_GENERATOR, NODE_HUMANIZER, NODE_STORYBOARD_GENERATOR}
        )


class TestHappyPath:
    def test_nodes_run_in_order_and_complete(self) -> None:
        overrides, calls = make_overrides()
        state = build_agent_graph(overrides).run(make_initial_state())
        assert state["history"] == NODE_ORDER
        assert state["status"] == STATUS_COMPLETED
        assert state["retry_count"] == 0
        assert calls["publisher"] == 1


class TestQualityGateFallbacks:
    def test_fact_failure_falls_back_to_script_generator(self) -> None:
        overrides, _calls = make_overrides(fact_failures=1)
        state = build_agent_graph(overrides).run(make_initial_state())
        assert state["status"] == STATUS_COMPLETED
        assert state["retry_count"] == 1
        assert state["history"] == [
            NODE_BRIEF_ANALYZER,
            NODE_CREATOR_STYLE_DISTILLER,
            NODE_SCRIPT_GENERATOR,
            NODE_HUMANIZER,
            NODE_FACT_REGRESSION,
            NODE_SCRIPT_GENERATOR,  # fact 未通过 → 回退重修
            NODE_HUMANIZER,
            NODE_FACT_REGRESSION,
            NODE_COMPLIANCE_REVIEWER,
            NODE_STORYBOARD_GENERATOR,
            NODE_HUMAN_APPROVAL,
            NODE_FEISHU_PUBLISHER,
        ]
        assert state["last_failure"]["gate"] == NODE_FACT_REGRESSION

    def test_compliance_failure_falls_back_to_script_generator(self) -> None:
        overrides, _calls = make_overrides(compliance_failures=1)
        state = build_agent_graph(overrides).run(make_initial_state())
        assert state["status"] == STATUS_COMPLETED
        assert state["retry_count"] == 1
        assert state["history"] == [
            NODE_BRIEF_ANALYZER,
            NODE_CREATOR_STYLE_DISTILLER,
            NODE_SCRIPT_GENERATOR,
            NODE_HUMANIZER,
            NODE_FACT_REGRESSION,
            NODE_COMPLIANCE_REVIEWER,
            NODE_SCRIPT_GENERATOR,  # compliance 未通过 → 回退重修
            NODE_HUMANIZER,
            NODE_FACT_REGRESSION,
            NODE_COMPLIANCE_REVIEWER,
            NODE_STORYBOARD_GENERATOR,
            NODE_HUMAN_APPROVAL,
            NODE_FEISHU_PUBLISHER,
        ]
        assert state["last_failure"]["gate"] == NODE_COMPLIANCE_REVIEWER

    def test_storyboard_duration_mismatch_retries_storyboard_generator(self) -> None:
        overrides, _calls = make_overrides(storyboard_mismatches=1)
        state = build_agent_graph(overrides).run(make_initial_state())
        assert state["status"] == STATUS_COMPLETED
        assert state["retry_count"] == 1
        assert state["history"] == [
            NODE_BRIEF_ANALYZER,
            NODE_CREATOR_STYLE_DISTILLER,
            NODE_SCRIPT_GENERATOR,
            NODE_HUMANIZER,
            NODE_FACT_REGRESSION,
            NODE_COMPLIANCE_REVIEWER,
            NODE_STORYBOARD_GENERATOR,
            NODE_STORYBOARD_GENERATOR,  # 时长不一致 → 回退重排
            NODE_HUMAN_APPROVAL,
            NODE_FEISHU_PUBLISHER,
        ]
        failure = state["last_failure"]
        assert failure["gate"] == "storyboard_duration"
        assert failure["detail"]["reason"] == "duration_mismatch"


class TestHumanApprovalRouting:
    def test_human_reject_routes_to_requested_node(self) -> None:
        decisions = [
            {"approved": False, "retry_node": NODE_HUMANIZER, "feedback": "语气太硬"},
            {"approved": True},
        ]
        overrides, _calls = make_overrides(human_decisions=decisions)
        state = build_agent_graph(overrides).run(make_initial_state())
        assert state["status"] == STATUS_COMPLETED
        assert state["retry_count"] == 1
        assert state["history"] == [
            NODE_BRIEF_ANALYZER,
            NODE_CREATOR_STYLE_DISTILLER,
            NODE_SCRIPT_GENERATOR,
            NODE_HUMANIZER,
            NODE_FACT_REGRESSION,
            NODE_COMPLIANCE_REVIEWER,
            NODE_STORYBOARD_GENERATOR,
            NODE_HUMAN_APPROVAL,
            NODE_HUMANIZER,  # 人工拒绝并指定回退 humanizer
            NODE_FACT_REGRESSION,
            NODE_COMPLIANCE_REVIEWER,
            NODE_STORYBOARD_GENERATOR,
            NODE_HUMAN_APPROVAL,
            NODE_FEISHU_PUBLISHER,
        ]
        assert state["last_failure"]["gate"] == NODE_HUMAN_APPROVAL

    def test_human_reject_with_invalid_target_aborts(self) -> None:
        decisions = [{"approved": False, "retry_node": NODE_FEISHU_PUBLISHER, "feedback": "x"}]
        overrides, calls = make_overrides(human_decisions=decisions)
        state = build_agent_graph(overrides).run(make_initial_state())
        assert state["status"] == STATUS_ABORTED_INVALID_ROUTE
        assert calls["publisher"] == 0

    def test_missing_human_decision_pauses_for_human(self) -> None:
        overrides, calls = make_overrides(override_human=False)  # 用默认 human_approval 节点
        state = build_agent_graph(overrides).run(make_initial_state())
        assert state["status"] == STATUS_WAITING_HUMAN
        assert state["history"][-1] == NODE_HUMAN_APPROVAL
        assert calls["publisher"] == 0


class TestRetryBudget:
    def test_max_retries_aborts_run(self) -> None:
        overrides, calls = make_overrides(compliance_failures=99)
        state = build_agent_graph(overrides).run(make_initial_state(max_retries=3))
        assert state["status"] == STATUS_ABORTED_MAX_RETRIES
        # 3 次回退后第 4 次失败触发中止：script 与 compliance 各执行 4 次
        assert state["retry_count"] == 4
        assert calls["compliance"] == 4
        assert state["history"].count(NODE_SCRIPT_GENERATOR) == 4
        assert calls["storyboard"] == 0
        assert calls["publisher"] == 0
        assert len(state["errors"]) == 4

    def test_shared_budget_across_gates(self) -> None:
        # fact 失败 2 次 + compliance 失败 2 次，共享预算 max_retries=3 → 中止
        overrides, _calls = make_overrides(fact_failures=2, compliance_failures=99)
        state = build_agent_graph(overrides).run(make_initial_state(max_retries=3))
        assert state["status"] == STATUS_ABORTED_MAX_RETRIES
        assert state["retry_count"] == 4


class TestDurationConsistency:
    def test_within_tolerance_passes(self) -> None:
        ok, _detail = check_duration_consistency(
            {"target_duration_s": 60.0}, {"total_duration_s": 63.0}
        )
        assert ok is True

    def test_beyond_tolerance_fails(self) -> None:
        ok, detail = check_duration_consistency(
            {"target_duration_s": 60.0}, {"total_duration_s": 75.0}
        )
        assert ok is False
        assert detail["reason"] == "duration_mismatch"
        assert detail["diff_s"] == 15.0

    def test_total_summed_from_shots_when_missing(self) -> None:
        storyboard = {
            "shots": [
                {"index": 0, "start_s": 0.0, "end_s": 20.0},
                {"index": 1, "start_s": 20.0, "end_s": 45.0},
            ]
        }
        ok, detail = check_duration_consistency({"target_duration_s": 45.0}, storyboard)
        assert ok is True
        assert detail["storyboard_total_s"] == 45.0

    def test_missing_inputs_fail(self) -> None:
        ok, detail = check_duration_consistency(None, None)
        assert ok is False
        assert detail["reason"] == "missing_script_or_storyboard"


class TestRunDemo:
    def test_run_demo_completes_end_to_end(self) -> None:
        state = run_demo()
        assert state["status"] == STATUS_COMPLETED
        assert state["history"] == NODE_ORDER
        assert state["retry_count"] == 0
        assert state["fact_result"]["passed"] is True
        assert state["compliance_result"]["passed"] is True


class TestRuleBasedDemoNodes:
    """规则演示节点测试（读取 agent/policies/ 真实策略文件）。"""

    def test_compliance_blocks_banned_expression(self) -> None:
        state: AgentState = {"humanized": {"text": "喝它减肥瘦身，轻松掉秤"}}
        result = compliance_reviewer.run(state)["compliance_result"]
        assert result["passed"] is False
        categories = {v["category"] for v in result["violations"]}
        assert "减肥功效承诺" in categories

    def test_compliance_restricted_expression_is_warning_only(self) -> None:
        state: AgentState = {"humanized": {"text": "控糖姐妹的办公室下午茶记录"}}
        result = compliance_reviewer.run(state)["compliance_result"]
        assert result["passed"] is True
        assert any(w["expression"] == "控糖" for w in result["warnings"])

    def test_compliance_passes_clean_text(self) -> None:
        state: AgentState = {
            "humanized": {"text": "早餐来一杯轻醒希腊酸奶，口感浓，配麦片很省心。"}
        }
        result = compliance_reviewer.run(state)["compliance_result"]
        assert result["passed"] is True
        assert result["violations"] == []

    def test_fact_blocks_nutrition_numbers(self) -> None:
        state: AgentState = {
            "humanized": {"text": "每杯含10g蛋白质，热量只有80千卡"},
            "script": {"claims_used": []},
        }
        result = fact_regression.run(state)["fact_result"]
        assert result["passed"] is False
        codes = {v["code"] for v in result["violations"]}
        assert "unverified_nutrition_number" in codes

    def test_fact_blocks_forbidden_interpretation(self) -> None:
        state: AgentState = {
            "humanized": {"text": "这款是无糖酸奶，放心喝"},
            "script": {"claims_used": []},
        }
        result = fact_regression.run(state)["fact_result"]
        assert result["passed"] is False
        assert any(v["code"] == "forbidden_interpretation" for v in result["violations"])

    def test_fact_blocks_unknown_claim(self) -> None:
        state: AgentState = {
            "script": {"text": "日常一杯。", "claims_used": ["缓解便秘"]},
        }
        result = fact_regression.run(state)["fact_result"]
        assert result["passed"] is False
        assert any(v["code"] == "unknown_claim" for v in result["violations"])

    def test_fact_passes_clean_text(self) -> None:
        state: AgentState = {
            "humanized": {"text": "下午犯困的时候来一杯蓝莓味酸奶。"},
            "script": {"claims_used": ["高蛋白"]},
        }
        result = fact_regression.run(state)["fact_result"]
        assert result["passed"] is True


class TestLocalDataDemoNodes:
    """本地数据演示节点测试（读取 Stage 1/3 已验收的真实数据文件）。"""

    def test_brief_analyzer_reads_default_brief_file(self) -> None:
        if not brief_analyzer.DEFAULT_BRIEF_PATH.exists():
            pytest.skip("默认 Brief 数据文件不存在")
        out = brief_analyzer.run({})["brief_analysis"]
        assert out["brand_name"] == "轻醒"
        assert "高蛋白" in out["allowed_claims"]
        assert out["blockers"], "阻塞级缺失信息必须非空透传"
        assert out["source"] == "data/processed/qingxing_brief.json"

    def test_style_distiller_reads_default_timelines(self) -> None:
        if not creator_style_distiller.DEFAULT_TIMELINES_PATH.exists():
            pytest.skip("默认时间线数据文件不存在")
        raw = json.loads(creator_style_distiller.DEFAULT_TIMELINES_PATH.read_text(encoding="utf-8"))
        formats_in_data = {t.get("primary_format") for t in raw.get("timelines", [])}
        out = creator_style_distiller.run({})["style_profile"]
        assert len(out["reference_videos"]) == len(raw.get("timelines", [])) == 3
        assert out["dominant_format"] in formats_in_data
        low, high = out["duration_range_s"]
        assert 0 < low <= high
