"""Stage 0 仓库结构自动化测试。"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent

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

CSV_REQUIRED_HEADER = {
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
}

YAML_FILES = [
    "config/project.yaml",
    "config/quality_gates.yaml",
    "registry/component_requirements.yaml",
    "registry/approved_components.yaml",
    "registry/rejected_components.yaml",
]


@pytest.mark.parametrize("rel_path", REQUIRED_FILES)
def test_required_file_exists(rel_path: str) -> None:
    assert (ROOT / rel_path).is_file(), f"必需文件缺失: {rel_path}"


@pytest.mark.parametrize("rel_path", YAML_FILES)
def test_yaml_valid(rel_path: str) -> None:
    content = (ROOT / rel_path).read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert data is not None, f"YAML 为空或解析失败: {rel_path}"


def test_current_stage_is_valid() -> None:
    data = yaml.safe_load((ROOT / "config/project.yaml").read_text(encoding="utf-8"))
    # Stage 0 已通过验收（97/100），允许推进到 stage_1
    assert data["project"]["current_stage"] in {"stage_0", "stage_1"}


def test_minimum_gate_score_is_90() -> None:
    project = yaml.safe_load((ROOT / "config/project.yaml").read_text(encoding="utf-8"))
    gates = yaml.safe_load((ROOT / "config/quality_gates.yaml").read_text(encoding="utf-8"))
    assert project["project"]["minimum_gate_score"] == 90
    assert gates["quality_gates"]["minimum_gate_score"] == 90


def test_scoring_model_weights_sum_to_100() -> None:
    gates = yaml.safe_load((ROOT / "config/quality_gates.yaml").read_text(encoding="utf-8"))
    dims = gates["quality_gates"]["scoring_model"]["dimensions"]
    assert sum(d["weight"] for d in dims) == 100


def test_env_example_has_no_real_values() -> None:
    content = (ROOT / ".env.example").read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        assert sep, f"非键值行: {line}"
        if key != "LOG_LEVEL":
            assert not value.strip(), f".env.example 含真实值: {key}"


def test_no_dot_env_file() -> None:
    assert not (ROOT / ".env").exists(), "仓库中不应存在 .env"


def test_approved_components_empty() -> None:
    data = yaml.safe_load((ROOT / "registry/approved_components.yaml").read_text(encoding="utf-8"))
    assert data["approved_components"] == [], "Stage 0 不应存在已批准组件"


def test_rejected_components_is_list() -> None:
    data = yaml.safe_load((ROOT / "registry/rejected_components.yaml").read_text(encoding="utf-8"))
    assert isinstance(data["rejected_components"], list)


def test_csv_header_complete() -> None:
    with (ROOT / "registry/component_candidates.csv").open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = set(next(reader, []))
    assert CSV_REQUIRED_HEADER.issubset(header)


def test_csv_example_row_marked_example_only() -> None:
    with (ROOT / "registry/component_candidates.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows, "CSV 应至少包含一行示例"
    for row in rows:
        assert row["status"] != "approved", "示例行不得标记为 approved"


def test_readme_marks_current_stage() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Stage 0 - 项目控制台与组件准入机制" in text
