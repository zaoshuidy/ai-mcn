"""节点：compliance_reviewer（食品广告合规审查）。

契约
----
输入（读取 state 键）：
- ``humanized`` (dict)：agent.schemas.HumanizedScript（优先扫描其 ``text``）；
- ``script`` (dict)：agent.schemas.ScriptDraft（无 humanized 时回退扫描）。
输出（写入 state 键）：
- ``compliance_result`` (dict)：agent.schemas.ComplianceResult；
  ``violations`` 为阻断项，``warnings`` 为受限提示项（不阻断）。
路由语义（由 agent.graph.route_after_compliance 实现）：
- passed=True  → storyboard_generator；
- passed=False → 回退 script_generator（累计超 max_retries 则中止）。

实现状态：可运行演示（确定性规则，策略文件 agent/policies/banned_claims.yaml，
类目与广告法红线来自 Stage 1 已验收 Brief 的 compliance_rules）。规则覆盖
减肥/燃脂/掉秤/降糖/医疗/绝对化/夸大体验/竞品贬低等违禁表达；受限表达
（如"控糖"仅作人群标签）记为 warning。正式版应叠加品牌禁用词清单与
LLM 语义审查，本演示为确定性下限。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agent.schemas import CheckViolation, ComplianceResult
from agent.state import AgentState

POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"
BANNED_POLICY_PATH = POLICIES_DIR / "banned_claims.yaml"

CHECKER_ID = "rule_based_demo_v1"


def load_banned_policy(path: Path = BANNED_POLICY_PATH) -> dict[str, Any]:
    """读取违禁表达策略文件。"""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def check_compliance(
    text: str, policy: dict[str, Any]
) -> tuple[list[CheckViolation], list[CheckViolation]]:
    """违禁表达扫描（纯函数，便于单测）。返回 (violations, warnings)。"""
    violations: list[CheckViolation] = []
    warnings: list[CheckViolation] = []
    for rule in policy.get("categories", []):
        category = rule.get("category", "")
        for expression in rule.get("prohibited", []):
            if expression and expression in text:
                violations.append(
                    CheckViolation(
                        code="banned_expression",
                        category=category,
                        expression=expression,
                        severity=rule.get("severity", ""),
                        detail=rule.get("reason", ""),
                        suggestion=rule.get("replacement", ""),
                    )
                )
        for expression in rule.get("restricted", []):
            if expression and expression in text:
                warnings.append(
                    CheckViolation(
                        code="restricted_expression",
                        category=category,
                        expression=expression,
                        severity=rule.get("severity", ""),
                        detail=rule.get("reason", ""),
                        suggestion=rule.get("replacement", ""),
                    )
                )
    return violations, warnings


def run(state: AgentState) -> dict[str, Any]:
    """节点入口：规则演示实现。"""
    from agent.nodes.fact_regression import extract_check_text

    text, _source = extract_check_text(state)
    policy = load_banned_policy()
    violations, warnings = check_compliance(text, policy)
    result = ComplianceResult(
        passed=not violations,
        violations=violations,
        warnings=warnings,
        checker=CHECKER_ID,
        policy_version=str(policy.get("version", "")),
    )
    return {"compliance_result": result.model_dump()}
