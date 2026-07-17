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

from src.brief_models import (  # noqa: E402
    BrandBrief,
    BrandInfo,
    ClaimType,
    ComplianceRule,
    MissingInformation,
    ProductVariant,
    SellingPoint,
    UsageScenario,
)
from src.brief_validator import (  # noqa: E402
    ValidationReport,
    build_validation_report,
    load_rules,
    validate_brief,
)

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
    "tests/test_brief_contract.py",
    "scripts/validate_stage_1.py",
    "reports/stage_1_brief_analysis_report.md",
]

ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/Users/|/home/")

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


def check_new_models_exist() -> None:
    """新数据契约模型必须可实例化。"""
    try:
        BrandInfo(brand_name="x", product_name="y")
        ProductVariant(name="原味", confirmed=True, source="brand_brief")
        UsageScenario(name="早餐", priority=1)
        ComplianceRule(category="减肥功效承诺")
        MissingInformation(field="营养成分表", blocks_next_stage=True)
        report(
            "PASS",
            "新模型均可实例化"
            "（BrandInfo/ProductVariant/UsageScenario/ComplianceRule/MissingInformation）",
        )
    except Exception as exc:  # noqa: BLE001
        report("FAIL", "新模型实例化失败", str(exc))


def check_new_structure(brief: BrandBrief | None) -> None:
    """标准 JSON 必须使用新结构。"""
    if brief is None:
        return
    if brief.brand is not None and brief.brand.platform and brief.brand.content_format:
        report("PASS", f"平台与内容形式已拆分: {brief.brand.platform}/{brief.brand.content_format}")
    else:
        report("FAIL", "brand 未拆分平台与内容形式")
    names = [v.name for v in brief.product_variants]
    if names == ["原味", "蓝莓", "黄桃"] and all(v.confirmed for v in brief.product_variants):
        report("PASS", "product_variants 结构化（3 个口味，confirmed）")
    else:
        report("FAIL", "product_variants 不符合预期")
    if brief.usage_scenarios and all(isinstance(s.priority, int) for s in brief.usage_scenarios):
        report("PASS", f"usage_scenarios 结构化（{len(brief.usage_scenarios)} 个场景，整数优先级）")
    else:
        report("FAIL", "usage_scenarios 未结构化")
    categories = {r.category for r in brief.compliance_rules}
    if len(categories) >= 7:
        report("PASS", f"compliance_rules 覆盖 {len(categories)} 类合规规则")
    else:
        report("FAIL", f"compliance_rules 不足 7 类（当前 {len(categories)}）")
    audience = brief.target_audience
    if audience.age_min == 22 and audience.age_max == 35:
        report("PASS", "年龄上下限结构化（22-35）")
    else:
        report("FAIL", "年龄上下限未结构化或与原文不一致")


def check_missing_information_contract(brief: BrandBrief | None) -> None:
    if brief is None:
        return
    if len(brief.missing_information) >= 12:
        report("PASS", f"缺失信息 {len(brief.missing_information)} 项（≥12）")
    else:
        report("FAIL", f"缺失信息不足 12 项（当前 {len(brief.missing_information)}）")
    bad = [m.field for m in brief.missing_information if not isinstance(m.blocks_next_stage, bool)]
    if not bad:
        report("PASS", "每项缺失信息均含 blocks_next_stage")
    else:
        report("FAIL", "存在缺少 blocks_next_stage 的缺失项", "、".join(bad))


def check_validation_report(brief: BrandBrief | None) -> ValidationReport | None:
    if brief is None:
        return None
    rules = load_rules(ROOT / "config/brief_rules.yaml")
    vreport = build_validation_report(brief, rules)
    required_fields = [
        vreport.status,
        isinstance(vreport.score, int),
        isinstance(vreport.errors, list),
        isinstance(vreport.warnings, list),
        isinstance(vreport.blockers, list),
        isinstance(vreport.passed_rules, list),
        isinstance(vreport.stage_2_research_ready, bool),
        isinstance(vreport.stage_2_final_selection_ready, bool),
    ]
    if all(required_fields):
        report("PASS", "ValidationReport 字段完整")
    else:
        report("FAIL", "ValidationReport 字段不完整")
    if 0 <= vreport.score <= 100:
        report("PASS", f"验证分数在 0-100 区间: {vreport.score}")
    else:
        report("FAIL", f"分数越界: {vreport.score}")
    if vreport.stage_2_research_ready and not vreport.stage_2_final_selection_ready:
        report("PASS", "Stage 2 门禁状态符合当前资料完备度（调研可开始，定案阻塞）")
    else:
        report(
            "WARNING",
            "Stage 2 门禁状态",
            f"research={vreport.stage_2_research_ready} "
            f"final={vreport.stage_2_final_selection_ready}",
        )
    return vreport


def check_cap_79_logic() -> None:
    """构造真实性/合规硬伤样例，验证封顶 79 与门禁拦截生效。"""
    brief = load_brief()
    if brief is None:
        report("FAIL", "无法加载 Brief 进行封顶检查")
        return
    rules = load_rules(ROOT / "config/brief_rules.yaml")
    # 虚构营养数值：应命中 FABRICATED_NUTRITION_DATA 且封顶 79
    brief.selling_points.append(
        SellingPoint(claim="高蛋白", claim_type=ClaimType.BRAND_CLAIM, note="含蛋白质15g")
    )
    vreport = build_validation_report(brief, rules)
    if any(i.code == "FABRICATED_NUTRITION_DATA" for i in vreport.errors) and vreport.score <= 79:
        report("PASS", f"虚构数据封顶 79 生效（score={vreport.score}）")
    else:
        report("FAIL", f"虚构数据未正确封顶（score={vreport.score}）")
    if not vreport.stage_2_research_ready:
        report("PASS", "真实性错误时 Stage 2 候选调研被拦截")
    else:
        report("FAIL", "真实性错误时 Stage 2 候选调研未被拦截")


def check_absolute_paths() -> None:
    """公共产物不得含本地绝对路径。"""
    scan_dirs = ["data/processed", "reports", "config"]
    # reports/component_reviews/evidence/ 为第三方仓库逐字引用的审查证据，
    # 其中的路径示例是上游原文，不属于本项目路径泄露
    evidence_dir = "reports/component_reviews/evidence"
    hits: list[str] = []
    for d in scan_dirs:
        dir_path = ROOT / d
        if not dir_path.is_dir():
            continue
        for path in dir_path.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            if rel.startswith(evidence_dir):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if ABSOLUTE_PATH_PATTERN.search(text):
                hits.append(rel)
    if hits:
        report("FAIL", "公共产物含本地绝对路径", "; ".join(hits))
    else:
        report("PASS", "data/processed、reports、config 无本地绝对路径")


def check_source_file_relative(brief: BrandBrief | None) -> None:
    if brief is None:
        return
    is_relative = (
        brief.source_file
        and not Path(brief.source_file).is_absolute()
        and "\\" not in brief.source_file
    )
    if is_relative:
        report("PASS", f"source_file 为相对路径: {brief.source_file}")
    else:
        report("FAIL", f"source_file 不是合法相对路径: {brief.source_file!r}")


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
    check_new_models_exist()
    check_new_structure(brief)
    check_missing_information_contract(brief)
    check_validation_report(brief)
    check_cap_79_logic()
    check_source_file_relative(brief)
    check_absolute_paths()
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
