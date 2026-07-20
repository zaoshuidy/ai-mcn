"""组件准入状态机与评分门禁测试。全部离线运行，不依赖真实第三方组件。"""

from __future__ import annotations

import json
from datetime import date, datetime
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
    """CAND-001~004 rejected；CAND-005~011 POC 工具（D-0008/D-0009 授权）；

    CAND-012~026 为 reference_only 参考组件（仅方法/结构参考，不打分）；无 approved。
    """
    candidates = load_candidates(ROOT / "registry/component_candidates.csv")
    approved = load_yaml_list(ROOT / "registry/approved_components.yaml", "approved_components")
    real = {r["component_id"]: r for r in candidates if r.get("status") != "example_only"}
    assert len(real) == 26
    expected_ids = {f"CAND-{number:03d}" for number in range(1, 27)}
    assert set(real) == expected_ids
    for cid in ["CAND-001", "CAND-002", "CAND-003", "CAND-004"]:
        assert real[cid]["status"] == "rejected"
    for cid in ["CAND-005", "CAND-006", "CAND-007", "CAND-008", "CAND-009", "CAND-010",
                "CAND-011"]:
        assert real[cid]["status"] == "poc_required"
        assert ("D-0008" in real[cid]["review_notes"] or "D-0009" in real[cid]["review_notes"]
                or int(real[cid]["final_score"]) >= 90)
    for cid in [f"CAND-{number:03d}" for number in range(12, 27)]:
        assert real[cid]["status"] == "reference_only"
    assert approved == []


def test_real_registry_scores_match_scorecard() -> None:
    """登记表 9 个分项加权分之和等于 final_score，且含预研初评分（初评/最终分离）。

    reference_only 参考组件按设计可不打分，分项与 final_score 均为 null。
    """
    candidates = load_candidates(ROOT / "registry/component_candidates.csv")
    real = [r for r in candidates if r.get("status") != "example_only"]
    dim_keys = [
        "business_fit", "input_output_compatibility", "reproducibility",
        "maintenance_score", "community_score", "license_score",
        "security_score", "modification_cost", "replaceability",
    ]
    for row in real:
        final_score = row["final_score"]
        if final_score == "null":
            assert row["status"] == "reference_only"
            assert (
                row["integration_type"]
                in {
                    "primary_skill_reference",
                    "primary_framework_reference",
                    "cli_runtime_reference",
                    "secondary_or_rejected",
                }
            )
            assert row["admission_status"] in {
                "primary",
                "rejected_as_primary",
                "demoted",
                "superseded",
            }
            assert all(row[k] == "null" for k in dim_keys), row["component_id"]
            continue
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


class TestHighStarReferenceAdmission:
    """高星参考登记与旧运行准入 status 分离的离线门禁。"""

    @staticmethod
    def real_rows() -> dict[str, dict]:
        candidates = load_candidates(ROOT / "registry/component_candidates.csv")
        return {
            row["component_id"]: row
            for row in candidates
            if row.get("component_id") != "EXAMPLE-000"
        }

    def test_schema_count_ids_and_enums(self) -> None:
        rows = self.real_rows()
        candidates = load_candidates(ROOT / "registry/component_candidates.csv")
        actual_ids = [
            row["component_id"]
            for row in candidates
            if row.get("component_id") != "EXAMPLE-000"
        ]
        expected_ids = {f"CAND-{number:03d}" for number in range(1, 27)}
        required = {
            "integration_type",
            "stars",
            "stars_observed_at",
            "license_spdx",
            "admission_status",
            "admission_reason",
        }
        assert set(rows) == expected_ids
        assert len(actual_ids) == 26
        assert len(set(actual_ids)) == 26
        assert required.issubset(next(iter(rows.values())))
        assert {row["integration_type"] for row in rows.values()} <= {
            "primary_skill_reference",
            "primary_framework_reference",
            "cli_runtime_reference",
            "secondary_or_rejected",
        }
        assert {row["admission_status"] for row in rows.values()} <= {
            "primary",
            "rejected_as_primary",
            "demoted",
            "superseded",
        }
        assert all(row["admission_reason"] for row in rows.values())

    def test_primary_references_have_stars_and_clear_licenses(self) -> None:
        forbidden = {"", "NONE", "NOASSERTION", "NULL", "无", "无许可证", "无LICENSE"}
        for row in self.real_rows().values():
            if not row["integration_type"].startswith("primary_"):
                continue
            assert int(row["stars"]) >= 1000, row["component_id"]
            assert row["license_spdx"] not in forbidden, row["component_id"]
            assert row["admission_status"] == "primary", row["component_id"]

    def test_cand_018_license_hard_gate(self) -> None:
        row = self.real_rows()["CAND-018"]
        assert row["integration_type"] == "secondary_or_rejected"
        assert row["admission_status"] == "rejected_as_primary"
        assert row["license_spdx"] == "NONE"
        assert not row["integration_type"].startswith("primary_")
        assert any(term in row["admission_reason"].lower() for term in ("license", "许可证"))

    def test_demoted_references_keep_legacy_status_and_reports(self) -> None:
        rows = self.real_rows()
        for component_id in ("CAND-015", "CAND-016"):
            row = rows[component_id]
            assert row["integration_type"] == "secondary_or_rejected"
            assert row["admission_status"] == "demoted"
            assert row["status"] == "reference_only"
            assert row["admission_reason"]
            assert list((ROOT / "reports/component_reviews").glob(f"{component_id}-*.md"))

    def test_cli_references_are_isolated(self) -> None:
        rows = self.real_rows()
        for component_id in ("CAND-023", "CAND-026"):
            row = rows[component_id]
            reason = row["admission_reason"].lower()
            assert row["integration_type"] == "cli_runtime_reference"
            assert row["admission_status"] == "primary"
            assert "cli" in reason or "subprocess" in reason
            assert "no ffmpeg source is copied" in reason or "no source copy" in reason
            assert not row["integration_type"].startswith("primary_")
        assert "gpl" in rows["CAND-026"]["admission_reason"].lower()
        assert "isolate" in rows["CAND-026"]["admission_reason"].lower()
        assert "build" in rows["CAND-023"]["admission_reason"].lower()

    def test_observation_dates_and_snapshot_agree(self) -> None:
        rows = self.real_rows()
        for row in rows.values():
            observed = row["stars_observed_at"]
            assert observed
            try:
                datetime.fromisoformat(observed.replace("Z", "+00:00"))
            except ValueError:
                date.fromisoformat(observed)

        snapshots = [
            ROOT / "reports/component_reviews/evidence/github_api_snapshot.json",
            ROOT / "data/processed/github_api_snapshot.json",
            ROOT / "tmp/github_api_snapshot.json",
        ]
        for path in snapshots:
            if not path.is_file():
                continue
            raw_snapshot = path.read_text(encoding="utf-8")
            payload, _ = json.JSONDecoder().raw_decode(raw_snapshot)
            records = payload.get("components", payload if isinstance(payload, list) else [])
            for record in records:
                row = rows[record["component_id"]]
                assert row["repository"] == record["repository"]
                assert int(row["stars"]) == int(record["stargazers_count"])
                assert row["license_spdx"] == record["license"]["spdx_id"]
                if row["license_spdx"] == "NONE":
                    assert not row["integration_type"].startswith("primary_")
            break
