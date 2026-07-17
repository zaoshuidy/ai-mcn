"""达人搜索策略生成（Stage 2）。

从 Stage 1 结构化 Brief 生成 4 组搜索关键词并输出搜索计划：
- 人群型：来自 target_audience.interests 与人群画像；
- 场景型：来自 usage_scenarios；
- 内容型：来自 creator_search_profile 的内容形式要求；
- 产品邻近型：来自产品卖点的邻近内容词（不宣称功效）。

合规约束（与 config/creator_search_rules.yaml 一致）：
- “控糖”只能作为内容与受众搜索词，不得用于推断产品具备降糖能力；
- 搜索计划不得包含功效承诺类表述；
- POC 执行子集受 poc_limits 上限约束。
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

DEFAULT_RULES_PATH = Path("config/creator_search_rules.yaml")
DEFAULT_PLAN_PATH = Path("data/processed/creator_search_plan.json")

SUGAR_CONTROL_NOTE = (
    "仅作为内容/受众搜索词：用于找到关注控糖饮食的人群，"
    "不得用于推断或宣称产品具备降糖、控制血糖或治疗能力"
)


class QueryType(str, Enum):
    """搜索词类型。"""

    AUDIENCE = "audience"  # 人群型
    SCENARIO = "scenario"  # 场景型
    CONTENT = "content"  # 内容型
    PRODUCT_ADJACENT = "product_adjacent"  # 产品邻近型


class SearchQuery(BaseModel):
    """单条搜索词及其业务说明。"""

    query: str
    query_type: QueryType
    business_reason: str
    expected_creator_type: str
    risk: str = ""
    priority: int = Field(..., ge=1, description="1 为最高优先级")
    max_results: int = Field(..., ge=1)


class SearchPlan(BaseModel):
    """完整搜索计划：4 组关键词 + POC 执行子集 + 上限快照。"""

    brief_id: str
    generated_from: str = Field(description="Brief 来源相对路径")
    groups: dict[str, list[SearchQuery]]
    poc_queries: list[SearchQuery] = Field(
        default_factory=list, description="POC 实际执行子集（受 poc_limits 约束）"
    )
    poc_limits: dict[str, int] = Field(default_factory=dict)
    compliance_notes: list[str] = Field(default_factory=list)

    @property
    def all_queries(self) -> list[SearchQuery]:
        return [q for queries in self.groups.values() for q in queries]


def load_search_rules(rules_path: str | Path = DEFAULT_RULES_PATH) -> dict[str, Any]:
    """读取搜索与 POC 规则。"""
    return yaml.safe_load(Path(rules_path).read_text(encoding="utf-8"))


def _audience_queries(max_results: int) -> list[SearchQuery]:
    return [
        SearchQuery(
            query="健身女孩饮食",
            query_type=QueryType.AUDIENCE,
            business_reason="目标人群含健身标签，饮食内容是健身女性达人的高频赛道",
            expected_creator_type="健身生活方式博主",
            risk="需排除以器械教学为主、几乎不涉及饮食内容的账号",
            priority=1,
            max_results=max_results,
        ),
        SearchQuery(
            query="都市女生轻食",
            query_type=QueryType.AUDIENCE,
            business_reason="贴合 22-35 岁城市女性与轻食兴趣标签",
            expected_creator_type="都市轻食/生活方式博主",
            risk="需排除纯探店账号，居家自炊内容更利于产品自然植入",
            priority=2,
            max_results=max_results,
        ),
        SearchQuery(
            query="上班族健康饮食",
            query_type=QueryType.AUDIENCE,
            business_reason="目标人群为城市上班族，关注效率生活下的健康饮食",
            expected_creator_type="上班族生活方式博主",
            risk="内容偏资讯科普的账号商单自然度较低，需人工判断",
            priority=3,
            max_results=max_results,
        ),
        SearchQuery(
            query="控糖饮食记录",
            query_type=QueryType.AUDIENCE,
            business_reason="目标人群兴趣标签含控糖，可找到记录控糖饮食的受众重合达人",
            expected_creator_type="控糖饮食记录博主",
            risk=SUGAR_CONTROL_NOTE,
            priority=4,
            max_results=max_results,
        ),
    ]


def _scenario_queries(max_results: int) -> list[SearchQuery]:
    return [
        SearchQuery(
            query="上班族早餐",
            query_type=QueryType.SCENARIO,
            business_reason="早餐是 Brief 第一优先级使用场景，上班族早餐内容与目标人群重合",
            expected_creator_type="早餐/带饭类生活博主",
            risk="需排除纯宝宝辅食类账号（人群不符）",
            priority=1,
            max_results=max_results,
        ),
        SearchQuery(
            query="运动后加餐",
            query_type=QueryType.SCENARIO,
            business_reason="运动后是 Brief 第二优先级场景，与健身人群重合",
            expected_creator_type="健身日常/饮食记录博主",
            risk="不得引导达人作出补充蛋白质克数等未经证实的功效表述",
            priority=2,
            max_results=max_results,
        ),
        SearchQuery(
            query="办公室下午茶",
            query_type=QueryType.SCENARIO,
            business_reason="下午茶是 Brief 第三优先级场景，办公室情境贴合上班族人群",
            expected_creator_type="办公室日常/零食分享博主",
            risk="需排除纯咖啡茶饮测评账号（赛道偏离）",
            priority=3,
            max_results=max_results,
        ),
        SearchQuery(
            query="一人食早餐",
            query_type=QueryType.SCENARIO,
            business_reason="一人食是城市年轻女性的典型内容情境，利于酸奶自然出镜",
            expected_creator_type="一人食/独居生活博主",
            risk="内容调性差异大，需人工确认与品牌调性匹配",
            priority=4,
            max_results=max_results,
        ),
    ]


def _content_queries(max_results: int) -> list[SearchQuery]:
    return [
        SearchQuery(
            query="一周早餐Vlog",
            query_type=QueryType.CONTENT,
            business_reason="Vlog 形式自然种草空间大，与 Brief 的非硬广要求一致",
            expected_creator_type="生活记录 Vlog 博主",
            risk="Vlog 更新频率不稳定，需确认近期活跃度",
            priority=2,
            max_results=max_results,
        ),
        SearchQuery(
            query="打工人吃什么",
            query_type=QueryType.CONTENT,
            business_reason="打工人饮食是高流量内容赛道，与上班族人群高度重合",
            expected_creator_type="打工人饮食记录博主",
            risk="部分账号偏外卖测评，与酸奶场景匹配度需人工判断",
            priority=1,
            max_results=max_results,
        ),
        SearchQuery(
            query="轻食一日三餐",
            query_type=QueryType.CONTENT,
            business_reason="一日三餐结构利于呈现早餐与下午茶两个核心场景",
            expected_creator_type="轻食记录博主",
            risk="需排除纯减重打卡账号（易触碰减肥功效红线）",
            priority=3,
            max_results=max_results,
        ),
        SearchQuery(
            query="健身日常Vlog",
            query_type=QueryType.CONTENT,
            business_reason="健身日常与运动后场景天然衔接，目标人群重合",
            expected_creator_type="健身 Vlog 博主",
            risk="需排除以补剂带货为主的账号（竞品与调性风险）",
            priority=4,
            max_results=max_results,
        ),
    ]


def _product_adjacent_queries(max_results: int) -> list[SearchQuery]:
    return [
        SearchQuery(
            query="高蛋白早餐",
            query_type=QueryType.PRODUCT_ADJACENT,
            business_reason="高蛋白是品牌方卖点（brand_claim），搜索邻近内容找受众重合达人",
            expected_creator_type="高蛋白饮食分享博主",
            risk="高蛋白为 brand_claim 而非已证实数据，达人内容不得虚构营养数值",
            priority=1,
            max_results=max_results,
        ),
        SearchQuery(
            query="希腊酸奶吃法",
            query_type=QueryType.PRODUCT_ADJACENT,
            business_reason="产品即希腊酸奶，同类吃法内容的达人对品类认知成熟",
            expected_creator_type="酸奶/乳制品吃法分享博主",
            risk="需排查是否已有明显同类酸奶竞品合作",
            priority=2,
            max_results=max_results,
        ),
        SearchQuery(
            query="酸奶碗",
            query_type=QueryType.PRODUCT_ADJACENT,
            business_reason="酸奶碗是小红书高热度内容形式，与产品形态直接相关",
            expected_creator_type="酸奶碗/早餐摆盘博主",
            risk="内容同质化高，需人工判断达人个人风格辨识度",
            priority=3,
            max_results=max_results,
        ),
        SearchQuery(
            query="低糖零食分享",
            query_type=QueryType.PRODUCT_ADJACENT,
            business_reason="低糖零食受众与控糖/轻食人群重合，适合下午茶场景",
            expected_creator_type="低糖零食测评博主",
            risk="低糖为内容标签，不得延伸为产品降糖功效表述",
            priority=4,
            max_results=max_results,
        ),
    ]


def select_poc_queries(
    queries: list[SearchQuery],
    rules: dict[str, Any],
) -> list[SearchQuery]:
    """按优先级选取 POC 执行子集，并应用 POC 每词结果上限。

    保证 4 个词来自不同组（每组取组内最高优先级），控制 POC 覆盖面。
    """
    limits = rules["poc_limits"]
    best_per_type: dict[QueryType, SearchQuery] = {}
    for q in sorted(queries, key=lambda x: x.priority):
        if q.query_type not in best_per_type:
            best_per_type[q.query_type] = q
    poc: list[SearchQuery] = []
    for q in sorted(best_per_type.values(), key=lambda x: x.priority):
        if len(poc) >= limits["max_queries"]:
            break
        capped = min(q.max_results, limits["max_results_per_query"])
        poc.append(q.model_copy(update={"max_results": capped}))
    return poc


def validate_plan_against_rules(plan: SearchPlan, rules: dict[str, Any]) -> list[str]:
    """校验搜索计划是否违反 POC 上限与合规约束，返回问题列表。"""
    problems: list[str] = []
    limits = rules["poc_limits"]
    plan_cap = limits.get("plan_max_results_per_query", 20)

    seen: set[str] = set()
    for q in plan.all_queries:
        if q.query in seen:
            problems.append(f"搜索词重复：{q.query}")
        seen.add(q.query)
        if q.max_results > plan_cap:
            problems.append(f"{q.query} max_results={q.max_results} 超过计划上限 {plan_cap}")

    if len(plan.poc_queries) > limits["max_queries"]:
        problems.append(
            f"POC 关键词数 {len(plan.poc_queries)} 超过上限 {limits['max_queries']}"
        )
    total = sum(q.max_results for q in plan.poc_queries)
    if total > limits["max_total_results"]:
        problems.append(f"POC 总结果数 {total} 超过上限 {limits['max_total_results']}")
    for q in plan.poc_queries:
        cap = limits["max_results_per_query"]
        if q.max_results > cap:
            problems.append(f"POC 词 {q.query} 结果数 {q.max_results} 超过上限 {cap}")

    if rules.get("compliance_constraints", {}).get("sugar_control_query_only"):
        for q in plan.all_queries:
            if "控糖" in q.query and q.query_type not in (QueryType.AUDIENCE, QueryType.CONTENT):
                problems.append(f"控糖搜索词 {q.query} 不允许出现在 {q.query_type.value} 组")
    return problems


def build_search_plan(
    brief: dict[str, Any],
    rules: Optional[dict[str, Any]] = None,
    *,
    generated_from: str = "data/processed/qingxing_brief.json",
) -> SearchPlan:
    """从结构化 Brief 生成搜索计划（4 组各 4 词，共 16 词）。"""
    if rules is None:
        rules = load_search_rules()
    plan_cap = rules["poc_limits"].get("plan_max_results_per_query", 20)

    groups = {
        "audience": _audience_queries(plan_cap),
        "scenario": _scenario_queries(plan_cap),
        "content": _content_queries(plan_cap),
        "product_adjacent": _product_adjacent_queries(plan_cap),
    }
    plan = SearchPlan(
        brief_id=brief.get("brief_id", ""),
        generated_from=generated_from,
        groups=groups,
        poc_limits=dict(rules["poc_limits"]),
        compliance_notes=[
            "控糖类搜索词仅用于内容与受众定位，不得推断产品降糖能力",
            "搜索策略不包含任何功效承诺表述；0 蔗糖不得解释为无糖",
            "达人受众画像为 AI 推测，必须带 evidence 与 confidence",
        ],
    )
    plan.poc_queries = select_poc_queries(plan.all_queries, rules)
    problems = validate_plan_against_rules(plan, rules)
    if problems:
        raise ValueError("搜索计划违反规则：" + "；".join(problems))
    return plan


def save_search_plan(plan: SearchPlan, path: str | Path = DEFAULT_PLAN_PATH) -> Path:
    """保存搜索计划 JSON。"""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return out


def main() -> None:
    """从默认 Brief 生成并保存搜索计划。"""
    brief = json.loads(Path("data/processed/qingxing_brief.json").read_text(encoding="utf-8"))
    plan = build_search_plan(brief)
    out = save_search_plan(plan)
    print(f"搜索计划已生成：{out}（{len(plan.all_queries)} 词，POC {len(plan.poc_queries)} 词）")


if __name__ == "__main__":
    main()
