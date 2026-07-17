"""规则版 Brief 解析器测试（使用固定测试 Brief，不依赖真实 LLM）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.brief_models import ClaimType
from src.brief_parser import (
    parse_brief,
    parse_brief_file,
    parse_prohibited_claims,
    parse_selling_points,
)
from src.brief_validator import load_rules

ROOT = Path(__file__).resolve().parent.parent
RAW_BRIEF = ROOT / "data/raw/qingxing_brief.md"
RULES = load_rules(ROOT / "config/brief_rules.yaml")


@pytest.fixture(scope="module")
def brief_text() -> str:
    return RAW_BRIEF.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parsed(brief_text: str):
    return parse_brief(brief_text, brief_id="qingxing-2026-07", source_file=str(RAW_BRIEF))


class TestFixedBriefParsing:
    def test_brand_name(self, parsed) -> None:
        assert parsed.brand_name == "轻醒"

    def test_product_name(self, parsed) -> None:
        assert parsed.product_name == "0蔗糖高蛋白希腊酸奶"

    def test_flavors(self, parsed) -> None:
        assert parsed.flavors == ["原味", "蓝莓", "黄桃"]

    def test_scenarios(self, parsed) -> None:
        assert parsed.scenarios == ["早餐", "运动后", "下午茶"]

    def test_platform(self, parsed) -> None:
        assert parsed.platform == "小红书短视频"

    def test_audience_age_range(self, parsed) -> None:
        assert parsed.target_audience.age_range == "22-35岁"

    def test_audience_gender(self, parsed) -> None:
        assert parsed.target_audience.gender == "女性"

    def test_audience_interests_include_kongtang(self, parsed) -> None:
        assert "控糖" in parsed.target_audience.interests

    def test_prohibited_claims(self, parsed) -> None:
        assert set(parsed.compliance.prohibited_claims) == {"减肥", "降糖"}

    def test_kongtang_marked_interest_only(self, parsed) -> None:
        assert "控糖" in parsed.compliance.audience_interest_not_product_claim

    def test_human_verified_default_false(self, parsed) -> None:
        assert parsed.human_verified is False


class TestSellingPointParsing:
    def test_selling_points_from_text(self, brief_text: str) -> None:
        points = parse_selling_points(brief_text)
        claims = {p.claim for p in points}
        assert {"高蛋白", "饱腹感", "低负担"}.issubset(claims)

    def test_zero_sucrose_extracted_from_product_name(self, parsed) -> None:
        claims = {p.claim: p for p in parsed.selling_points}
        assert "0蔗糖" in claims
        assert claims["0蔗糖"].claim_type == ClaimType.BRAND_CLAIM

    def test_gaodanbai_is_brand_claim(self, parsed) -> None:
        claims = {p.claim: p for p in parsed.selling_points}
        assert claims["高蛋白"].claim_type == ClaimType.BRAND_CLAIM

    def test_baofugan_not_confirmed(self, parsed) -> None:
        claims = {p.claim: p for p in parsed.selling_points}
        assert claims["饱腹感"].claim_type in {
            ClaimType.SUBJECTIVE_EXPERIENCE,
            ClaimType.UNVERIFIED,
        }

    def test_difudan_is_unverified(self, parsed) -> None:
        claims = {p.claim: p for p in parsed.selling_points}
        assert claims["低负担"].claim_type == ClaimType.UNVERIFIED

    def test_zero_sucrose_forbidden_interpretation(self, parsed) -> None:
        claims = {p.claim: p for p in parsed.selling_points}
        assert "无糖" in claims["0蔗糖"].forbidden_interpretations

    def test_difudan_forbidden_interpretation(self, parsed) -> None:
        claims = {p.claim: p for p in parsed.selling_points}
        assert "不长胖" in claims["低负担"].forbidden_interpretations

    def test_no_evidence_attached_by_default(self, parsed) -> None:
        for point in parsed.selling_points:
            assert point.evidence is None


class TestProhibitedClaimParsing:
    def test_parse_prohibited_claims(self, brief_text: str) -> None:
        assert parse_prohibited_claims(brief_text) == ["减肥", "降糖"]

    def test_parse_empty_text(self) -> None:
        assert parse_prohibited_claims("无合规要求段落") == []
        assert parse_selling_points("无卖点段落") == []


class TestFullPipeline:
    def test_parse_brief_file_attaches_missing_info(self) -> None:
        brief = parse_brief_file(RAW_BRIEF, RULES, brief_id="qingxing-2026-07")
        assert len(brief.missing_info) >= 4
        fields = {item.field for item in brief.missing_info}
        assert any("营养" in f for f in fields)

    def test_parse_brief_file_builds_creator_profile(self) -> None:
        brief = parse_brief_file(RAW_BRIEF, RULES, brief_id="qingxing-2026-07")
        profile = brief.creator_search_profile
        assert profile.search_keywords
        assert profile.excluded_creator_types
        assert any("早餐" in kw for kw in profile.search_keywords)

    def test_creator_profile_excludes_official_accounts(self) -> None:
        brief = parse_brief_file(RAW_BRIEF, RULES, brief_id="qingxing-2026-07")
        assert "品牌官方号" in brief.creator_search_profile.excluded_creator_types
