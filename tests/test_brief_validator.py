"""业务规则校验器测试（合规边界核心测试，不依赖真实 LLM）。"""

from __future__ import annotations

from pathlib import Path

from src.brief_models import (
    BrandBrief,
    ClaimType,
    ComplianceBoundary,
    SellingPoint,
    TargetAudience,
)
from src.brief_parser import parse_brief_file
from src.brief_validator import (
    check_claim_types,
    check_fabrication_guard,
    check_forbidden_interpretations,
    check_required_sections,
    load_rules,
    validate_brief,
)

ROOT = Path(__file__).resolve().parent.parent
RULES = load_rules(ROOT / "config/brief_rules.yaml")
RAW_BRIEF = ROOT / "data/raw/qingxing_brief.md"


def make_brief_with_points(points: list[SellingPoint]) -> BrandBrief:
    return BrandBrief(
        brief_id="validator-test",
        brand_name="测试品牌",
        product_name="测试产品",
        selling_points=points,
        target_audience=TargetAudience(
            age_range="22-35岁", gender="女性", interests=["健身", "控糖"]
        ),
        platform="小红书短视频",
        compliance=ComplianceBoundary(prohibited_claims=["减肥", "降糖"]),
    )


def error_codes(brief: BrandBrief) -> set[str]:
    return {i.code for i in validate_brief(brief, RULES).errors}


class TestRealBriefPasses:
    def test_qingxing_brief_is_valid(self) -> None:
        brief = parse_brief_file(RAW_BRIEF, RULES, brief_id="qingxing-2026-07")
        result = validate_brief(brief, RULES)
        assert result.is_valid, [f"{i.code}: {i.message}" for i in result.errors]

    def test_qingxing_brief_has_missing_info(self) -> None:
        brief = parse_brief_file(RAW_BRIEF, RULES, brief_id="qingxing-2026-07")
        assert brief.missing_info, "缺失信息识别必须非空"


class TestClaimTypeRules:
    def test_zero_sucrose_must_be_brand_claim(self) -> None:
        brief = make_brief_with_points(
            [SellingPoint(claim="0蔗糖", claim_type=ClaimType.UNVERIFIED)]
        )
        assert "CLAIM_TYPE_MISMATCH" in error_codes(brief)

    def test_zero_sucrose_confirmed_without_evidence_fails(self) -> None:
        brief = make_brief_with_points(
            [SellingPoint(claim="0蔗糖", claim_type=ClaimType.CONFIRMED)]
        )
        codes = error_codes(brief)
        assert "CLAIM_TYPE_MISMATCH" in codes or "CONFIRMED_WITHOUT_EVIDENCE" in codes

    def test_zero_sucrose_confirmed_with_evidence_fails_rule(self) -> None:
        """即使给了依据，0蔗糖仍须保持 brand_claim（按任务书业务边界）。"""
        brief = make_brief_with_points(
            [SellingPoint(claim="0蔗糖", claim_type=ClaimType.CONFIRMED, evidence="包装标识")]
        )
        assert "CLAIM_TYPE_MISMATCH" in error_codes(brief)

    def test_baofugan_confirmed_fails(self) -> None:
        brief = make_brief_with_points(
            [SellingPoint(claim="饱腹感", claim_type=ClaimType.CONFIRMED, evidence="用户反馈")]
        )
        assert "CLAIM_TYPE_NOT_ALLOWED" in error_codes(brief)

    def test_difudan_brand_claim_fails(self) -> None:
        brief = make_brief_with_points(
            [SellingPoint(claim="低负担", claim_type=ClaimType.BRAND_CLAIM)]
        )
        assert "CLAIM_TYPE_NOT_ALLOWED" in error_codes(brief)

    def test_difudan_unverified_passes_claim_check(self) -> None:
        brief = make_brief_with_points(
            [SellingPoint(claim="低负担", claim_type=ClaimType.UNVERIFIED)]
        )
        assert check_claim_types(brief, RULES) == []

    def test_unknown_claim_confirmed_without_evidence_fails(self) -> None:
        brief = make_brief_with_points(
            [SellingPoint(claim="增强免疫力", claim_type=ClaimType.CONFIRMED)]
        )
        assert "UNVERIFIED_CONFIRMED" in error_codes(brief)


