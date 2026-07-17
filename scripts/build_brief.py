"""Stage 1 构建脚本：解析原始 Brief → 校验 → 生成结构化产物。

用法：
    python scripts/build_brief.py

产物：
    data/processed/qingxing_brief.json
    data/processed/qingxing_brief_summary.md
    config/brief_schema.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.brief_models import BrandBrief  # noqa: E402
from src.brief_parser import parse_brief_file  # noqa: E402
from src.brief_renderer import render_summary  # noqa: E402
from src.brief_validator import (  # noqa: E402
    build_validation_report,
    load_rules,
    validate_brief,
)

RAW_BRIEF = ROOT / "data/raw/qingxing_brief.md"
RULES = ROOT / "config/brief_rules.yaml"
OUT_JSON = ROOT / "data/processed/qingxing_brief.json"
OUT_SUMMARY = ROOT / "data/processed/qingxing_brief_summary.md"
OUT_SCHEMA = ROOT / "config/brief_schema.json"


def main() -> int:
    rules = load_rules(RULES)
    brief = parse_brief_file(RAW_BRIEF, rules, brief_id="qingxing-2026-07")
    result = validate_brief(brief, rules)
    report = build_validation_report(brief, rules, result)
    brief.validation_status = report.status

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(brief.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    OUT_SUMMARY.write_text(render_summary(brief, result, report), encoding="utf-8")
    OUT_SCHEMA.write_text(
        json.dumps(BrandBrief.model_json_schema(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"已生成: {OUT_JSON.relative_to(ROOT)}")
    print(f"已生成: {OUT_SUMMARY.relative_to(ROOT)}")
    print(f"已生成: {OUT_SCHEMA.relative_to(ROOT)}")
    print(f"业务规则校验: error={len(result.errors)} warning={len(result.warnings)}")
    print(
        f"验证报告: score={report.score} status={report.status} "
        f"research_ready={report.stage_2_research_ready} "
        f"final_selection_ready={report.stage_2_final_selection_ready}"
    )
    for issue in result.issues:
        print(f"  [{issue.severity}] {issue.code}: {issue.message}")
    if not result.is_valid:
        print("构建失败：存在 error 级问题")
        return 1
    print("构建成功")
    return 0


if __name__ == "__main__":
    sys.exit(main())
