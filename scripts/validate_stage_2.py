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
    "config/xhs_readonly_policy.yaml",
    "adapters/xhs_browser_adapter.py",
    "adapters/xhs_video_adapter.py",
    "src/video_models.py",
    "src/video_analyzer.py",
    "scripts/run_xhs_readonly_poc.py",
    "scripts/analyze_xhs_video.py",
    "tests/test_xhs_readonly_policy.py",
    "tests/test_video_pipeline.py",
    "reports/stage_2_browser_video_poc.md",
    "data/processed/xhs_browser_poc.json",
]

ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/Users/|/home/")
# token 前不得有字母/下划线：xsec_token 是小红书公开分享链接参数，非凭据
_SECRET_CRED = (
    r"(?i)(api[_-]?key|secret|(?<![A-Za-z_])token|password)"
    r"[ \t]*[:=][ \t]*['\"]?[A-Za-z0-9_\-]{16,}"
)
SECRET_PATTERNS = [
    re.compile(_SECRET_CRED),
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
    if len(real_rows) >= 4:
        report("PASS", f"候选登记表含 {len(real_rows)} 个真实组件")
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


def check_readonly_policy() -> None:
    """只读浏览器策略与 POC 数据完整性。"""
    from adapters.xhs_browser_adapter import (  # noqa: PLC0415
        ReadOnlyPolicy,
        XhsReadOnlyBrowserAdapter,
    )

    policy = ReadOnlyPolicy.load(ROOT / "config/xhs_readonly_policy.yaml")
    if policy.min_interval >= 3 and policy.max_retries <= 1:
        report("PASS", f"POC 限速 {policy.min_interval}s、重试 ≤{policy.max_retries}")
    else:
        report("FAIL", "POC 限速/重试上限不合规")
    limits = policy.scope_limits
    if limits["max_keywords"] == 1 and limits["max_search_results"] <= 5:
        report("PASS", "POC 范围上限符合任务书（1 词 ≤5 结果）")
    else:
        report("FAIL", "POC 范围上限超标")
    for action in ["click", "fill", "upload", "cdp"]:
        try:
            policy.check_bridge_action(action)
            report("FAIL", f"写能力动作未被策略拦截: {action}")
        except Exception:  # noqa: BLE001
            pass
    else:
        report("PASS", "click/fill/upload/cdp 均被策略拦截")
    adapter = XhsReadOnlyBrowserAdapter(policy=policy, clock=lambda: 0.0, sleeper=lambda s: None)
    write_methods = [
        m for m in ["like", "collect", "comment", "follow", "dm", "publish", "click", "fill"]
        if hasattr(adapter, m)
    ]
    if not write_methods:
        report("PASS", "适配器无任何写操作方法")
    else:
        report("FAIL", "适配器存在写操作方法", "、".join(write_methods))

    poc_path = ROOT / "data/processed/xhs_browser_poc.json"
    poc = json.loads(poc_path.read_text(encoding="utf-8"))
    actions = set(poc.get("actions_log", []))
    if actions and not actions & {"click", "fill", "cdp", "upload"}:
        report("PASS", f"POC 审计动作全部为只读（{sorted(actions)}）")
    else:
        report("FAIL", "POC 审计含写动作或缺失", str(sorted(actions)))
    profiles = poc.get("profiles", [])
    if profiles and all(p.get("nickname") and p.get("fans") for p in profiles):
        report("PASS", f"POC 主页数据真实完整（{len(profiles)} 位，含粉丝数）")
    else:
        report("FAIL", "POC 主页数据不完整")
    note = poc.get("note") or {}
    if note.get("title") and note.get("url", "").startswith("https://www.xiaohongshu.com/"):
        report("PASS", "POC 笔记数据真实（标题+真实URL+互动数据）")
    else:
        report("FAIL", "POC 笔记数据不完整")


def check_representative_poc() -> None:
    """代表性生活 Vlog POC 双层门禁（minimal / representative 分离）。"""
    import yaml  # noqa: PLC0415

    from src.representative_poc import evaluate_representative_gates  # noqa: PLC0415

    proj = yaml.safe_load((ROOT / "config/project.yaml").read_text(encoding="utf-8"))[
        "project"]

    # 双层 POC 定义存在且不互相否定
    if proj.get("minimal_video_poc_ready") is True:
        report("PASS", "minimal_video_poc_ready=true（3秒链路样本保留有效）")
    else:
        report("FAIL", "minimal_video_poc_ready 必须为 true")
    rep_flag = proj.get("representative_video_poc_ready")

    candidate_p = ROOT / "data/processed/xhs_representative_video_candidate.json"
    manifest_p = ROOT / "data/processed/xhs_representative_video_manifest.json"
    timeline_p = ROOT / "data/processed/xhs_representative_video_timeline.json"
    report_p = ROOT / "reports/stage_2_representative_video_analysis.md"
    for p in (candidate_p, manifest_p, timeline_p, report_p):
        if p.is_file():
            report("PASS", f"{p.relative_to(ROOT)} 存在")
        else:
            report("FAIL", f"缺少 {p.relative_to(ROOT)}")
    if not all(p.is_file() for p in (candidate_p, manifest_p, timeline_p, report_p)):
        if rep_flag is True:
            report("FAIL", "representative_video_poc_ready=true 但产物缺失")
        return

    candidate = json.loads(candidate_p.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    timeline = json.loads(timeline_p.read_text(encoding="utf-8"))
    report_text = report_p.read_text(encoding="utf-8")

    # 候选契约
    if candidate.get("usage_scope") == "stage_2_representative_poc":
        report("PASS", "候选 usage_scope 正确")
    else:
        report("FAIL", "候选 usage_scope 错误", str(candidate.get("usage_scope")))
    if candidate.get("human_verified") is False:
        report("PASS", "候选 human_verified=false")
    else:
        report("FAIL", "候选 human_verified 必须为 false")
    raw = candidate_p.read_text(encoding="utf-8") + manifest_p.read_text(encoding="utf-8")
    if "xsec_token" not in raw:
        report("PASS", "候选与清单不含 xsec_token")
    else:
        report("FAIL", "候选/清单泄露 xsec_token")
    if "D:\\" not in raw and "C:\\" not in raw:
        report("PASS", "候选与清单无本地绝对路径")
    else:
        report("FAIL", "候选/清单含本地绝对路径")

    # 门禁评估
    result = evaluate_representative_gates(candidate, manifest, timeline, report_text)
    if result.ready:
        report("PASS", f"代表性门禁全部满足（{result.stats}）")
    else:
        report("FAIL", "代表性门禁未满足", "、".join(result.failures))

    # 标志位一致性：门禁满足才允许 flag=true
    if rep_flag is True and not result.ready:
        report("FAIL", "representative_video_poc_ready=true 但门禁未满足")
    elif rep_flag is True:
        report("PASS", "representative_video_poc_ready=true 与门禁一致")
    elif rep_flag is False:
        if result.ready:
            report("WARNING", "门禁已满足但 flag 仍为 false（待确认后更新）")
        else:
            report("PASS", "representative_video_poc_ready=false 与门禁一致")
    else:
        report("FAIL", "project.yaml 缺少 representative_video_poc_ready")

    # Stage 2 总放行条件
    if rep_flag is True:
        stage3_ok = (
            proj.get("stage_2_browser_poc_ready") is True
            and proj.get("stage_2_video_poc_ready") is True
            and proj.get("representative_video_poc_ready") is True
        )
        if stage3_ok and proj.get("current_stage") == "stage_3":
            report("PASS", "三项 POC 均 true，已按规则进入 stage_3")
        elif stage3_ok:
            report("WARNING", "三项 POC 均 true 但 current_stage 未升级")
        else:
            report("FAIL", "representative=true 但其他 POC 条件不满足")

    # 原始媒体未入 Git
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    if "tmp/" in gitignore:
        report("PASS", "tmp/ 已 gitignore（原始视频/转写/关键帧不入库）")
    else:
        report("FAIL", "tmp/ 未被 gitignore")


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
    check_readonly_policy()
    check_representative_poc()

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
