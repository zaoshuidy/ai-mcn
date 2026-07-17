"""Creator 数据模型测试。全部离线运行，不依赖真实小红书数据。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.creator_models import (
    AudienceInference,
    CreatorCandidate,
    CreatorIdentity,
    CreatorPost,
    DataSourceType,
    SelectionStatus,
)

ROOT = Path(__file__).resolve().parent.parent


def make_identity(**kwargs) -> CreatorIdentity:
    base = {
        "creator_id": "u_001",
        "nickname": "测试达人",
        "profile_url": "https://example.com/user/u_001",
    }
    base.update(kwargs)
    return CreatorIdentity(**base)


def make_candidate(**kwargs) -> CreatorCandidate:
    base = {"creator": make_identity(), "collection_source": "manual_search"}
    base.update(kwargs)
    return CreatorCandidate(**base)


# ---------- CreatorIdentity ----------


def test_identity_minimal_creation() -> None:
    identity = make_identity()
    assert identity.platform == "小红书"
    assert identity.followers is None
    assert identity.location is None


def test_identity_sensitive_fields_nullable() -> None:
    """位置等敏感或不可靠信息允许为空。"""
    identity = make_identity(location=None, verified_type=None, bio=None)
    assert identity.location is None


def test_identity_negative_followers_rejected() -> None:
    with pytest.raises(ValidationError):
        make_identity(followers=-1)


def test_identity_followers_source_marking() -> None:
    identity = make_identity(
        followers=1000,
        followers_source=DataSourceType.PAGE_OBSERVED,
        followers_observed_at="2026-07-17T00:00:00+00:00",
    )
    assert identity.followers_source == DataSourceType.PAGE_OBSERVED


def test_identity_requires_core_fields() -> None:
    with pytest.raises(ValidationError):
        CreatorIdentity(creator_id="u_001", nickname="x")  # 缺 profile_url


# ---------- CreatorPost ----------


def test_post_minimal_creation() -> None:
    post = CreatorPost(post_id="p_001", url="https://example.com/p_001")
    assert post.content_type == "video"
    assert post.likes is None


def test_post_negative_metrics_rejected() -> None:
    with pytest.raises(ValidationError):
        CreatorPost(post_id="p", url="https://example.com/p", likes=-5)


def test_post_requires_url() -> None:
    with pytest.raises(ValidationError):
        CreatorPost(post_id="p_001")


# ---------- AudienceInference ----------


def test_inference_valid_with_evidence() -> None:
    inference = AudienceInference(
        gender_tendency="女性为主（推测）",
        interests=["健身"],
        evidence=["笔记标题含健身餐"],
        confidence=0.6,
    )
    assert inference.source_type == DataSourceType.AI_INFERRED


def test_inference_claim_without_evidence_rejected() -> None:
    """有推测结论时 evidence 不得为空。"""
    with pytest.raises(ValidationError, match="evidence"):
        AudienceInference(gender_tendency="女性为主", evidence=[], confidence=0.5)


def test_inference_confidence_without_claim_rejected() -> None:
    """无推测结论时 confidence 必须为 0。"""
    with pytest.raises(ValidationError, match="confidence"):
        AudienceInference(evidence=[], confidence=0.5)


def test_inference_source_type_locked_to_ai() -> None:
    """受众画像必须标记为 ai_inferred，不得写成平台官方数据。"""
    with pytest.raises(ValidationError):
        AudienceInference(
            gender_tendency="女性为主",
            evidence=["依据"],
            confidence=0.5,
            source_type=DataSourceType.PAGE_OBSERVED,
        )


def test_inference_confidence_upper_bound() -> None:
    with pytest.raises(ValidationError):
        AudienceInference(gender_tendency="女", evidence=["e"], confidence=1.01)


def test_inference_confidence_lower_bound() -> None:
    with pytest.raises(ValidationError):
        AudienceInference(gender_tendency="女", evidence=["e"], confidence=-0.1)


def test_inference_empty_conclusion_allowed() -> None:
    """无结论 + confidence=0 合法（表示无法推测，不编造）。"""
    inference = AudienceInference(evidence=[], confidence=0.0)
    assert inference.gender_tendency is None


# ---------- CreatorCandidate ----------


def test_candidate_minimal_creation() -> None:
    candidate = make_candidate()
    assert candidate.human_verified is False
    assert candidate.selection_status == SelectionStatus.POC_CANDIDATE
    assert candidate.collected_at  # 自动生成采集时间


def test_candidate_poc_cannot_be_human_verified() -> None:
    """POC 候选不得标记 human_verified，需先经人工审核升级状态。"""
    with pytest.raises(ValidationError, match="human_verified"):
        make_candidate(human_verified=True, selection_status=SelectionStatus.POC_CANDIDATE)


def test_candidate_research_status_can_be_verified() -> None:
    candidate = make_candidate(
        human_verified=True, selection_status=SelectionStatus.RESEARCH_CANDIDATE
    )
    assert candidate.human_verified is True


def test_candidate_json_roundtrip() -> None:
    candidate = make_candidate(
        content_categories=["健身饮食"],
        audience_inference=AudienceInference(
            interests=["轻食"], evidence=["简介提及轻食"], confidence=0.4
        ),
        representative_posts=[CreatorPost(post_id="p1", url="https://example.com/p1")],
        commercial_signals=["历史食品合作（依据：笔记 X）"],
        risk_signals=["广告占比待确认"],
    )
    payload = json.loads(candidate.model_dump_json())
    restored = CreatorCandidate.model_validate(payload)
    assert restored.creator.creator_id == candidate.creator.creator_id
    assert restored.audience_inference.confidence == 0.4


def test_data_source_type_values() -> None:
    values = {t.value for t in DataSourceType}
    assert values == {
        "page_observed", "tool_returned", "ai_inferred", "human_verified", "unknown"
    }


def test_selection_status_values() -> None:
    values = {s.value for s in SelectionStatus}
    assert values == {"poc_candidate", "research_candidate", "final_candidate", "excluded"}


# ---------- 样例文件 ----------


def load_sample() -> dict:
    path = ROOT / "data/samples/creator_candidate_example.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_sample_file_validates() -> None:
    CreatorCandidate.model_validate(load_sample())


def test_sample_marked_as_fictional() -> None:
    sample = load_sample()
    assert "虚构" in sample.get("_example_note", "")
    assert "非真实" in sample["creator"]["nickname"]


def test_sample_inference_has_evidence_and_confidence() -> None:
    sample = load_sample()
    inference = sample["audience_inference"]
    assert inference["evidence"], "推测字段必须带 evidence"
    assert 0 <= inference["confidence"] <= 1
    assert inference["source_type"] == "ai_inferred"


def test_sample_not_human_verified() -> None:
    sample = load_sample()
    assert sample["human_verified"] is False
    assert sample["selection_status"] == "poc_candidate"
