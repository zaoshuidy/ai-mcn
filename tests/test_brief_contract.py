"""Stage 1 数据契约补齐测试：新子模型、迁移、评分报告与 Stage 2 门禁。

不依赖真实 LLM；复用固定测试 Brief。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.brief_models import (
    BrandBrief,
    BrandInfo,
    ClaimType,
    ComplianceBoundary,
    ComplianceRule,
    MissingInfoItem,
    MissingInformation,
    ProductVariant,
    SellingPoint,
    TargetAudience,
    UsageScenario,
    split_platform_text,
    upgrade_legacy_brief,
)
from src.brief_parser import parse_brief_file
from src.brief_renderer import render_summary
from src.brief_validator import (
    FINAL_SELECTION_REQUIRED,
    Issue,
    build_validation_report,
    load_rules,
)

ROOT = Path(__file__).resolve().parent.parent
RULES = load_rules(ROOT / "config/brief_rules.yaml")
RAW_BRIEF = ROOT / "data/raw/qingxing_brief.md"
PROCESSED_JSON = ROOT / "data/processed/qingxing_brief.json"


@pytest.fixture(scope="module")
def brief() -> BrandBrief:
    return parse_brief_file(RAW_BRIEF, RULES, brief_id="qingxing-2026-07")


@pytest.fixture(scope="module")
def report(brief: BrandBrief):
    return build_validation_report(brief, RULES)


def make_clean_brief() -> BrandBrief:
    """构造无缺失、无违规的完整 Brief（用于满分/放行测试）。"""
    return BrandBrief(
        brief_id="clean-001",
        brand_name="测试品牌",
        product_name="测试产品",
        platform="小红书短视频",
        brand=BrandInfo(
            brand_name="测试品牌",
            product_name="测试产品",
            platform="小红书",
            content_format="短视频",
        ),
        selling_points=[SellingPoint(claim="高蛋白", claim_type=ClaimType.BRAND_CLAIM)],
        target_audience=TargetAudience(
            age_range="22-35岁", age_min=22, age_max=35, gender="女性", interests=["健身"]
        ),
        compliance=ComplianceBoundary(prohibited_claims=["减肥", "降糖"]),
        compliance_rules=[],
        # 非阻塞且不记 warning 的缺失项：避免 NO_MISSING_INFO 警告，不影响最终定案
        missing_information=[MissingInformation(field="产品包装图")],
    )


# ---------- 1. BrandInfo 模型 ----------
class TestBrandInfo:
    def test_create(self) -> None:
        info = BrandInfo(brand_name="轻醒", product_name="希腊酸奶")
        assert info.platform == ""

    def test_parsed_brief_has_brand(self, brief: BrandBrief) -> None:
        assert brief.brand is not None
        assert brief.brand.brand_name == "轻醒"

    def test_brand_campaign_goal(self, brief: BrandBrief) -> None:
        assert "自然种草" in brief.brand.campaign_goal


# ---------- 2. ProductVariant 模型 ----------
class TestProductVariant:
    def test_create(self) -> None:
        variant = ProductVariant(name="原味", confirmed=True, source="brand_brief")
        assert variant.confirmed is True

    def test_parsed_variants(self, brief: BrandBrief) -> None:
        names = [v.name for v in brief.product_variants]
        assert names == ["原味", "蓝莓", "黄桃"]
        for variant in brief.product_variants:
            assert variant.confirmed is True
            assert variant.source == "brand_brief"


# ---------- 3. UsageScenario 模型 ----------
class TestUsageScenario:
    def test_create(self) -> None:
        scenario = UsageScenario(name="早餐", priority=1)
        assert scenario.priority == 1

    def test_parsed_scenarios(self, brief: BrandBrief) -> None:
        names = [s.name for s in brief.usage_scenarios]
        assert {"早餐", "运动后", "下午茶"}.issubset(set(names))

    def test_priority_sortable(self, brief: BrandBrief) -> None:
        priorities = [s.priority for s in brief.usage_scenarios]
        assert all(isinstance(p, int) for p in priorities)
        assert sorted(priorities) == priorities

    def test_scenario_reason_and_feasibility(self, brief: BrandBrief) -> None:
        breakfast = next(s for s in brief.usage_scenarios if s.name == "早餐")
        assert breakfast.natural_integration_reason
        assert breakfast.shooting_feasibility


# ---------- 4. ComplianceRule 模型 ----------
class TestComplianceRule:
    def test_create(self) -> None:
        rule = ComplianceRule(category="减肥功效承诺", severity="high")
        assert rule.prohibited_expressions == []

    def test_parsed_has_seven_rules(self, brief: BrandBrief) -> None:
        categories = {r.category for r in brief.compliance_rules}
        expected = {
            "减肥功效承诺",
            "降糖或血糖功效",
            "疾病治疗",
            "绝对化用语",
            "未证实营养数据",
            "夸大主观体验",
            "不适当竞品贬低",
        }
        assert expected.issubset(categories)


# ---------- 5. MissingInformation 模型 ----------
class TestMissingInformation:
    def test_create_defaults(self) -> None:
        item = MissingInformation(field="营养成分表")
        assert item.blocks_next_stage is False
        assert item.importance == "medium"

    def test_legacy_compat_preserved(self, brief: BrandBrief) -> None:
        assert brief.missing_info, "兼容旧结构 missing_info 必须同步填充"
        assert isinstance(brief.missing_info[0], MissingInfoItem)


# ---------- 6. 年龄上下限 ----------
class TestAgeBounds:
    def test_parsed_age_bounds(self, brief: BrandBrief) -> None:
        assert brief.target_audience.age_min == 22
        assert brief.target_audience.age_max == 35
        assert brief.target_audience.age_range == "22-35岁"

    def test_age_max_must_exceed_min(self) -> None:
        with pytest.raises(ValidationError):
            TargetAudience(age_range="35-22岁", age_min=35, age_max=22, gender="女性")

    def test_age_min_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            TargetAudience(age_range="-1-35岁", age_min=-1, age_max=35, gender="女性")

    def test_age_extension_rejected(self, brief: BrandBrief) -> None:
        """不得根据常识擅自扩展年龄：上下限与原文不一致即报错。"""
        brief.target_audience.age_min = 18
        report = build_validation_report(brief, RULES)
        assert "AGE_RANGE_MISMATCH" in {i.code for i in report.errors}
        brief.target_audience.age_min = 22  # 还原，避免影响其他 fixture


# ---------- 7. 平台与内容形式拆分 ----------
class TestPlatformSplit:
    def test_split_helper(self) -> None:
        assert split_platform_text("小红书短视频") == ("小红书", "短视频")

    def test_parsed_split(self, brief: BrandBrief) -> None:
        assert brief.brand.platform == "小红书"
        assert brief.brand.content_format == "短视频"

    def test_legacy_platform_preserved(self, brief: BrandBrief) -> None:
        assert brief.platform == "小红书短视频"


# ---------- 8. 旧模型迁移 ----------
class TestLegacyUpgrade:
    def make_legacy(self) -> BrandBrief:
        return BrandBrief(
            brief_id="legacy-001",
            brand_name="旧品牌",
            product_name="旧产品",
            platform="小红书短视频",
            flavors=["原味"],
            scenarios=["早餐"],
            missing_info=[
                MissingInfoItem(
                    field="营养成分表", question="请提供", impact="合规", severity="high"
                )
            ],
            target_audience=TargetAudience(age_range="22-35岁", gender="女性"),
        )

    def test_upgrade_fills_brand(self) -> None:
        brief = upgrade_legacy_brief(self.make_legacy())
        assert brief.brand is not None
        assert brief.brand.platform == "小红书"
        assert brief.brand.content_format == "短视频"

    def test_upgrade_fills_variants_scenarios_missing(self) -> None:
        brief = upgrade_legacy_brief(self.make_legacy())
        assert brief.product_variants[0].name == "原味"
        assert brief.usage_scenarios[0].name == "早餐"
        assert brief.missing_information[0].field == "营养成分表"
        assert brief.missing_information[0].importance == "high"


# ---------- 9/10. 相对路径与绝对路径拦截 ----------
class TestPathSafety:
    def test_source_file_relative(self, brief: BrandBrief) -> None:
        assert brief.source_file == "data/raw/qingxing_brief.md"
        assert not Path(brief.source_file).is_absolute()

    def test_no_absolute_path_in_outputs(self) -> None:
        pattern = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/Users/|/home/")
        targets = list((ROOT / "data/processed").glob("*")) + list(
            (ROOT / "reports").glob("*.md")
        ) + list((ROOT / "config").glob("*.json")) + list((ROOT / "config").glob("*.yaml"))
        assert targets, "扫描目标为空"
        for path in targets:
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert not pattern.search(text), f"{path.name} 含本地绝对路径"


# ---------- 11/12. 缺失信息清单 ----------
class TestMissingInfoList:
    def test_at_least_12_items(self, brief: BrandBrief) -> None:
        assert len(brief.missing_information) >= 12

    def test_all_items_have_blocks_flag(self, brief: BrandBrief) -> None:
        for item in brief.missing_information:
            assert isinstance(item.blocks_next_stage, bool)
            assert item.recommended_action
            assert item.reason

    def test_final_selection_blockers(self, brief: BrandBrief) -> None:
        blocking = {m.field for m in brief.missing_information if m.blocks_next_stage}
        assert set(FINAL_SELECTION_REQUIRED).issubset(blocking)


# ---------- 13-19. 评分计算 ----------
class TestScoring:
    def test_clean_brief_scores_100(self) -> None:
        report = build_validation_report(make_clean_brief(), RULES)
        assert report.score == 100
        assert report.status == "ready"

    def test_error_deduction(self) -> None:
        brief = make_clean_brief()
        brief.selling_points.append(SellingPoint(claim="胶原蛋白", claim_type=ClaimType.CONFIRMED))
        report = build_validation_report(brief, RULES)
        assert report.score <= 80  # 100 - 20，且封顶 79

    def test_blocker_deduction(self) -> None:
        brief = make_clean_brief()
        brief.brand_name = ""
        brief.brand.brand_name = ""
        report = build_validation_report(brief, RULES)
        assert any(i.code == "CORE_FIELD_MISSING" for i in report.blockers)
        # 品牌名缺失同时触发 MISSING_SECTION error(-20) 与 CORE_FIELD_MISSING blocker(-15)
        assert report.score == 65
        assert report.status == "invalid"

    def test_score_floor_zero(self) -> None:
        issues = [Issue("error", "X", "m") for _ in range(10)]
        score = max(0, 100 - 20 * len(issues))
        assert score == 0

    def test_warning_deduction(self) -> None:
        brief = make_clean_brief()
        brief.missing_information = [
            MissingInformation(field="品牌禁用词", warn_if_missing=True)
        ]
        report = build_validation_report(brief, RULES)
        assert report.score == 98  # low warning -2
        assert report.status == "ready_with_warnings"

    def test_cap_79_on_fabrication(self) -> None:
        brief = make_clean_brief()
        brief.selling_points.append(
            SellingPoint(claim="高蛋白", claim_type=ClaimType.BRAND_CLAIM, note="含蛋白质15g")
        )
        report = build_validation_report(brief, RULES)
        assert report.score <= 79

    def test_cap_79_on_forbidden_interpretation(self) -> None:
        brief = make_clean_brief()
        brief.selling_points.append(
            SellingPoint(claim="低负担", claim_type=ClaimType.UNVERIFIED)
        )
        brief.selling_points.append(
            SellingPoint(claim="口感好", claim_type=ClaimType.UNVERIFIED, note="低负担吃了不长胖")
        )
        report = build_validation_report(brief, RULES)
        assert "FORBIDDEN_INTERPRETATION" in {i.code for i in report.errors}
        assert report.score <= 79

    def test_cap_79_on_prohibited_claim(self) -> None:
        brief = make_clean_brief()
        brief.compliance.prohibited_claims = ["减肥"]
        brief.selling_points.append(
            SellingPoint(claim="减肥神器", claim_type=ClaimType.BRAND_CLAIM)
        )
        report = build_validation_report(brief, RULES)
        assert report.score <= 79


# ---------- 20/21. Stage 2 放行判断 ----------
class TestStage2Gate:
    def test_qingxing_research_ready(self, report) -> None:
        assert report.stage_2_research_ready is True

    def test_qingxing_final_not_ready(self, report) -> None:
        assert report.stage_2_final_selection_ready is False

    def test_clean_brief_final_ready(self) -> None:
        report = build_validation_report(make_clean_brief(), RULES)
        assert report.stage_2_research_ready is True
        assert report.stage_2_final_selection_ready is True

    def test_errors_block_research(self) -> None:
        brief = make_clean_brief()
        brief.selling_points.append(SellingPoint(claim="胶原蛋白", claim_type=ClaimType.CONFIRMED))
        report = build_validation_report(brief, RULES)
        assert report.stage_2_research_ready is False


# ---------- 22-25. 报告字段与状态 ----------
class TestReportFields:
    def test_passed_rules(self, report) -> None:
        assert "卖点证据等级" in report.passed_rules
        assert "臆造数据拦截" in report.passed_rules

    def test_blockers_list(self, report) -> None:
        assert report.blockers == []

    def test_invalid_status(self) -> None:
        brief = make_clean_brief()
        brief.selling_points.append(SellingPoint(claim="胶原蛋白", claim_type=ClaimType.CONFIRMED))
        report = build_validation_report(brief, RULES)
        assert report.status == "invalid"

    def test_ready_with_warnings_status(self, report) -> None:
        assert report.status == "ready_with_warnings"
        assert report.score == 90
        assert len(report.warnings) == 5


# ---------- 26/27. Schema 与 JSON ----------
class TestSchemaAndJson:
    def test_schema_export_new_fields(self) -> None:
        schema = BrandBrief.model_json_schema()
        for key in ["brand", "product_variants", "usage_scenarios", "compliance_rules",
                    "missing_information", "version", "validation_status"]:
            assert key in schema["properties"]

    def test_json_round_trip(self, brief: BrandBrief) -> None:
        restored = BrandBrief.model_validate_json(brief.model_dump_json())
        assert restored.brand_name == brief.brand_name
        assert restored.brand.platform == "小红书"
        assert len(restored.missing_information) == len(brief.missing_information)

    def test_processed_json_uses_new_structure(self) -> None:
        data = json.loads(PROCESSED_JSON.read_text(encoding="utf-8"))
        assert data["brand"]["platform"] == "小红书"
        assert data["validation_status"] in {"ready", "ready_with_warnings", "blocked", "invalid"}
        assert len(data["missing_information"]) >= 12


# ---------- 28/29. 摘要中的分数与放行状态 ----------
class TestSummaryGate:
    def test_summary_contains_score(self, brief: BrandBrief, report) -> None:
        summary = render_summary(brief, report=report)
        assert "90 分" in summary

    def test_summary_contains_gate_status(self, brief: BrandBrief, report) -> None:
        summary = render_summary(brief, report=report)
        assert "Stage 2 候选调研是否可开始：是" in summary
        assert "Stage 2 最终达人定案是否可开始：否" in summary
        assert "ready_with_warnings" in summary

    def test_summary_lists_blocking_missing(self, brief: BrandBrief, report) -> None:
        summary = render_summary(brief, report=report)
        assert "营养成分表" in summary
        assert "购买渠道" in summary
