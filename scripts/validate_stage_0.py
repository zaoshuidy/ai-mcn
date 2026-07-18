"""Stage 0 自动验证脚本。

检查项目基础仓库是否满足 Stage 0 验收要求。
任何关键检查失败都会以非 0 退出码结束。
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DIRS = [
    "project",
    "registry",
    "config",
    "data",
    "data/raw",
    "data/processed",
    "data/samples",
    "reports",
    "outputs",
    "prompts",
    "skills",
    "adapters",
    "src",
    "tests",
    "docs",
    "scripts",
    "screenshots",
]

REQUIRED_FILES = [
    "README.md",
    ".gitignore",
    ".env.example",
    "requirements.txt",
    "pyproject.toml",
    "project/project_charter.md",
    "project/acceptance_criteria.md",
    "project/role_matrix.md",
    "project/execution_log.md",
    "project/decision_log.md",
    "registry/component_requirements.yaml",
    "registry/component_candidates.csv",
    "registry/approved_components.yaml",
    "registry/rejected_components.yaml",
    "registry/component_scorecard.md",
    "registry/THIRD_PARTY_NOTICES.md",
    "config/project.yaml",
    "config/quality_gates.yaml",
]

CSV_REQUIRED_HEADER = [
    "component_id",
    "name",
    "category",
    "purpose",
    "repository",
    "source_url",
    "stars",
    "last_update",
    "license",
    "business_fit",
    "input_output_compatibility",
    "reproducibility",
    "maintenance_score",
    "security_score",
    "modification_cost",
    "replaceability",
    "final_score",
    "status",
    "review_notes",
]

# token 前不得有字母/下划线：xsec_token 是小红书公开分享链接参数，非凭据
_SECRET_CRED = (
    r"(?i)(api[_-]?key|secret|(?<![A-Za-z_])token|password)"
    r"[ \t]*[:=][ \t]*['\"]?[A-Za-z0-9_\-]{16,}"
)
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(_SECRET_CRED),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
]

SCAN_EXCLUDES = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
SCAN_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".toml", ".txt", ".csv", ".json", ".env"}

results: list[tuple[str, str, str]] = []  # (level, check, message)


def report(level: str, check: str, message: str = "") -> None:
    results.append((level, check, message))
    line = f"[{level}] {check}" + (f" - {message}" if message else "")
    print(line)


def check_dirs() -> None:
    for d in REQUIRED_DIRS:
        if (ROOT / d).is_dir():
            report("PASS", f"目录存在: {d}")
        else:
            report("FAIL", f"目录缺失: {d}")


def check_files() -> None:
    for f in REQUIRED_FILES:
        if (ROOT / f).is_file():
            report("PASS", f"文件存在: {f}")
        else:
            report("FAIL", f"文件缺失: {f}")


def check_env_example() -> None:
    env_example = ROOT / ".env.example"
    if not env_example.is_file():
        report("FAIL", ".env.example 不存在")
        return
    report("PASS", ".env.example 存在")
    content = env_example.read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            report("FAIL", ".env.example 存在非键值行", line)
            continue
        key, _, value = line.partition("=")
        if key != "LOG_LEVEL" and value.strip():
            report("FAIL", ".env.example 含真实值", f"{key} 已赋值")


def check_no_env_committed() -> None:
    env_path = ROOT / ".env"
    if env_path.exists():
        report("FAIL", "仓库中存在 .env 文件")
    else:
        report("PASS", "未发现 .env 文件")
    gitignore = ROOT / ".gitignore"
    if gitignore.is_file():
        text = gitignore.read_text(encoding="utf-8")
        if ".env" in text and "!.env.example" in text:
            report("PASS", ".gitignore 已忽略 .env 并放行 .env.example")
        else:
            report("FAIL", ".gitignore 未正确配置 .env 忽略规则")


def iter_scannable_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in SCAN_EXCLUDES for part in rel.parts):
            continue
        if path.suffix.lower() in SCAN_SUFFIXES or path.name in {".env.example"}:
            yield path


def check_secrets() -> None:
    hits = []
    for path in iter_scannable_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append(str(path.relative_to(ROOT)))
                break
    if hits:
        report("FAIL", "发现疑似密钥", "; ".join(hits))
    else:
        report("PASS", "未发现疑似密钥")


def check_yaml_parseable() -> None:
    yaml_files = [
        "config/project.yaml",
        "config/quality_gates.yaml",
        "registry/component_requirements.yaml",
        "registry/approved_components.yaml",
        "registry/rejected_components.yaml",
    ]
    for f in yaml_files:
        path = ROOT / f
        if not path.is_file():
            report("FAIL", f"YAML 缺失无法解析: {f}")
            continue
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
            report("PASS", f"YAML 可解析: {f}")
        except yaml.YAMLError as exc:
            report("FAIL", f"YAML 解析失败: {f}", str(exc))


def check_csv_header() -> None:
    path = ROOT / "registry/component_candidates.csv"
    if not path.is_file():
        report("FAIL", "component_candidates.csv 缺失")
        return
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, [])
    missing = [c for c in CSV_REQUIRED_HEADER if c not in header]
    if missing:
        report("FAIL", "CSV 表头缺少字段", ", ".join(missing))
    else:
        report("PASS", "CSV 表头完整")
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    example_rows = [r for r in rows if r.get("status") == "example_only"]
    # 合法状态全集（与 src/component_admission.ComponentStatus 一致）；
    # 仅 approved 需要 approved_components.yaml 佐证，其余中间态合法
    legal = {
        "example_only", "pending", "under_review", "poc_required",
        "reference_only", "rejected", "",
    }
    unknown = [r for r in rows if r.get("status") not in legal | {"approved"}]
    fake_approved = [r for r in rows if r.get("status") == "approved"]
    if unknown or fake_approved:
        report("FAIL", "存在被错误标记为已批准的示例/未审查组件")
    elif example_rows:
        report("PASS", "CSV 示例行已标记 example_only")
    else:
        report("WARNING", "CSV 无示例行", "建议保留一行 example_only 示例")


def check_component_lists() -> None:
    for f, key in [
        ("registry/approved_components.yaml", "approved_components"),
        ("registry/rejected_components.yaml", "rejected_components"),
    ]:
        path = ROOT / f
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            report("FAIL", f"组件清单解析失败: {f}", str(exc))
            continue
        if isinstance(data, dict) and isinstance(data.get(key), list):
            report("PASS", f"{key} 已初始化为列表（当前 {len(data[key])} 项）")
        else:
            report("FAIL", f"{key} 未正确初始化为列表: {f}")


def check_readme_stage() -> None:
    readme = ROOT / "README.md"
    if not readme.is_file():
        report("FAIL", "README.md 缺失")
        return
    text = readme.read_text(encoding="utf-8")
    if "Stage 0 - 项目控制台与组件准入机制" in text:
        report("PASS", "README 已标记当前阶段")
    else:
        report("FAIL", "README 未标记当前阶段")
    forbidden_claims = ["达人调研已完成", "脚本生成已完成", "飞书接入已完成"]
    for claim in forbidden_claims:
        if claim in text:
            report("FAIL", "README 含违规完成声明", claim)


def check_gitkeep() -> None:
    empty_candidates = [
        "data/raw",
        "data/processed",
        "data/samples",
        "reports",
        "outputs",
        "prompts",
        "skills",
        "adapters",
        "src",
        "tests",
        "docs",
        "scripts",
        "screenshots",
    ]
    for d in empty_candidates:
        dir_path = ROOT / d
        if not dir_path.is_dir():
            continue  # 目录缺失已在目录检查中报 FAIL
        entries = [p for p in dir_path.iterdir() if p.name != ".gitkeep"]
        py_or_md = [p for p in entries if p.suffix in {".py", ".md"}]
        if not py_or_md and not (dir_path / ".gitkeep").exists():
            report("FAIL", f"空目录缺少 .gitkeep: {d}")
        elif (dir_path / ".gitkeep").exists():
            report("PASS", f".gitkeep 存在: {d}")
        else:
            report("PASS", f"目录已有内容文件: {d}")


def check_current_stage() -> None:
    path = ROOT / "config/project.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        report("FAIL", "project.yaml 无法读取", str(exc))
        return
    stage = (data or {}).get("project", {}).get("current_stage")
    # Stage 0/1 已通过验收，阶段可正常推进；本检查确认阶段值合法且已记录推进
    valid_stages = {"stage_0", "stage_1", "stage_2"}
    if stage in valid_stages:
        report("PASS", f"当前阶段值合法: {stage}（Stage 0 交付物回归检查）")
    else:
        report("FAIL", f"当前阶段应为 {sorted(valid_stages)} 之一，实际为 {stage!r}")


def check_doc_sections() -> None:
    required_sections = {
        "project/project_charter.md": [
            "项目目标", "项目范围", "非本阶段范围", "核心原则", "成功标准",
        ],
        "project/role_matrix.md": ["项目总控", "人工执行者", "技术执行 AI"],
        "project/acceptance_criteria.md": [
            "统一门禁", "Stage 0", "Stage 14", "评分门槛", "失败处理",
        ],
        "README.md": [
            "项目名称", "业务问题", "当前阶段", "阶段验收机制",
            "第三方组件准入机制", "数据真实性原则", "安全原则",
        ],
    }
    for f, sections in required_sections.items():
        path = ROOT / f
        if not path.is_file():
            report("FAIL", f"文档缺失无法检查栏目: {f}")
            continue
        text = path.read_text(encoding="utf-8")
        missing = [s for s in sections if s not in text]
        if missing:
            report("FAIL", f"{f} 缺少核心栏目", ", ".join(missing))
        else:
            report("PASS", f"{f} 核心栏目完整")


def main() -> int:
    check_dirs()
    check_files()
    check_env_example()
    check_no_env_committed()
    check_secrets()
    check_yaml_parseable()
    check_csv_header()
    check_component_lists()
    check_readme_stage()
    check_gitkeep()
    check_current_stage()
    check_doc_sections()

    fails = [r for r in results if r[0] == "FAIL"]
    warnings = [r for r in results if r[0] == "WARNING"]
    passes = [r for r in results if r[0] == "PASS"]

    print()
    print(f"汇总: PASS={len(passes)} WARNING={len(warnings)} FAIL={len(fails)}")
    if fails:
        print("Stage 0 validation failed")
        return 1
    print("Stage 0 validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