class TestForbiddenInterpretations:
    def test_wutang_interpretation_fails(self) -> None:
        brief = make_brief_with_points(
            [
                SellingPoint(claim="0蔗糖", claim_type=ClaimType.BRAND_CLAIM),
                SellingPoint(claim="高蛋白", claim_type=ClaimType.BRAND_CLAIM, note="无糖配方"),
            ]
        )
        assert "FORBIDDEN_INTERPRETATION" in error_codes(brief)

    def test_buzhangpang_extension_fails(self) -> None:
        brief = make_brief_with_points(
            [
                SellingPoint(claim="低负担", claim_type=ClaimType.UNVERIFIED),
                SellingPoint(claim="高蛋白", claim_type=ClaimType.BRAND_CLAIM, note="吃了不长胖"),
            ]
        )
        assert "FORBIDDEN_INTERPRETATION" in error_codes(brief)

    def test_recording_forbidden_list_itself_is_allowed(self) -> None:
        brief = make_brief_with_points(
            [
                SellingPoint(
                    claim="0蔗糖",
                    claim_type=ClaimType.BRAND_CLAIM,
                    forbidden_interpretations=["无糖"],
                )
            ]
        )
        assert check_forbidden_interpretations(brief, RULES) == []


class TestInterestIsolation:
    def test_jiangtang_as_product_claim_fails(self) -> None:
        brief = make_brief_with_points(
            [SellingPoint(claim="高蛋白", claim_type=ClaimType.BRAND_CLAIM, note="帮助降糖")]
        )
        assert "INTEREST_AS_PRODUCT_CLAIM" in error_codes(brief)

    def test_kongtang_as_selling_point_fails(self) -> None:
        brief = make_brief_with_points(
            [SellingPoint(claim="控糖", claim_type=ClaimType.BRAND_CLAIM)]
        )
        assert "INTEREST_AS_SELLING_POINT" in error_codes(brief)

    def test_kongtang_as_audience_interest_passes(self) -> None:
        brief = make_brief_with_points(
            [SellingPoint(claim="高蛋白", claim_type=ClaimType.BRAND_CLAIM)]
        )
        result = validate_brief(brief, RULES)
        assert "INTEREST_AS_PRODUCT_CLAIM" not in {i.code for i in result.errors}
        assert "控糖" in brief.target_audience.interests


class TestFabricationGuard:
    def test_fabricated_protein_grams_fails(self) -> None:
        brief = make_brief_with_points(
            [SellingPoint(claim="高蛋白", claim_type=ClaimType.BRAND_CLAIM, note="每杯含蛋白质15g")]
        )
        assert "FABRICATED_NUTRITION_DATA" in error_codes(brief)

    def test_fabricated_calorie_fails(self) -> None:
        brief = make_brief_with_points(
            [SellingPoint(claim="低负担", claim_type=ClaimType.UNVERIFIED, note="仅80kcal")]
        )
        assert "FABRICATED_NUTRITION_DATA" in error_codes(brief)

    def test_confirmed_with_evidence_allows_numbers(self) -> None:
        brief = make_brief_with_points(
            [
                SellingPoint(
                    claim="蛋白质含量9g/100g",
                    claim_type=ClaimType.CONFIRMED,
                    evidence="品牌方营养成分表2026-06",
                )
            ]
        )
        assert check_fabrication_guard(brief, RULES) == []

    def test_plain_claim_without_numbers_passes(self) -> None:
        brief = make_brief_with_points(
            [SellingPoint(claim="高蛋白", claim_type=ClaimType.BRAND_CLAIM)]
        )
        assert check_fabrication_guard(brief, RULES) == []


class TestRequiredSections:
    def test_empty_platform_fails(self) -> None:
        brief = make_brief_with_points([])
        brief.platform = ""
        codes = {i.code for i in check_required_sections(brief, RULES)}
        assert "MISSING_SECTION" in codes

    def test_empty_prohibited_claims_fails(self) -> None:
        brief = make_brief_with_points([])
        brief.compliance.prohibited_claims = []
        codes = {i.code for i in check_required_sections(brief, RULES)}
        assert "MISSING_SECTION" in codes


class TestValidationResult:
    def test_result_aggregation(self) -> None:
        brief = parse_brief_file(RAW_BRIEF, RULES, brief_id="qingxing-2026-07")
        result = validate_brief(brief, RULES)
        assert result.errors == []
        assert result.is_valid

    def test_invalid_brief_not_valid(self) -> None:
        brief = make_brief_with_points(
            [SellingPoint(claim="0蔗糖", claim_type=ClaimType.CONFIRMED)]
        )
        assert not validate_brief(brief, RULES).is_valid
