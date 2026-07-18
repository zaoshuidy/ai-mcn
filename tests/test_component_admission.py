"""组件准入状态机与评分门禁测试。全部离线运行，不依赖真实第三方组件。"""

from __future__ import annotations

from pathlib import Path

from src.component_admission import (
    APPROVE_MIN_SCORE,
    MAX_APPROVED_COMPONENTS,
    ComponentStatus,
    check_registry_consistency,
    compute_weighted_score,
    evaluate_admission,
    is_legal_transition,
    load_candidates,
    load_yaml_list,
)

ROOT = Path(__file__).resolve().parent.parent

FULL_DIMS = {
    "business_fit": 100,
    "input_output_compatibility": 100,
    "reproducibility": 100,
    "maintenance_score": 100,
    "community_score": 100,
    "license_score": 100,
    "security_score": 100,
    "modification_cost": 100,
    "replaceability": 100,
}

APPROVED_KWARGS = {
    "license_verified": True,
    "license_value": "MIT",
    "security_review_passed": True,
    "read_only_mode_possible": True,
    "bypasses_captcha_or_risk_control": False,
    "auto_interaction_can_be_disabled": True,
    "poc_passed": True,
    "has_fallback": True,
}


# ---------- 状态机 ----------


def test_pending_to_under_review_legal() -> None:
    assert is_legal_transition("pending", "under_review")


def test_pending_to_approved_illegal() -> None:
    """批准路径不得跳级：pending 不能直接 approved。"""
    assert not is_legal_transition("pending", "approved")


def test_pending_to_poc_required_illegal() -> None:
    assert not is_legal_transition("pending", "poc_required")


def test_pending_to_rejected_legal() -> None:
    assert is_legal_transition("pending", "rejected")


def test_under_review_to_poc_required_legal() -> None:
    assert is_legal_transition("under_review", "poc_required")


def test_under_review_to_reference_only_legal() -> None:
    assert is_legal_transition("under_review", "reference_only")


def test_under_review_to_rejected_legal() -> None:
    assert is_legal_transition("under_review", "rejected")


def test_under_review_to_approved_illegal() -> None:
    """under_review 必须先进入 poc_required，不能直接 approved。"""
    assert not is_legal_transition("under_review", "approved")


def test_poc_required_to_approved_legal() -> None:
    assert is_legal_transition("poc_required", "approved")


def test_poc_required_to_rejected_legal() -> None:
    assert is_legal_transition("poc_required", "rejected")


def test_approved_to_rejected_legal() -> None:
    """approved 只能被吊销为 rejected。"""
    assert is_legal_transition("approved", "rejected")


def test_approved_to_reference_only_illegal() -> None:
    assert not is_legal_transition("approved", "reference_only")


def test_rejected_to_under_review_legal() -> None:
    """满足重评条件后可重新进入 under_review。"""
    assert is_legal_transition("rejected", "under_review")


def test_rejected_to_approved_illegal() -> None:
    assert not is_legal_transition("rejected", "approved")


def test_invalid_status_string() -> None:
    assert not is_legal_transition("pending", "not_a_status")
    assert not is_legal_transition("not_a_status", "pending")


# ---------- 加权评分 ----------


def test_weighted_score_full() -> None:
    assert compute_weighted_score(FULL_DIMS) == 100


def test_weighted_score_zero() -> None:
    assert compute_weighted_score({k: 0 for k in FULL_DIMS}) == 0


def test_weighted_score_single_dimension() -> None:
    dims = {k: 0 for k in FULL_DIMS}
    dims["business_fit"] = 100
    assert compute_weighted_score(dims) == 25


def test_weighted_score_missing_dimension_counts_zero() -> None:
    assert compute_weighted_score({"business_fit": 100}) == 25


def test_weighted_score_none_counts_zero() -> None:
    dims = dict(FULL_DIMS)
    dims["security_score"] = None
    assert compute_weighted_score(dims) == 90


def test_weighted_score_weights_sum_100() -> None:
    from src.component_admission import SCORECARD_WEIGHTS

    assert sum(SCORECARD_WEIGHTS.values()) == 100


