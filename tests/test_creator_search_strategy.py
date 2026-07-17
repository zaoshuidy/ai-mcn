"""达人搜索策略测试。全部离线运行，不执行真实搜索。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.creator_search_strategy import (
    QueryType,
    SearchPlan,
    build_search_plan,
    load_search_rules,
    select_poc_queries,
    validate_plan_against_rules,
)

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def brief() -> dict:
    path = ROOT / "data/processed/qingxing_brief.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rules() -> dict:
    return load_search_rules(ROOT / "config/creator_search_rules.yaml")


@pytest.fixture(scope="module")
def plan(brief: dict, rules: dict) -> SearchPlan:
    return build_search_plan(brief, rules)


# ---------- 计划结构 ----------


def test_plan_has_four_groups(plan: SearchPlan) -> None:
    assert set(plan.groups.keys()) == {"audience", "scenario", "content", "product_adjacent"}


def test_plan_sixteen_queries(plan: SearchPlan) -> None:
    assert len(plan.all_queries) == 16
    assert all(len(queries) == 4 for queries in plan.groups.values())


def test_plan_query_fields_complete(plan: SearchPlan) -> None:
    for q in plan.all_queries:
        assert q.query and q.business_reason and q.expected_creator_type
        assert q.priority >= 1
        assert q.max_results >= 1


def test_plan_no_duplicate_queries(plan: SearchPlan) -> None:
    queries = [q.query for q in plan.all_queries]
    assert len(queries) == len(set(queries))


def test_plan_matches_task_keywords(plan: SearchPlan) -> None:
    """16 个关键词与任务书规定一致。"""
    expected = {
        "健身女孩饮食", "都市女生轻食", "上班族健康饮食", "控糖饮食记录",
        "上班族早餐", "运动后加餐", "办公室下午茶", "一人食早餐",
        "一周早餐Vlog", "打工人吃什么", "轻食一日三餐", "健身日常Vlog",
        "高蛋白早餐", "希腊酸奶吃法", "酸奶碗", "低糖零食分享",
    }
    assert {q.query for q in plan.all_queries} == expected


def test_plan_brief_id_linked(plan: SearchPlan, brief: dict) -> None:
    assert plan.brief_id == brief["brief_id"]
    assert plan.generated_from == "data/processed/qingxing_brief.json"


# ---------- 合规约束 ----------


def test_sugar_control_only_in_audience_or_content(plan: SearchPlan) -> None:
    """控糖只能作为内容与受众搜索词。"""
    for q in plan.all_queries:
        if "控糖" in q.query:
            assert q.query_type in (QueryType.AUDIENCE, QueryType.CONTENT)


def test_sugar_control_risk_note(plan: SearchPlan) -> None:
    sugar = next(q for q in plan.all_queries if "控糖" in q.query)
    assert "不得" in sugar.risk and "降糖" in sugar.risk


def test_no_efficacy_claims_in_queries(plan: SearchPlan) -> None:
    """搜索词不得包含功效承诺表述。"""
    forbidden = ["减肥", "降糖", "降血糖", "治疗", "无糖", "不长胖"]
    for q in plan.all_queries:
        for word in forbidden:
            assert word not in q.query


# ---------- POC 子集与上限 ----------


def test_poc_queries_within_limits(plan: SearchPlan, rules: dict) -> None:
    limits = rules["poc_limits"]
    assert len(plan.poc_queries) <= limits["max_queries"]
    assert all(q.max_results <= limits["max_results_per_query"] for q in plan.poc_queries)
    assert sum(q.max_results for q in plan.poc_queries) <= limits["max_total_results"]


def test_poc_queries_cover_distinct_groups(plan: SearchPlan) -> None:
    types = {q.query_type for q in plan.poc_queries}
    assert len(types) == len(plan.poc_queries) == 4


def test_poc_queries_are_top_priority_per_group(plan: SearchPlan) -> None:
    for queries in plan.groups.values():
        top = min(queries, key=lambda q: q.priority)
        assert any(p.query == top.query for p in plan.poc_queries)


def test_select_poc_respects_custom_limit(plan: SearchPlan, rules: dict) -> None:
    custom = json.loads(json.dumps(rules))
    custom["poc_limits"]["max_queries"] = 2
    poc = select_poc_queries(plan.all_queries, custom)
    assert len(poc) == 2


def test_plan_limits_snapshot(plan: SearchPlan, rules: dict) -> None:
    expected = rules["poc_limits"]["max_creators_deep_read"]
    assert plan.poc_limits["max_creators_deep_read"] == expected
    assert plan.poc_limits["max_retries_per_request"] == 2


# ---------- 规则校验拦截 ----------


def test_validate_catches_duplicate(plan: SearchPlan, rules: dict) -> None:
    broken = plan.model_copy(deep=True)
    broken.groups["audience"][0].query = broken.groups["scenario"][0].query
    assert any("重复" in p for p in validate_plan_against_rules(broken, rules))


def test_validate_catches_excess_results(plan: SearchPlan, rules: dict) -> None:
    broken = plan.model_copy(deep=True)
    broken.groups["audience"][0].max_results = 999
    assert any("上限" in p for p in validate_plan_against_rules(broken, rules))


def test_validate_catches_sugar_in_wrong_group(plan: SearchPlan, rules: dict) -> None:
    broken = plan.model_copy(deep=True)
    broken.groups["product_adjacent"][0].query = "控糖酸奶"
    assert any("控糖" in p for p in validate_plan_against_rules(broken, rules))


def test_validate_catches_too_many_poc_queries(plan: SearchPlan, rules: dict) -> None:
    broken = plan.model_copy(deep=True)
    broken.poc_queries = broken.poc_queries + [broken.groups["scenario"][1]]
    assert any("POC" in p for p in validate_plan_against_rules(broken, rules))


def test_build_plan_rejects_internally_inconsistent_rules(brief: dict, rules: dict) -> None:
    """规则自相矛盾（4 词 × 10 条必然超过总上限）时构建必须失败，而不是静默放行。"""
    broken_rules = json.loads(json.dumps(rules))
    broken_rules["poc_limits"]["max_total_results"] = 15  # 4 组各 1 词 × 10 条 = 40 > 15
    with pytest.raises(ValueError, match="POC"):
        build_search_plan(brief, broken_rules)


# ---------- 落盘文件 ----------


def test_saved_plan_file_valid() -> None:
    path = ROOT / "data/processed/creator_search_plan.json"
    plan = SearchPlan.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert len(plan.groups) >= 4
    assert plan.poc_queries


def test_saved_plan_uses_relative_paths() -> None:
    text = (ROOT / "data/processed/creator_search_plan.json").read_text(encoding="utf-8")
    assert "D:\\" not in text and "D:/" not in text
