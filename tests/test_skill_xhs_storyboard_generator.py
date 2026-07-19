"""skills/xhs-storyboard-generator 分镜校验器单元测试（离线，不依赖小红书）。

覆盖：evals.json 全部 eval（2 正例 + 时间轴/产品露出反例 + 不可执行运镜反例）、
schema 校验、时间轴连续无重叠、总时长偏差、运镜黑名单、产品露出时点、
examples.md 示例与 evals.json 的一致性、CLI 退出码。
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "xhs-storyboard-generator"
VALIDATOR_PATH = SKILL_DIR / "validate_output.py"
EVALS_PATH = SKILL_DIR / "evals.json"
EXAMPLES_PATH = SKILL_DIR / "examples.md"


def _load_validator():
    """按路径加载 validate_output.py（目录名含连字符，不能常规 import）。"""
    spec = importlib.util.spec_from_file_location("xhs_storyboard_validate_output", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    # dataclass 在 from __future__ import annotations 下需按模块名回查 sys.modules
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = _load_validator()


# ---------------------------------------------------------------------------
# 构造工具
# ---------------------------------------------------------------------------


def _shot(**overrides) -> dict:
    """构造一镜合法镜头，可用关键字覆盖。"""
    shot = {
        "shot_id": "s01",
        "start_time": 0.0,
        "end_time": 2.0,
        "duration": 2.0,
        "visual": "俯拍特写：成品早餐放到餐桌中央",
        "shot_size": "特写",
        "camera_position": "俯拍",
        "camera_motion": "固定",
        "person_action": "端起早餐放下",
        "spoken_line": None,
        "on_screen_text": None,
        "product_state": "未出现",
        "product_exposure": False,
        "props": ["餐盘"],
        "location": "餐桌",
        "bgm_or_sound": "环境音",
        "transition": "硬切",
        "shooting_difficulty": "easy",
        "compliance_note": "无卖点表述，无合规风险",
        "script_source": "b1",
        "style_evidence": "一只牛 avg_shot_s=2.0（stage_3_top3_video_timelines.json）",
    }
    shot.update(overrides)
    return shot


def _storyboard(shots: list[dict] | None = None, **overrides) -> dict:
    """构造一份合法分镜：默认 2 镜共 4.0s；总时长默认按末镜头 end_time 推算。"""
    if shots is None:
        shots = [
            _shot(),
            _shot(shot_id="s02", start_time=2.0, end_time=4.0, duration=2.0),
        ]
    total = shots[-1]["end_time"] if shots else 0.0
    board = {
        "schema_version": "1.0",
        "storyboard_id": "sb-test-001",
        "scene": "早餐",
        "aspect_ratio": "9:16",
        "target_duration_s": total,
        "actual_total_duration_s": total,
        "product_first_appearance_s": None,
        "shots": shots,
    }
    board.update(overrides)
    return board


# ---------------------------------------------------------------------------
# evals.json 全量回放
# ---------------------------------------------------------------------------


def test_evals_file_structure():
    data = json.loads(EVALS_PATH.read_text(encoding="utf-8"))
    assert data["skill"] == "xhs-storyboard-generator"
    evals = data["evals"]
    assert len(evals) == 4, "应为 3 真实 eval + 1 反例"
    types = [e["type"] for e in evals]
    assert types.count("positive") == 2
    assert "counter_example" in types
    for e in evals:
        assert {"id", "name", "type", "input", "expect"} <= set(e)
        assert "storyboard" in e["input"]
        assert "ok" in e["expect"]


@pytest.mark.parametrize(
    "eval_case",
    json.loads(EVALS_PATH.read_text(encoding="utf-8"))["evals"],
    ids=lambda e: e["id"],
)
def test_eval_replay(eval_case):
    storyboard = eval_case["input"]["storyboard"]
    script = eval_case["input"].get("script")
    result = validator.validate_storyboard(storyboard, script)
    assert result.ok is eval_case["expect"]["ok"], (
        f"{eval_case['id']} 期望 ok={eval_case['expect']['ok']}，"
        f"实际 errors={result.to_dict()['errors']}"
    )
    expected_codes = set(eval_case["expect"].get("error_codes", []))
    assert expected_codes <= set(result.error_codes())


def test_counter_example_blacklist_terms_named():
    """反例（eval_004）命中的必须是黑名单运镜词。"""
    data = json.loads(EVALS_PATH.read_text(encoding="utf-8"))
    counter = next(e for e in data["evals"] if e["type"] == "counter_example")
    result = validator.validate_storyboard(
        counter["input"]["storyboard"], counter["input"]["script"]
    )
    hits = [e for e in result.errors if e.code == "CAMERA_MOTION_NOT_EXECUTABLE"]
    assert len(hits) == 2, "无人机与轨道两处运镜应各命中一次"
    messages = " ".join(h.message for h in hits)
    assert "无人机" in messages and "轨道" in messages


# ---------------------------------------------------------------------------
# Schema 校验
# ---------------------------------------------------------------------------


def test_schema_missing_top_field():
    board = _storyboard()
    del board["aspect_ratio"]
    result = validator.validate_storyboard(board)
    assert not result.ok
    assert "SCHEMA_MISSING_FIELD" in result.error_codes()


def test_schema_missing_shot_field():
    shot = _shot()
    del shot["camera_motion"]
    result = validator.validate_storyboard(_storyboard(shots=[shot]))
    assert not result.ok
    assert "SCHEMA_MISSING_FIELD" in result.error_codes()


def test_schema_wrong_type():
    shot = _shot(start_time="0.0")
    result = validator.validate_storyboard(_storyboard(shots=[shot]))
    assert not result.ok
    assert "SCHEMA_WRONG_TYPE" in result.error_codes()


def test_schema_bool_not_accepted_as_number():
    shot = _shot(start_time=True)
    result = validator.validate_storyboard(_storyboard(shots=[shot]))
    assert not result.ok
    assert "SCHEMA_WRONG_TYPE" in result.error_codes()


def test_schema_empty_shots():
    result = validator.validate_storyboard(_storyboard(shots=[], actual_total_duration_s=0.0))
    assert not result.ok
    assert "SCHEMA_EMPTY_SHOTS" in result.error_codes()


def test_schema_bad_difficulty_enum():
    shot = _shot(shooting_difficulty="impossible")
    result = validator.validate_storyboard(_storyboard(shots=[shot]))
    assert not result.ok
    assert "SCHEMA_BAD_ENUM" in result.error_codes()


# ---------------------------------------------------------------------------
# 时间轴
# ---------------------------------------------------------------------------


def test_timeline_overlap_fails():
    shots = [
        _shot(end_time=2.5, duration=2.5),
        _shot(shot_id="s02", start_time=2.0, end_time=4.0, duration=2.0),
    ]
    result = validator.validate_storyboard(_storyboard(shots=shots))
    assert not result.ok
    assert "TIMELINE_OVERLAP" in result.error_codes()


def test_timeline_gap_fails():
    shots = [
        _shot(end_time=2.0, duration=2.0),
        _shot(shot_id="s02", start_time=2.6, end_time=4.6, duration=2.0),
    ]
    board = _storyboard(shots=shots, actual_total_duration_s=4.6, target_duration_s=4.6)
    result = validator.validate_storyboard(board)
    assert not result.ok
    assert "TIMELINE_GAP" in result.error_codes()


def test_timeline_start_nonzero_fails():
    shots = [_shot(start_time=1.0, end_time=3.0, duration=2.0)]
    board = _storyboard(shots=shots, actual_total_duration_s=3.0, target_duration_s=3.0)
    result = validator.validate_storyboard(board)
    assert not result.ok
    assert "TIMELINE_START_NONZERO" in result.error_codes()


def test_shot_duration_mismatch_fails():
    shots = [_shot(duration=3.5)]
    result = validator.validate_storyboard(_storyboard(shots=shots))
    assert not result.ok
    assert "TIMELINE_DURATION_MISMATCH" in result.error_codes()


def test_declared_total_mismatch_fails():
    board = _storyboard(actual_total_duration_s=5.0, target_duration_s=5.0)
    result = validator.validate_storyboard(board)
    assert not result.ok
    assert "TIMELINE_TOTAL_MISMATCH" in result.error_codes()


# ---------------------------------------------------------------------------
# 总时长偏差
# ---------------------------------------------------------------------------


def test_total_duration_deviation_fails():
    board = _storyboard(target_duration_s=10.0)  # 实际 4.0s
    result = validator.validate_storyboard(board)
    assert not result.ok
    assert "TOTAL_DURATION_DEVIATION" in result.error_codes()


def test_total_duration_within_tolerance_passes():
    board = _storyboard(target_duration_s=6.5)  # 偏差 2.5s <= 3.0s
    result = validator.validate_storyboard(board)
    assert result.ok


def test_total_duration_custom_threshold():
    board = _storyboard(target_duration_s=5.5)  # 偏差 1.5s
    result = validator.validate_storyboard(board, max_deviation_s=1.0)
    assert not result.ok
    assert "TOTAL_DURATION_DEVIATION" in result.error_codes()


# ---------------------------------------------------------------------------
# 可执行性（运镜黑名单）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "term", ["无人机", "航拍", "穿越机", "轨道", "滑轨", "摇臂", "吊臂", "斯坦尼康"]
)
def test_camera_motion_blacklist_hit_fails(term):
    shot = _shot(camera_motion=f"{term}镜头")
    result = validator.validate_storyboard(_storyboard(shots=[shot]))
    assert not result.ok
    assert "CAMERA_MOTION_NOT_EXECUTABLE" in result.error_codes()


@pytest.mark.parametrize(
    "motion", ["固定", "手持微晃", "缓慢推进", "跟随平移", "俯拍下移", "抬起转向"]
)
def test_camera_motion_whitelist_passes(motion):
    shot = _shot(camera_motion=motion)
    result = validator.validate_storyboard(_storyboard(shots=[shot]))
    assert result.ok


def test_hard_difficulty_only_warns():
    shot = _shot(shooting_difficulty="hard")
    result = validator.validate_storyboard(_storyboard(shots=[shot]))
    assert result.ok
    assert any(w.code == "DIFFICULTY_HARD" for w in result.warnings)


# ---------------------------------------------------------------------------
# 产品露出时点
# ---------------------------------------------------------------------------


def test_product_exposure_before_script_first_appearance_fails():
    script = {"product_first_appearance_s": 6.0}
    shot = _shot(product_exposure=True, product_state="手持展示")  # start_time=0.0
    result = validator.validate_storyboard(
        _storyboard(shots=[shot], product_first_appearance_s=6.0), script
    )
    assert not result.ok
    assert "PRODUCT_EXPOSURE_TOO_EARLY" in result.error_codes()


def test_exposing_state_without_flag_also_fails():
    """product_exposure=false 但 product_state 为露出态，同样判早露。"""
    script = {"product_first_appearance_s": 6.0}
    shot = _shot(product_exposure=False, product_state="特写展示")
    result = validator.validate_storyboard(
        _storyboard(shots=[shot], product_first_appearance_s=6.0), script
    )
    assert not result.ok
    assert "PRODUCT_EXPOSURE_TOO_EARLY" in result.error_codes()


def test_product_exposure_at_first_appearance_passes():
    script = {"product_first_appearance_s": 2.0}
    shots = [
        _shot(),
        _shot(
            shot_id="s02", start_time=2.0, end_time=4.0, duration=2.0,
            product_exposure=True, product_state="入镜静置",
        ),
    ]
    board = _storyboard(shots=shots, product_first_appearance_s=2.0)
    result = validator.validate_storyboard(board, script)
    assert result.ok


def test_script_first_appearance_overrides_storyboard():
    """script 提供时点时以其为准（storyboard 声明更晚也不放行）。"""
    script = {"product_first_appearance_s": 1.0}
    shot = _shot(product_exposure=True, product_state="手持展示")  # start 0.0 < 1.0
    board = _storyboard(shots=[shot], product_first_appearance_s=0.0)
    result = validator.validate_storyboard(board, script)
    assert not result.ok
    assert "PRODUCT_EXPOSURE_TOO_EARLY" in result.error_codes()


def test_no_first_appearance_skips_check():
    shot = _shot(product_exposure=True, product_state="手持展示")
    result = validator.validate_storyboard(_storyboard(shots=[shot]))
    assert result.ok


# ---------------------------------------------------------------------------
# 非阻断提示
# ---------------------------------------------------------------------------


def test_non_9_16_aspect_warns():
    result = validator.validate_storyboard(_storyboard(aspect_ratio="16:9"))
    assert result.ok
    assert any(w.code == "ASPECT_RATIO_NOT_9_16" for w in result.warnings)


def test_avg_shot_out_of_range_warns():
    shots = [_shot(end_time=8.0, duration=8.0)]
    board = _storyboard(shots=shots, actual_total_duration_s=8.0, target_duration_s=8.0)
    result = validator.validate_storyboard(board)
    assert result.ok
    assert any(w.code == "AVG_SHOT_OUT_OF_RANGE" for w in result.warnings)


# ---------------------------------------------------------------------------
# examples.md 与 evals.json 一致性
# ---------------------------------------------------------------------------


def _extract_json_blocks(markdown: str) -> list[dict]:
    blocks = re.findall(r"```json\n(.*?)```", markdown, re.DOTALL)
    return [json.loads(b) for b in blocks]


def test_examples_md_storyboard_valid_and_matches_eval():
    """examples.md 中的分镜 JSON 必须通过校验，且与 eval_001 一致。"""
    data = json.loads(EVALS_PATH.read_text(encoding="utf-8"))
    eval_001 = next(e for e in data["evals"] if e["id"] == "eval_001")
    blocks = _extract_json_blocks(EXAMPLES_PATH.read_text(encoding="utf-8"))
    example_board = next(b for b in blocks if "storyboard_id" in b)
    assert example_board == eval_001["input"]["storyboard"]
    result = validator.validate_storyboard(example_board, eval_001["input"]["script"])
    assert result.ok, f"examples.md 示例未通过校验: {result.to_dict()['errors']}"


def test_examples_md_avg_shot_within_real_evidence_range():
    """示例镜头平均时长须落在真实证据区间 1.0–4.0s（2.0/2.4/2.5s 证据值的包络）。"""
    blocks = _extract_json_blocks(EXAMPLES_PATH.read_text(encoding="utf-8"))
    board = next(b for b in blocks if "storyboard_id" in b)
    durations = [s["end_time"] - s["start_time"] for s in board["shots"]]
    avg = sum(durations) / len(durations)
    assert 1.0 <= avg <= 4.0
    assert 8 <= len(board["shots"]) <= 10, "早餐示例应为 8-10 镜"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_pass_exit_code(tmp_path, capsys):
    board_file = tmp_path / "sb.json"
    board_file.write_text(json.dumps(_storyboard(), ensure_ascii=False), encoding="utf-8")
    code = validator.main([str(board_file)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["ok"] is True


def test_cli_fail_exit_code(tmp_path, capsys):
    shot = _shot(camera_motion="无人机航拍")
    board_file = tmp_path / "sb.json"
    board_file.write_text(
        json.dumps(_storyboard(shots=[shot]), ensure_ascii=False), encoding="utf-8"
    )
    code = validator.main([str(board_file)])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["ok"] is False
    assert any(e["code"] == "CAMERA_MOTION_NOT_EXECUTABLE" for e in out["errors"])


def test_cli_missing_file_exit_code(capsys):
    code = validator.main(["nonexistent_storyboard.json"])
    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False


def test_cli_with_script_file(tmp_path, capsys):
    script_file = tmp_path / "script.json"
    script_file.write_text(
        json.dumps({"product_first_appearance_s": 2.0}, ensure_ascii=False), encoding="utf-8"
    )
    shot = _shot(product_exposure=True, product_state="手持展示")
    board_file = tmp_path / "sb.json"
    board_file.write_text(
        json.dumps(
            _storyboard(shots=[shot], product_first_appearance_s=2.0), ensure_ascii=False
        ),
        encoding="utf-8",
    )
    code = validator.main([str(board_file), "--script", str(script_file)])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert any(e["code"] == "PRODUCT_EXPOSURE_TOO_EARLY" for e in out["errors"])
