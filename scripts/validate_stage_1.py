"""Stage 1 自动验证脚本：品牌 Brief 结构化。

检查 Stage 1 交付物是否齐全、结构化产物是否符合业务规则与合规边界。
任何关键检查失败都会以非 0 退出码结束。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from src.brief_models import BrandBrief, ClaimType  # noqa: E402
from src.brief_validator import load_rules, validate_brief  # noqa: E402

REQUIRED_FILES = [
    "data/raw/qingxing_brief.md",
    "data/processed/qingxing_brief.json",
    "data/processed/qingxing_brief_summary.md",
    "src/brief_models.py",
    "src/brief_parser.py",
    "src/brief_validator.py",
    "src/brief_renderer.py",
    "prompts/brief_analyzer.md",
    "config/brief_schema.json",
    "config/brief_rules.yaml",
    "tests/test_brief_models.py",
    "tests/test_brief_validator.py",
    "tests/test_brief_parser.py",
    "tests/test_brief_renderer.py",
    "scripts/validate_stage_1.py",
    "reports/stage_1_brief_analysis_report.md",
]

NUMERIC_PATTERN = re.compile(r"\d+(\.\d+)?\s*(g|克|mg|毫克|kcal|千卡|大卡|千焦|kJ|%)")

results: list[tuple[str, str, str]] = []


def report(level: str, check: str, message: str = "") -> None:
    results.append((level, check, message))
    print(f"[{level}] {check}" + (f" - {message}" if message else ""))


def load_brief() -> BrandBrief | None:
    path = ROOT / "data/processed/qingxing_brief.json"
    if not path.is_file():
        return None
    try:
        return BrandBrief.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception as exc:  # noqa: BLE001 - 验证脚本需兜底所有解析错误
        report("FAIL", "结构化 JSON 无法被模型校验", str(exc))
        return None


def check_files() -> None:
    for f in REQUIRED_FILES:
        if (ROOT / f).is_file():
            report("PASS", f"文件存在: {f}")
        else:
            report("FAIL", f"文件缺失: {f}")


def check_json_against_model(brief: BrandBrief | None) -> None:
    if brief is not None:
        report("PASS", "qingxing_brief.json 通过 BrandBrief 模型校验")


def check_schema_file() -> None:
    path = ROOT / "config/brief_schema.json"
    if not path.is_file():
        report("FAIL", "brief_schema.json 缺失")
        return
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report("FAIL", "brief_schema.json 不是合法 JSON", str(exc))
        return
    props = schema.get("properties", {})
    required_keys = {
        "brand_name", "product_name", "selling_points", "target_audience", "compliance",
    }
    if required_keys.issubset(props):
        report("PASS", "brief_schema.json 含核心属性")
    else:
        report("FAIL", "brief_schema.json 缺少核心属性", str(required_keys - props.keys()))


def check_rules_file() -> None:
    path = ROOT / "config/brief_rules.yaml"
    if not path.is_file():
        report("FAIL", "brief_rules.yaml 缺失")
        return
    rules = yaml.safe_load(path.read_text(encoding="utf-8"))
    claim_rules = rules.get("brief_rules", {}).get("claim_rules", [])
    names = {r["claim"] for r in claim_rules}
    if {"0蔗糖", "高蛋白", "饱腹感", "低负担"}.issubset(names):
        report("PASS", "brief_rules.yaml 覆盖四个关键卖点规则")
    else:
        report("FAIL", "brief_rules.yaml 缺少关键卖点规则")


def check_claim_boundaries(brief: BrandBrief | None) -> None:
    if brief is None:
        return
    claims = {p.claim: p for p in brief.selling_points}
    if claims.get("0蔗糖") and claims["0蔗糖"].claim_type == ClaimType.BRAND_CLAIM:
        report("PASS", "0蔗糖 标记为 brand_claim")
    else:
        report("FAIL", "0蔗糖 未标记为 brand_claim")
    if claims.get("高蛋白") and claims["高蛋白"].claim_type == ClaimType.BRAND_CLAIM:
        report("PASS", "高蛋白 标记为 brand_claim")
    else:
        report("FAIL", "高蛋白 未标记为 brand_claim")
    if claims.get("饱腹感") and claims["饱腹感"].claim_type in {
        ClaimType.SUBJECTIVE_EXPERIENCE,
        ClaimType.UNVERIFIED,
    }:
        report("PASS", "饱腹感 为主观体验/未验证")
    else:
        report("FAIL", "饱腹感 证据等级越界")
    if claims.get("低负担") and claims["低负担"].claim_type == ClaimType.UNVERIFIED:
        report("PASS", "低负担 标记为 unverified")
    else:
        report("FAIL", "低负担 未标记为 unverified")
    if claims.get("0蔗糖") and "无糖" in claims["0蔗糖"].forbidden_interpretations:
        report("PASS", "0蔗糖→无糖 已列入禁止解释")
    else:
        report("FAIL", "0蔗糖 未记录禁止解释 无糖")


def check_interest_isolation(brief: BrandBrief | None) -> None:
    if brief is None:
        return
    claims_text = " ".join(p.claim + (p.note or "") for p in brief.selling_points)
    if "控糖" in brief.target_audience.interests:
        report("PASS", "控糖 作为人群兴趣标签")
    else:
        report("FAIL", "控糖 未作为人群兴趣标签")
    if "控糖" in brief.compliance.audience_interest_not_product_claim:
        report("PASS", "控糖 已标记为仅人群兴趣")
    else:
        report("FAIL", "控糖 未标记为仅人群兴趣")
    for word in ["降糖", "控制血糖", "降血糖", "治疗"]:
        if word in claims_text:
            report("FAIL", f"产品卖点含禁止功效词: {word}")
            return
    report("PASS", "产品卖点未将控糖转换为功效")


def check_fabrication(brief: BrandBrief | None) -> None:
    if brief is None:
        return
    for point in brief.selling_points:
        if point.claim_type == ClaimType.CONFIRMED and point.evidence:
            continue
        for text in (point.claim, point.note or "", point.evidence or ""):
            if NUMERIC_PATTERN.search(text):
                report("FAIL", "发现疑似臆造营养/检测数据", f"{point.claim}: {text}")
                return
    report("PASS", "未发现臆造蛋白质/糖/热量数值")


def check_missing_info(brief: BrandBrief | None) -> None:
    if brief is None:
        return
    if brief.missing_info:
        fields = "、".join(item.field for item in brief.missing_info[:3])
        report("PASS", f"缺失信息已识别（{len(brief.missing_info)} 项）", f"含 {fields} 等")
    else:
        report("FAIL", "缺失信息清单为空")


def check_business_rules(brief: BrandBrief | None) -> None:
    if brief is None:
        return
    rules = load_rules(ROOT / "config/brief_rules.yaml")
    result = validate_brief(brief, rules)
    if result.is_valid:
        report("PASS", f"业务规则校验通过（warning={len(result.warnings)}）")
    else:
        for issue in result.errors:
            report("FAIL", f"业务规则违反: {issue.code}", issue.message)


def check_summary(brief: BrandBrief | None) -> None:
    path = ROOT / "data/processed/qingxing_brief_summary.md"
    if not path.is_file():
        report("FAIL", "摘要文件缺失")
        return
    text = path.read_text(encoding="utf-8")
    sections = ["卖点与证据状态", "合规边界", "缺失信息清单", "达人搜索画像"]
    missing = [s for s in sections if s not in text]
    if missing:
        report("FAIL", "摘要缺少栏目", "、".join(missing))
    else:
        report("PASS", "摘要核心栏目完整")


def check_creator_profile(brief: BrandBrief | None) -> None:
    if brief is None:
        return
    profile = brief.creator_search_profile
    if profile.search_keywords and profile.excluded_creator_types:
        report("PASS", f"达人搜索画像完整（关键词 {len(profile.search_keywords)} 个）")
    else:
        report("FAIL", "达人搜索画像不完整")


def check_no_stage2_install() -> None:
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    # 只检查真实依赖行，忽略注释
    deps = "\n".join(
        line for line in lines if line.strip() and not line.strip().startswith("#")
    ).lower()
    forbidden = ["xiaohongshu-mcp", "xhs-cli", "playwright", "selenium"]
    hits = [pkg for pkg in forbidden if pkg in deps]
    if hits:
        report("FAIL", "检测到未准入的 Stage 2 组件依赖", "、".join(hits))
    else:
        report("PASS", "未安装 Stage 2 候选组件")


def main() -> int:
    check_files()
    brief = load_brief()
    check_json_against_model(brief)
    check_schema_file()
    check_rules_file()
    check_claim_boundaries(brief)
    check_interest_isolation(brief)
    check_fabrication(brief)
    check_missing_info(brief)
    check_business_rules(brief)
    check_summary(brief)
    check_creator_profile(brief)
    check_no_stage2_install()

    fails = [r for r in results if r[0] == "FAIL"]
    warnings = [r for r in results if r[0] == "WARNING"]
    passes = [r for r in results if r[0] == "PASS"]
    print()
    print(f"汇总: PASS={len(passes)} WARNING={len(warnings)} FAIL={len(fails)}")
    if fails:
        print("Stage 1 validation failed")
        return 1
    print("Stage 1 validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
