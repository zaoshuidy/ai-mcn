"""人工可读摘要渲染器测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.brief_models import ClaimType
from src.brief_parser import parse_brief_file
from src.brief_renderer import render_claim_type_label, render_summary
from src.brief_validator import load_rules, validate_brief

ROOT = Path(__file__).resolve().parent.parent
RULES = load_rules(ROOT / "config/brief_rules.yaml")
RAW_BRIEF = ROOT / "data/raw/qingxing_brief.md"
SUMMARY_FILE = ROOT / "data/processed/qingxing_brief_summary.md"


@pytest.fixture(scope="module")
def summary() -> str:
    brief = parse_brief_file(RAW_BRIEF, RULES, brief_id="qingxing-2026-07")
    result = validate_brief(brief, RULES)
    return render_summary(brief, result)


class TestClaimTypeLabels:
    def test_labels_cover_all_types(self) -> None:
        for claim_type in ClaimType:
            assert render_claim_type_label(claim_type)

    def test_brand_claim_label(self) -> None:
        assert "品牌方宣称" in render_claim_type_label(ClaimType.BRAND_CLAIM)

    def test_unverified_label(self) -> None:
        assert "未经验证" in render_claim_type_label(ClaimType.UNVERIFIED)


class TestSummarySections:
    def test_contains_brand(self, summary: str) -> None:
        assert "轻醒" in summary

    def test_contains_all_core_sections(self, summary: str) -> None:
        for section in [
            "品牌与产品",
            "卖点与证据状态",
            "目标人群",
            "使用场景与内容目标",
            "合规边界",
            "缺失信息清单",
            "达人搜索画像",
            "业务规则校验结果",
        ]:
            assert section in summary, f"摘要缺少栏目: {section}"

    def test_claim_types_rendered(self, summary: str) -> None:
        assert "品牌方宣称" in summary
        assert "未经验证" in summary
        assert "主观体验" in summary

    def test_forbidden_interpretation_shown(self, summary: str) -> None:
        assert "无糖" in summary  # 出现在禁止解释方向列

    def test_prohibited_claims_shown(self, summary: str) -> None:
        assert "减肥" in summary
        assert "降糖" in summary

    def test_interest_isolation_note_shown(self, summary: str) -> None:
        assert "控糖" in summary
        assert "不得转为产品功效" in summary

    def test_missing_info_table(self, summary: str) -> None:
        assert "营养成分" in summary
        assert "高" in summary  # high 优先级

    def test_creator_profile_shown(self, summary: str) -> None:
        assert "上班族早餐" in summary
        assert "品牌官方号" in summary

    def test_validation_result_shown(self, summary: str) -> None:
        assert "通过（无 error）" in summary

    def test_human_verified_status_shown(self, summary: str) -> None:
        assert "待人工执行者确认" in summary


class TestSummaryFile:
    def test_summary_file_exists(self) -> None:
        assert SUMMARY_FILE.is_file()

    def test_summary_file_matches_renderer(self, summary: str) -> None:
        content = SUMMARY_FILE.read_text(encoding="utf-8")
        for section in ["卖点与证据状态", "达人搜索画像", "缺失信息清单"]:
            assert section in content
