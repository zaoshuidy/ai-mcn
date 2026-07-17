"""第三方组件准入状态机与评分门禁。

承载 Stage 2 组件治理规则：
- 状态流转：pending → under_review → poc_required → approved；
  under_review 之后可 rejected / reference_only；
- 评分：9 维加权（见 SCORECARD_WEIGHTS），初评分与最终准入分分离；
- 准入规则：许可证不明确不能 approved；绕过验证码/风控逻辑直接 rejected；
  无法关闭的自动互动能力不能 approved；approved 最多 2 个且必须 POC 通过。

本模块只做判定与校验，不修改 registry 文件；registry 更新由人工/执行流程写入。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml


class ComponentStatus(str, Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    POC_REQUIRED = "poc_required"
    APPROVED = "approved"
    REFERENCE_ONLY = "reference_only"
    REJECTED = "rejected"


# 合法状态流转（批准路径不得跳级；拒绝/参考路径自 under_review 起可判定）
LEGAL_TRANSITIONS: dict[ComponentStatus, set[ComponentStatus]] = {
    ComponentStatus.PENDING: {ComponentStatus.UNDER_REVIEW, ComponentStatus.REJECTED},
    ComponentStatus.UNDER_REVIEW: {
        ComponentStatus.POC_REQUIRED,
        ComponentStatus.REFERENCE_ONLY,
        ComponentStatus.REJECTED,
    },
    ComponentStatus.POC_REQUIRED: {
        ComponentStatus.APPROVED,
        ComponentStatus.REFERENCE_ONLY,
        ComponentStatus.REJECTED,
    },
    ComponentStatus.APPROVED: {ComponentStatus.REJECTED},  # 吊销
    ComponentStatus.REFERENCE_ONLY: {ComponentStatus.UNDER_REVIEW, ComponentStatus.REJECTED},
    ComponentStatus.REJECTED: {ComponentStatus.UNDER_REVIEW},  # 重新评估
}

SCORECARD_WEIGHTS: dict[str, int] = {
    "business_fit": 25,
    "input_output_compatibility": 15,
    "reproducibility": 10,
    "maintenance_score": 10,
    "community_score": 10,
    "license_score": 10,
    "security_score": 10,
    "modification_cost": 5,
    "replaceability": 5,
}

APPROVE_MIN_SCORE = 90
REFERENCE_MIN_SCORE = 85
MAX_APPROVED_COMPONENTS = 2

REVIEW_REQUIRED_FIELDS = [
    "component_id",
    "name",
    "category",
    "purpose",
    "repository",
    "source_url",
    "license",
    "final_score",
    "status",
    "review_notes",
]


@dataclass
class AdmissionVerdict:
    """准入判定结果。"""

    score: int
    status: ComponentStatus
    reasons: list[str] = field(default_factory=list)


def is_legal_transition(from_status: str, to_status: str) -> bool:
    """检查状态流转是否合法。"""
    try:
        src = ComponentStatus(from_status)
        dst = ComponentStatus(to_status)
    except ValueError:
        return False
    return dst in LEGAL_TRANSITIONS[src]


def compute_weighted_score(dimensions: dict[str, int | float | None]) -> int:
    """按评分卡权重计算加权总分（0-100）。缺失维度按 0 计。"""
    total = 0.0
    for key, weight in SCORECARD_WEIGHTS.items():
        value = dimensions.get(key) or 0
        total += float(value) * weight / 100
    return round(total)


def evaluate_admission(
    *,
    dimensions: dict[str, int | float | None],
    license_verified: bool,
    license_value: str,
    security_review_passed: bool,
    read_only_mode_possible: bool,
    bypasses_captcha_or_risk_control: bool,
    auto_interaction_can_be_disabled: bool,
    poc_passed: bool,
    has_fallback: bool,
    current_status: str = ComponentStatus.PENDING.value,
) -> AdmissionVerdict:
    """按准入规则判定组件状态与分数。

    规则优先级：绕过风控直接 rejected → 分数定档 → approved 附加条件。
    """
    score = compute_weighted_score(dimensions)
    reasons: list[str] = []

    if bypasses_captcha_or_risk_control:
        return AdmissionVerdict(
            score=score,
            status=ComponentStatus.REJECTED,
            reasons=["存在绕过验证码或平台风控逻辑：直接 rejected"],
        )

    if score < REFERENCE_MIN_SCORE:
        reasons.append(f"总分 {score} < {REFERENCE_MIN_SCORE}")
        if not license_verified or not license_value:
            reasons.append("许可证缺失或未核实")
        return AdmissionVerdict(score=score, status=ComponentStatus.REJECTED, reasons=reasons)

    if score < APPROVE_MIN_SCORE:
        return AdmissionVerdict(
            score=score,
            status=ComponentStatus.REFERENCE_ONLY,
            reasons=[
                f"总分 {score} 处于 {REFERENCE_MIN_SCORE}-{APPROVE_MIN_SCORE - 1} 区间，仅借鉴方法"
            ],
        )

    # score >= 90：逐项核查 approved 附加条件
    blockers: list[str] = []
    if not license_verified or not license_value:
        blockers.append("许可证不明确")
    if not security_review_passed:
        blockers.append("安全审查未通过")
    if not read_only_mode_possible:
        blockers.append("只读模式不可实现")
    if not auto_interaction_can_be_disabled:
        blockers.append("存在无法关闭的自动互动能力")
    if not poc_passed:
        blockers.append("POC 未通过")
    if not has_fallback:
        blockers.append("缺少替代方案")

    if blockers:
        fallback_status = (
            ComponentStatus.POC_REQUIRED if not poc_passed else ComponentStatus.REFERENCE_ONLY
        )
        return AdmissionVerdict(
            score=score,
            status=fallback_status,
            reasons=[f"总分 {score} 达标但：{b}" for b in blockers],
        )

    return AdmissionVerdict(
        score=score,
        status=ComponentStatus.APPROVED,
        reasons=[f"总分 {score} ≥ {APPROVE_MIN_SCORE} 且全部附加条件满足"],
    )


def load_candidates(csv_path: str | Path) -> list[dict]:
    """读取候选组件登记表。"""
    with Path(csv_path).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_yaml_list(yaml_path: str | Path, key: str) -> list:
    """读取 approved/rejected 清单。"""
    data = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
    return (data or {}).get(key, [])


def check_registry_consistency(
    candidates: list[dict],
    approved: list,
    rejected: list,
) -> list[str]:
    """校验登记表与批准/拒绝清单的一致性，返回问题列表。"""
    problems: list[str] = []
    if len(approved) > MAX_APPROVED_COMPONENTS:
        problems.append(f"approved 组件数 {len(approved)} 超过上限 {MAX_APPROVED_COMPONENTS}")

    approved_ids = {c.get("component_id") for c in approved if isinstance(c, dict)}
    rejected_ids = {c.get("component_id") for c in rejected if isinstance(c, dict)}
    real_rows = [r for r in candidates if r.get("status") != "example_only"]

    for row in real_rows:
        cid = row.get("component_id", "")
        status = row.get("status", "")
        if status == ComponentStatus.APPROVED.value and cid not in approved_ids:
            problems.append(f"{cid} 登记为 approved 但未写入 approved_components.yaml")
        if status == ComponentStatus.REJECTED.value and cid not in rejected_ids:
            problems.append(f"{cid} 登记为 rejected 但未写入 rejected_components.yaml")
        if status == ComponentStatus.APPROVED.value:
            try:
                if float(row.get("final_score") or 0) < APPROVE_MIN_SCORE:
                    problems.append(f"{cid} approved 但分数不足 {APPROVE_MIN_SCORE}")
            except (TypeError, ValueError):
                problems.append(f"{cid} final_score 无法解析")
    return problems
