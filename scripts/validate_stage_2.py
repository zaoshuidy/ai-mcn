"""Stage 2 自动验证脚本：组件准入、Creator Schema、搜索策略与受控 POC 边界。

检查 Stage 2 交付物是否齐全、组件治理是否合规、数据真实性与安全边界是否成立。
任何关键检查失败都会以非 0 退出码结束。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.component_admission import (  # noqa: E402
    APPROVE_MIN_SCORE,
    MAX_APPROVED_COMPONENTS,
    ComponentStatus,
    check_registry_consistency,
    is_legal_transition,
    load_candidates,
    load_yaml_list,
)
from src.creator_models import (  # noqa: E402
    AudienceInference,
    CreatorCandidate,
    CreatorIdentity,
    CreatorPost,
    DataSourceType,
    SelectionStatus,
)
from src.creator_search_strategy import (  # noqa: E402
    QueryType,
    SearchPlan,
    load_search_rules,
    validate_plan_against_rules,
)

REQUIRED_FILES = [
    "src/creator_models.py",
    "src/creator_search_strategy.py",
    "src/component_admission.py",
    "config/creator_schema.json",
    "config/creator_search_rules.yaml",
    "data/processed/creator_search_plan.json",
    "data/processed/creator_candidates_poc.json",
    "data/samples/creator_candidate_example.json",
    "reports/stage_2_search_strategy.md",
    "reports/stage_2_poc_report.md",
    "reports/creator_human_review_template.md",
    "reports/component_reviews/CAND-001-xiaohongshu-mcp.md",
    "reports/component_reviews/CAND-002-xhs-cli.md",
    "reports/component_reviews/CAND-003-xiaohongshu-skill.md",
    "reports/component_reviews/CAND-004-browser-mcp.md",
    "registry/component_candidates.csv",
    "registry/approved_components.yaml",
    "registry/rejected_components.yaml",
    "registry/THIRD_PARTY_NOTICES.md",
    "scripts/validate_stage_2.py",
    "tests/test_component_admission.py",
    "tests/test_creator_models.py",
    "tests/test_creator_search_strategy.py",
]

ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/Users/|/home/")
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)[ \t]*[:=][ \t]*['\"]?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(cookie|set-cookie)[ \t]*[:=][ \t]*['\"]?[A-Za-z0-9_\-=;]{20,}"),
]
SENSITIVE_FILENAMES = {"cookies.json", "storage_state.json", ".env"}

results: list[tuple[str, str, str]] = []


def report(level: str, check: str, message: str = "") -> None:
    results.append((level, check, message))
    print(f"[{level}] {check}" + (f" - {message}" if message else ""))


def check_files() -> None:
    for f in REQUIRED_FILES:
        if (ROOT / f).is_file():
            report("PASS", f"文件存在: {f}")
        else:
            report("FAIL", f"文件缺失: {f}")


def check_stage1_regression() -> dict | None:
    """Stage 1 门禁状态仍为：调研可开始、最终定案未放行。"""
    path = ROOT / "data/processed/qingxing_brief.json"
    if not path.is_file():
        report("FAIL", "Stage 1 结构化 Brief 缺失")
        return None
    brief = json.loads(path.read_text(encoding="utf-8"))
    if brief.get("validation_status") in {"ready", "ready_with_warnings"}:
        report("PASS", f"Stage 1 回归：validation_status={brief['validation_status']}")
    else:
        report("FAIL", f"Stage 1 回归失败：validation_status={brief.get('validation_status')}")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_stage_1.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
    )
    if proc.returncode == 0:
        report("PASS", "Stage 1 验证脚本回归通过")
    else:
        report("FAIL", "Stage 1 验证脚本回归失败", proc.stdout.strip().splitlines()[-1:])
    return brief


def check_review_reports() -> None:
    """4 份组件审查报告存在，且每份含许可证与安全结论。"""
    for cid in ["CAND-001", "CAND-002", "CAND-003", "CAND-004"]:
        matches = list((ROOT / "reports/component_reviews").glob(f"{cid}-*.md"))
        if not matches:
            report("FAIL", f"{cid} 审查报告缺失")
            continue
        text = matches[0].read_text(encoding="utf-8")
        has_license = "许可证" in text or "License" in text or "LICENSE" in text
        has_security = "安全" in text and "风险" in text
        has_date = "2026-07-17" in text
        if has_license and has_security and has_date:
            report("PASS", f"{cid} 审查报告含许可证/安全结论与核实日期")
        else:
            report(
                "FAIL",
                f"{cid} 审查报告要素不全",
                f"license={has_license} security={has_security} date={has_date}",
            )


def load_registry() -> tuple[list[dict], list, list]:
    candidates = load_candidates(ROOT / "registry/component_candidates.csv")
    approved = load_yaml_list(ROOT / "registry/approved_components.yaml", "approved_components")
    rejected = load_yaml_list(ROOT / "registry/rejected_components.yaml", "rejected_components")
    return candidates, approved, rejected


def check_component_status_flow(candidates: list[dict], approved: list, rejected: list) -> None:
    """状态机合法：无 pending 直接 approved；approved 必须过 POC 且分数达标。"""
    real_rows = [r for r in candidates if r.get("status") != "example_only"]
    if len(real_rows) == 4:
        report("PASS", "候选登记表含 4 个真实组件")
    else:
        report("FAIL", f"真实组件数异常: {len(real_rows)}")

    legal_statuses = {s.value for s in ComponentStatus}
    bad = [r["component_id"] for r in real_rows if r.get("status") not in legal_statuses]
    if not bad:
        report("PASS", "全部组件状态均为合法枚举值")
    else:
        report("FAIL", "存在非法状态值", "、".join(bad))

    if not is_legal_transition("pending", "approved"):
        report("PASS", "状态机禁止 pending → approved 跳级")
    else:
        report("FAIL", "状态机存在 pending → approved 非法路径")

    for row in real_rows:
        if row.get("status") != ComponentStatus.APPROVED.value:
            continue
        cid = row["component_id"]
        try:
            score = float(row.get("final_score") or 0)
        except ValueError:
            score = 0
        if score < APPROVE_MIN_SCORE:
            report("FAIL", f"{cid} approved 但分数 {score} < {APPROVE_MIN_SCORE}")
        entry = next((c for c in approved if c.get("component_id") == cid), None)
        if entry is None:
            report("FAIL", f"{cid} approved 但未写入 approved_components.yaml")
        elif not entry.get("poc_passed"):
            report("FAIL", f"{cid} approved 但缺少 POC 通过记录")

    if len(approved) <= MAX_APPROVED_COMPONENTS:
        report("PASS", f"approved 组件数 {len(approved)} ≤ {MAX_APPROVED_COMPONENTS}")
    else:
        report("FAIL", f"approved 组件数 {len(approved)} 超过上限 {MAX_APPROVED_COMPONENTS}")

    problems = check_registry_consistency(candidates, approved, rejected)
    if not problems:
        report("PASS", "登记表与批准/拒绝清单一致")
    else:
        for p in problems:
            report("FAIL", "registry 一致性问题", p)


def check_creator_schema() -> None:
    """Creator Schema 合法，样例可被模型校验，推测字段强制 evidence+confidence。"""
    schema_path = ROOT / "config/creator_schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report("FAIL", "creator_schema.json 无法解析", str(exc))
        return
    defs = json.dumps(schema, ensure_ascii=False)
    for key in ["CreatorIdentity", "CreatorPost", "CreatorCandidate", "AudienceInference"]:
        if key in defs:
            report("PASS", f"Schema 含模型定义: {key}")
        else:
            report("FAIL", f"Schema 缺少模型定义: {key}")

    sample_path = ROOT / "data/samples/creator_candidate_example.json"
    try:
        payload = json.loads(sample_path.read_text(encoding="utf-8"))
        CreatorCandidate.model_validate(payload)
        report("PASS", "样例 creator_candidate_example.json 通过模型校验")
    except Exception as exc:  # noqa: BLE001
        report("FAIL", "样例未通过模型校验", str(exc))

    try:
        AudienceInference(
            gender_tendency="女性为主",
            interests=["健身"],
            evidence=[],
            confidence=0.5,
        )
        report("FAIL", "推测字段缺少 evidence 未被拦截")
    except Exception:  # noqa: BLE001
        report("PASS", "推测结论缺少 evidence 时被模型拦截")
    try:
        AudienceInference(evidence=[], confidence=0.5)
        report("FAIL", "无结论但 confidence>0 未被拦截")
    except Exception:  # noqa: BLE001
        report("PASS", "无推测结论时 confidence>0 被模型拦截")


def check_search_plan() -> None:
    """搜索计划 ≥4 组、POC 上限未超、控糖词位置合规。"""
    path = ROOT / "data/processed/creator_search_plan.json"
    if not path.is_file():
        report("FAIL", "creator_search_plan.json 缺失")
        return
    try:
        plan = SearchPlan.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception as exc:  # noqa: BLE001
        report("FAIL", "搜索计划无法被模型校验", str(exc))
        return

    if len(plan.groups) >= 4:
        report("PASS", f"搜索计划含 {len(plan.groups)} 组关键词")
    else:
        report("FAIL", f"搜索计划仅 {len(plan.groups)} 组（要求 ≥4）")

    rules = load_search_rules(ROOT / "config/creator_search_rules.yaml")
    problems = validate_plan_against_rules(plan, rules)
    if not problems:
        report("PASS", "搜索计划未超 POC 上限且控糖词位置合规")
    else:
        for p in problems:
            report("FAIL", "搜索计划违反规则", p)

    required_fields = {"query", "query_type", "business_reason", "expected_creator_type",
                       "risk", "priority", "max_results"}
    raw = json.loads(path.read_text(encoding="utf-8"))
    first_query = next(iter(raw["groups"].values()))[0]
    if required_fields.issubset(first_query.keys()):
        report("PASS", "搜索词字段完整（7 个必填字段）")
    else:
        report("FAIL", "搜索词字段不完整", str(required_fields - first_query.keys()))

    for q in plan.all_queries:
        if "控糖" in q.query and q.query_type not in (QueryType.AUDIENCE, QueryType.CONTENT):
            report("FAIL", f"控糖词 {q.query} 出现在违规组别 {q.query_type.value}")
            break
    else:
        report("PASS", "控糖仅作为人群/内容搜索词")


def check_poc_boundaries() -> None:
    """POC 边界：候选池状态合法、禁止行为清单完整、无自动互动。"""
    path = ROOT / "data/processed/creator_candidates_poc.json"
    try:
        pool = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report("FAIL", "creator_candidates_poc.json 无法解析", str(exc))
        return
    candidates = pool.get("candidates", [])
    bad_verified = [c for c in candidates if c.get("human_verified")]
    bad_status = [
        c for c in candidates if c.get("selection_status") != SelectionStatus.POC_CANDIDATE.value
    ]
    if not bad_verified and not bad_status:
        report("PASS", f"POC 候选池合规（{len(candidates)} 条，human_verified 全为 false）")
    else:
        report("FAIL", "POC 候选池存在未授权状态升级")
    if pool.get("_metadata", {}).get("final_selection_ready") is False:
        report("PASS", "最终达人定案保持未放行")
    else:
        report("FAIL", "最终达人定案状态异常")

    rules = load_search_rules(ROOT / "config/creator_search_rules.yaml")
    prohibited = set(rules.get("prohibited_behaviors", []))
    required_prohibitions = {
        "bypass_captcha", "auto_like", "auto_collect", "auto_comment",
        "auto_follow", "auto_dm", "auto_publish", "infinite_scroll",
    }
    if required_prohibitions.issubset(prohibited):
        report("PASS", f"禁止行为清单完整（{len(prohibited)} 项）")
    else:
        report("FAIL", "禁止行为清单缺失", "、".join(required_prohibitions - prohibited))
    login = rules.get("login_policy", {})
    if login.get("mode") == "manual_gate" and login.get("forbid_cookie_handover_to_ai"):
        report("PASS", "登录人工门禁规则已配置")
    else:
        report("FAIL", "登录人工门禁规则缺失")


def check_sensitive_leak() -> None:
    """无 Cookie/Token/Session/密钥进入 Git，无绝对路径泄露。"""
    proc = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
        check=True,
    )
    tracked = [line.strip() for line in proc.stdout.splitlines() if line.strip()]

    sensitive = [f for f in tracked if Path(f).name.lower() in SENSITIVE_FILENAMES]
    if not sensitive:
        report("PASS", "Git 未跟踪 Cookie/Session/.env 文件")
    else:
        report("FAIL", "Git 跟踪了敏感文件", "、".join(sensitive))

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    missing_ignores = [
        p for p in ["cookies.json", "storage_state.json", ".env", "*.key", "*.pem", "*.token"]
        if p not in gitignore
    ]
    if not missing_ignores:
        report("PASS", ".gitignore 覆盖登录态与密钥文件")
    else:
        report("FAIL", ".gitignore 缺少忽略规则", "、".join(missing_ignores))

    hits: list[str] = []
    abs_hits: list[str] = []
    scan_dirs = ["data", "reports", "config", "registry", "src", "scripts"]
    # reports/component_reviews/evidence/ 为第三方仓库逐字引用的审查证据，
    # 其中的路径示例（如 /Users/username/...）是上游原文，不属于本项目路径泄露
    evidence_dir = "reports/component_reviews/evidence"
    for d in scan_dirs:
        dir_path = ROOT / d
        if not dir_path.is_dir():
            continue
        for path in dir_path.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            if rel.startswith(evidence_dir):
                continue
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    hits.append(rel)
                    break
            if d in {"data", "reports", "config"} and ABSOLUTE_PATH_PATTERN.search(text):
                abs_hits.append(rel)
    if not hits:
        report("PASS", "未发现疑似密钥/Cookie 字符串")
    else:
        report("FAIL", "发现疑似密钥/Cookie 字符串", "、".join(sorted(set(hits))))
    if not abs_hits:
        report("PASS", "data/reports/config 无本地绝对路径")
    else:
        report("FAIL", "公共产物含本地绝对路径", "、".join(sorted(set(abs_hits))))


def check_notices_consistency(approved: list) -> None:
    """approved_components 与 THIRD_PARTY_NOTICES 一致。"""
    notices = (ROOT / "registry/THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    if not approved:
        if "无任何已批准的第三方组件" in notices or "当前组件清单" in notices:
            report("PASS", "无 approved 组件，第三方声明一致（空清单）")
        else:
            report("FAIL", "第三方声明与空 approved 清单不一致")
        return
    for comp in approved:
        name = comp.get("name", "")
        if name and name in notices:
            report("PASS", f"approved 组件 {name} 已记录于 THIRD_PARTY_NOTICES")
        else:
            report("FAIL", f"approved 组件 {name} 未记录于 THIRD_PARTY_NOTICES")


def check_model_instantiation() -> None:
    """Stage 2 新模型均可实例化。"""
    try:
        CreatorIdentity(
            creator_id="u1", nickname="n", profile_url="https://example.com/u1"
        )
        CreatorPost(post_id="p1", url="https://example.com/p1")
        AudienceInference(evidence=[], confidence=0.0)
        CreatorCandidate(
            creator=CreatorIdentity(
                creator_id="u1", nickname="n", profile_url="https://example.com/u1"
            ),
            collection_source="manual_search",
        )
        DataSourceType.PAGE_OBSERVED
        report("PASS", "Stage 2 模型均可实例化（含来源类型枚举）")
    except Exception as exc:  # noqa: BLE001
        report("FAIL", "Stage 2 模型实例化失败", str(exc))


def main() -> int:
    check_files()
    check_stage1_regression()
    check_review_reports()
    candidates, approved, rejected = load_registry()
    check_component_status_flow(candidates, approved, rejected)
    check_creator_schema()
    check_search_plan()
    check_poc_boundaries()
    check_sensitive_leak()
    check_notices_consistency(approved)
    check_model_instantiation()

    fails = [r for r in results if r[0] == "FAIL"]
    warnings = [r for r in results if r[0] == "WARNING"]
    passes = [r for r in results if r[0] == "PASS"]
    print()
    print(f"汇总: PASS={len(passes)} WARNING={len(warnings)} FAIL={len(fails)}")
    if fails:
        print("Stage 2 validation failed")
        return 1
    print("Stage 2 validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