# ---------- 准入判定 ----------


def test_bypass_captcha_direct_rejected() -> None:
    """存在绕过验证码/风控逻辑：无论分数多高直接 rejected。"""
    kwargs = {**APPROVED_KWARGS, "bypasses_captcha_or_risk_control": True}
    verdict = evaluate_admission(dimensions=FULL_DIMS, **kwargs)
    assert verdict.status == ComponentStatus.REJECTED
    assert any("绕过" in r or "风控" in r for r in verdict.reasons)


def test_score_below_85_rejected() -> None:
    dims = {k: 80 for k in FULL_DIMS}
    verdict = evaluate_admission(dimensions=dims, **APPROVED_KWARGS)
    assert verdict.score == 80
    assert verdict.status == ComponentStatus.REJECTED


def test_score_85_to_89_reference_only() -> None:
    dims = {k: 85 for k in FULL_DIMS}
    verdict = evaluate_admission(dimensions=dims, **APPROVED_KWARGS)
    assert verdict.score == 85
    assert verdict.status == ComponentStatus.REFERENCE_ONLY


def test_score_90_all_conditions_approved() -> None:
    dims = {k: 90 for k in FULL_DIMS}
    verdict = evaluate_admission(dimensions=dims, **APPROVED_KWARGS)
    assert verdict.score == 90
    assert verdict.status == ComponentStatus.APPROVED


def test_score_90_without_license_not_approved() -> None:
    """许可证不明确不能 approved。"""
    kwargs = {**APPROVED_KWARGS, "license_verified": False, "license_value": ""}
    verdict = evaluate_admission(dimensions={k: 95 for k in FULL_DIMS}, **kwargs)
    assert verdict.status != ComponentStatus.APPROVED
    assert any("许可证" in r for r in verdict.reasons)


def test_score_90_without_poc_goes_poc_required() -> None:
    """分数达标但 POC 未通过：状态保持 poc_required，不得 approved。"""
    kwargs = {**APPROVED_KWARGS, "poc_passed": False}
    verdict = evaluate_admission(dimensions={k: 95 for k in FULL_DIMS}, **kwargs)
    assert verdict.status == ComponentStatus.POC_REQUIRED


def test_score_90_undisableable_interaction_not_approved() -> None:
    """存在无法关闭的自动互动能力：不能 approved。"""
    kwargs = {**APPROVED_KWARGS, "auto_interaction_can_be_disabled": False}
    verdict = evaluate_admission(dimensions={k: 95 for k in FULL_DIMS}, **kwargs)
    assert verdict.status != ComponentStatus.APPROVED
    assert any("互动" in r for r in verdict.reasons)


def test_score_90_without_fallback_not_approved() -> None:
    kwargs = {**APPROVED_KWARGS, "has_fallback": False}
    verdict = evaluate_admission(dimensions={k: 95 for k in FULL_DIMS}, **kwargs)
    assert verdict.status != ComponentStatus.APPROVED
    assert any("替代" in r for r in verdict.reasons)


def test_score_90_failed_security_not_approved() -> None:
    kwargs = {**APPROVED_KWARGS, "security_review_passed": False}
    verdict = evaluate_admission(dimensions={k: 95 for k in FULL_DIMS}, **kwargs)
    assert verdict.status != ComponentStatus.APPROVED


def test_score_90_not_read_only_not_approved() -> None:
    kwargs = {**APPROVED_KWARGS, "read_only_mode_possible": False}
    verdict = evaluate_admission(dimensions={k: 95 for k in FULL_DIMS}, **kwargs)
    assert verdict.status != ComponentStatus.APPROVED


# ---------- registry 一致性 ----------


def test_consistency_approved_over_limit() -> None:
    approved = [{"component_id": f"C-{i}"} for i in range(MAX_APPROVED_COMPONENTS + 1)]
    problems = check_registry_consistency([], approved, [])
    assert any("上限" in p for p in problems)


