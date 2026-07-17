"""BrandBrief Pydantic 模型测试。不依赖真实 LLM。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.brief_models import (
    BrandBrief,
    ClaimType,
    ComplianceBoundary,
    CreatorSearchProfile,
    MissingInfoItem,
    SellingPoint,
    TargetAudience,
)

ROOT = Path(__file__).resolve().parent.parent


def make_audience() -> TargetAudience:
    return TargetAudience(
        age_range="22-35岁",
        gender="女性",
        city_scope="城市",
        interests=["健身", "控糖", "轻食"],
        lifestyle=["上班族效率生活"],
    )


def make_brief() -> BrandBrief:
    return BrandBrief(
        brief_id="test-001",
        brand_name="测试品牌",
        product_name="测试产品",
        target_audience=make_audience(),
        platform="小红书短视频",
    )


class TestClaimType:
    def test_claim_type_values(self) -> None:
        assert ClaimType.CONFIRMED.value == "confirmed"
        assert ClaimType.BRAND_CLAIM.value == "brand_claim"
        assert ClaimType.SUBJECTIVE_EXPERIENCE.value == "subjective_experience"
        assert ClaimType.UNVERIFIED.value == "unverified"

    def test_selling_point_accepts_valid_type(self) -> None:
        point = SellingPoint(claim="0蔗糖", claim_type=ClaimType.BRAND_CLAIM)
        assert point.claim_type == ClaimType.BRAND_CLAIM

    def test_selling_point_rejects_invalid_type(self) -> None:
        with pytest.raises(ValidationError):
            SellingPoint(claim="0蔗糖", claim_type="guaranteed")  # type: ignore[arg-type]

    def test_selling_point_defaults(self) -> None:
        point = SellingPoint(claim="高蛋白", claim_type=ClaimType.BRAND_CLAIM)
        assert point.evidence is None
        assert point.forbidden_interpretations == []


class TestBrandBriefModel:
    def test_minimal_brief_valid(self) -> None:
        brief = make_brief()
        assert brief.brand_name == "测试品牌"
        assert brief.human_verified is False

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            BrandBrief(brief_id="x", brand_name="x")  # type: ignore[call-arg]

    def test_default_factories(self) -> None:
        brief = make_brief()
        assert brief.flavors == []
        assert brief.selling_points == []
        assert brief.missing_info == []
        assert isinstance(brief.compliance, ComplianceBoundary)
        assert isinstance(brief.creator_search_profile, CreatorSearchProfile)

    def test_json_round_trip(self) -> None:
        brief = make_brief()
        brief.selling_points.append(SellingPoint(claim="0蔗糖", claim_type=ClaimType.BRAND_CLAIM))
        payload = brief.model_dump_json()
        restored = BrandBrief.model_validate_json(payload)
        assert restored == brief

    def test_json_schema_has_required_properties(self) -> None:
        schema = BrandBrief.model_json_schema()
        props = schema["properties"]
        keys = ["brand_name", "product_name", "selling_points", "target_audience", "compliance"]
        for key in keys:
            assert key in props

    def test_schema_file_matches_model(self) -> None:
        schema_file = ROOT / "config/brief_schema.json"
        assert schema_file.is_file()
        file_schema = json.loads(schema_file.read_text(encoding="utf-8"))
        model_props = BrandBrief.model_json_schema()["properties"].keys()
        assert file_schema["properties"].keys() == model_props

    def test_missing_info_item(self) -> None:
        item = MissingInfoItem(field="营养成分", question="请提供", impact="合规", severity="high")
        assert item.severity == "high"

    def test_compliance_boundary_defaults(self) -> None:
        boundary = ComplianceBoundary()
        assert boundary.prohibited_claims == []
        assert boundary.audience_interest_not_product_claim == []
