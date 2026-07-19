"""节点：fact_regression（事实回检）。

契约
----
输入（读取 state 键）：
- ``humanized`` (dict)：agent.schemas.HumanizedScript（优先扫描其 ``text``）；
- ``script`` (dict)：agent.schemas.ScriptDraft（无 humanized 时回退扫描，
  且读取 ``claims_used`` 做卖点白名单核对）；
- ``brief_analysis`` (dict)：可选，提供允许卖点清单（与策略文件取并集）。
输出（写入 state 键）：
- ``fact_result`` (dict)：agent.schemas.FactCheckResult。
路由语义（由 agent.graph.route_after_fact 实现）：
- passed=True  → compliance_reviewer；
- passed=False → 回退 script_generator（累计超 max_retries 则中止）。

实现状态：可运行演示（确定性规则，策略文件 agent/policies/qingxing_claims.yaml）：
1. 未证实营养数值：文本中出现 数字+g/克/kcal/千卡/大卡/千焦 即判违规——
   品牌方营养成分表仍是 Brief 阻塞级缺失信息，任何营养数值均无 ProductEvidence；
2. 禁止解释方向：命中允许卖点的 forbidden_interpretations（如 0蔗糖→无糖）；
3. 未知卖点：claims_used 中出现策略白名单之外的卖点。
正式版应叠加 LLM 事实抽取与 ProductEvidence 库比对；本演示保证"无证据即拦截"
的下限，不保证召回全部事实错误。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from agent.schemas import CheckViolation, FactCheckResult
from agent.state import AgentState

POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"
CLAIMS_POLICY_PATH = POLICIES_DIR / "qingxing_claims.yaml"

#: 营养数值表达（无 ProductEvidence 时一律拦截）。
NUTRITION_NUMBER_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*(?:g|克|kcal|千卡|大卡|千焦|kj)", re.IGNORECASE
)

CHECKER_ID = "rule_based_demo_v1"


def load_claims_policy(path: Path = CLAIMS_POLICY_PATH) -> dict[str, Any]:
    """读取轻醒卖点策略文件。"""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def extract_check_text(state: AgentState) -> tuple[str, str]:
    """确定被检文本及其来源：humanized.text 优先，回退 script.text。"""
    humanized = state.get("humanized") or {}
    if humanized.get("text"):
        return humanized["text"], "humanized"
    script = state.get("script") or {}
    return script.get("text", ""), "script"


def check_facts(text: str, claims_used: list[str], policy: dict[str, Any]) -> list[CheckViolation]:
    """规则回检（纯函数，便于单测）。"""
    violations: list[CheckViolation] = []
    for match in NUTRITION_NUMBER_PATTERN.finditer(text):
        violations.append(
            CheckViolation(
                code="unverified_nutrition_number",
                category="未证实营养数据",
                expression=match.group(0),
                severity="high",
                detail="营养数值无品牌方 ProductEvidence（营养成分表仍属阻塞级缺失信息）",
                suggestion="删除数值或改为口感/场景描述，待品牌方提供营养成分表后回填",
            )
        )
    allowed = policy.get("allowed_claims", [])
    for claim in allowed:
        for bad in claim.get("forbidden_interpretations", []):
            if bad and bad in text:
                violations.append(
                    CheckViolation(
                        code="forbidden_interpretation",
                        category="卖点禁止解释方向",
                        expression=bad,
                        severity="high",
                        detail=f"卖点「{claim.get('claim')}」禁止解释为「{bad}」",
                        suggestion=f"恢复为「{claim.get('claim')}」原始表述或删除",
                    )
                )
    whitelist = {c.get("claim") for c in allowed}
    unknown = [c for c in claims_used if c not in whitelist]
    for claim in unknown:
        violations.append(
            CheckViolation(
                code="unknown_claim",
                category="卖点白名单",
                expression=claim,
                severity="high",
                detail="使用了策略白名单之外的卖点",
                suggestion="移除该卖点，或先经品牌方确认并更新 qingxing_claims.yaml",
            )
        )
    return violations


def run(state: AgentState) -> dict[str, Any]:
    """节点入口：规则演示实现。"""
    text, source = extract_check_text(state)
    script = state.get("script") or {}
    policy = load_claims_policy()
    violations = check_facts(text, script.get("claims_used", []), policy)
    result = FactCheckResult(
        passed=not violations,
        violations=violations,
        checker=CHECKER_ID,
        checked_text_source=source,
    )
    return {"fact_result": result.model_dump()}