def test_consistency_approved_missing_from_yaml() -> None:
    candidates = [
        {"component_id": "C-1", "status": "approved", "final_score": "95"},
    ]
    problems = check_registry_consistency(candidates, [], [])
    assert any("approved_components.yaml" in p for p in problems)


def test_consistency_rejected_missing_from_yaml() -> None:
    candidates = [
        {"component_id": "C-1", "status": "rejected", "final_score": "70"},
    ]
    problems = check_registry_consistency(candidates, [], [])
    assert any("rejected_components.yaml" in p for p in problems)


def test_consistency_approved_below_min_score() -> None:
    candidates = [
        {"component_id": "C-1", "status": "approved", "final_score": "80"},
    ]
    approved = [{"component_id": "C-1"}]
    problems = check_registry_consistency(candidates, approved, [])
    assert any(str(APPROVE_MIN_SCORE) in p for p in problems)


def test_consistency_example_row_skipped() -> None:
    candidates = [{"component_id": "EXAMPLE-000", "status": "example_only"}]
    assert check_registry_consistency(candidates, [], []) == []


# ---------- 真实 registry 文件 ----------


def test_real_registry_consistent() -> None:
    candidates = load_candidates(ROOT / "registry/component_candidates.csv")
    approved = load_yaml_list(ROOT / "registry/approved_components.yaml", "approved_components")
    rejected = load_yaml_list(ROOT / "registry/rejected_components.yaml", "rejected_components")
    assert check_registry_consistency(candidates, approved, rejected) == []


def test_real_registry_candidates_status() -> None:
    """CAND-001~004 全部 rejected；CAND-005~010 为 D-0008 授权的 POC 工具；无 approved。"""
    candidates = load_candidates(ROOT / "registry/component_candidates.csv")
    approved = load_yaml_list(ROOT / "registry/approved_components.yaml", "approved_components")
    real = {r["component_id"]: r for r in candidates if r.get("status") != "example_only"}
    assert len(real) == 10
    for cid in ["CAND-001", "CAND-002", "CAND-003", "CAND-004"]:
        assert real[cid]["status"] == "rejected"
    for cid in ["CAND-005", "CAND-006", "CAND-007", "CAND-008", "CAND-009", "CAND-010"]:
        assert real[cid]["status"] == "poc_required"
        assert "D-0008" in real[cid]["review_notes"] or int(real[cid]["final_score"]) >= 90
    assert approved == []


def test_real_registry_scores_match_scorecard() -> None:
    """登记表 9 个分项加权分之和等于 final_score，且含预研初评分（初评/最终分离）。"""
    candidates = load_candidates(ROOT / "registry/component_candidates.csv")
    real = [r for r in candidates if r.get("status") != "example_only"]
    dim_keys = [
        "business_fit", "input_output_compatibility", "reproducibility",
        "maintenance_score", "community_score", "license_score",
        "security_score", "modification_cost", "replaceability",
    ]
    for row in real:
        sub_scores = [int(row[k]) for k in dim_keys]
        assert sum(sub_scores) == int(row["final_score"]), row["component_id"]
        if row["component_id"] in {"CAND-001", "CAND-002", "CAND-003", "CAND-004"}:
            assert "预研初评分" in row["review_notes"]


def test_weighted_score_matches_scorecard_cand_001() -> None:
    """compute_weighted_score 以 0-100 原始分复算 CAND-001 总分（对评分卡交叉验证）。"""
    dims = {
        "business_fit": 92, "input_output_compatibility": 87, "reproducibility": 80,
        "maintenance_score": 90, "community_score": 100, "license_score": 0,
        "security_score": 30, "modification_cost": 80, "replaceability": 80,
    }
    assert compute_weighted_score(dims) == 74


def test_rejected_entries_have_reasons_and_conditions() -> None:
    rejected = load_yaml_list(ROOT / "registry/rejected_components.yaml", "rejected_components")
    assert len(rejected) == 4
    for entry in rejected:
        assert entry["reject_reasons"], entry["component_id"]
        assert entry["review_report"], entry["component_id"]
        assert "re_evaluation_condition" in entry
