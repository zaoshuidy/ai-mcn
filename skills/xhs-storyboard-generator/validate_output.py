"""小红书分镜（storyboard）输出校验器。

校验内容：
1. Schema 校验：顶层字段与每个镜头的 21 个必填字段及类型。
2. 时间轴：从 0.0 开始，镜头间连续、无重叠、无空洞；单镜 duration 与起止一致。
3. 总时长：成片总时长与 target_duration_s 的偏差不得超过阈值（默认 3.0s）。
4. 可执行性：camera_motion 命中黑名单（无人机/轨道/摇臂等单人手机无法完成的
   运镜）判失败；shooting_difficulty 枚举校验。
5. 产品露出时点：product_exposure=true 或 product_state 为露出态的镜头，其
   start_time 不得早于脚本的 product_first_appearance_s。

使用方式：
    python validate_output.py storyboard.json [--script script.json] [--max-deviation 3.0]

退出码：0 = 通过（允许 warning），1 = 存在 error 或文件读取失败。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Schema 定义
# ---------------------------------------------------------------------------

REQUIRED_TOP_FIELDS: dict[str, type | tuple[type, ...]] = {
    "schema_version": str,
    "storyboard_id": str,
    "scene": str,
    "aspect_ratio": str,
    "target_duration_s": (int, float),
    "actual_total_duration_s": (int, float),
    "product_first_appearance_s": ((int, float), type(None)),
    "shots": list,
}

REQUIRED_SHOT_FIELDS: dict[str, type | tuple[type, ...]] = {
    "shot_id": str,
    "start_time": (int, float),
    "end_time": (int, float),
    "duration": (int, float),
    "visual": str,
    "shot_size": str,
    "camera_position": str,
    "camera_motion": str,
    "person_action": str,
    "spoken_line": (str, type(None)),
    "on_screen_text": (str, type(None)),
    "product_state": str,
    "product_exposure": bool,
    "props": list,
    "location": str,
    "bgm_or_sound": (str, type(None)),
    "transition": str,
    "shooting_difficulty": str,
    "compliance_note": (str, type(None)),
    "script_source": str,
    "style_evidence": str,
}

ALLOWED_DIFFICULTY = {"easy", "medium", "hard"}

# 单人 + 手机无法完成的运镜黑名单（命中即判失败）。
# 依据：rules.md「可执行性铁律」；反例见 evals.json eval_004。
CAMERA_MOTION_BLACKLIST = (
    "无人机",
    "航拍",
    "穿越机",
    "轨道",
    "滑轨",
    "摇臂",
    "吊臂",
    "升降炮",
    "斯坦尼康",
    "机械臂",
    "索道",
    "飞猫",
)

# 视为产品露出的 product_state 取值。
EXPOSING_PRODUCT_STATES = {
    "入镜静置",
    "手持展示",
    "特写展示",
    "开封/使用中",
    "食用/饮用中",
}

# 时间比较容差（秒），覆盖浮点误差。
EPSILON = 0.05
# 单镜时长低于该值视为不可剪辑执行（过短）。
MIN_SHOT_DURATION_S = 0.5
# 默认成片总时长允许偏差（秒）。
DEFAULT_MAX_DEVIATION_S = 3.0


# ---------------------------------------------------------------------------
# 结果模型
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    """单条校验问题。"""

    code: str
    message: str
    shot_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "shot_id": self.shot_id}


@dataclass
class ValidationResult:
    """校验结果：errors 非空即失败，warnings 仅提示。"""

    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error_codes(self) -> list[str]:
        return [e.code for e in self.errors]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }


# ---------------------------------------------------------------------------
# 单项检查
# ---------------------------------------------------------------------------


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_type(value: Any, expected: type | tuple[type, ...]) -> bool:
    # bool 是 int 的子类，数值字段不接受 bool。
    if expected == (int, float) or expected == ((int, float), type(None)):
        if value is None and type(None) in (expected if isinstance(expected, tuple) else ()):
            return True
        return _is_number(value)
    return isinstance(value, expected)


def check_schema(storyboard: dict[str, Any], result: ValidationResult) -> None:
    """顶层字段与逐镜头字段的存在性与类型校验。"""
    for name, expected in REQUIRED_TOP_FIELDS.items():
        if name not in storyboard:
            result.errors.append(
                ValidationIssue("SCHEMA_MISSING_FIELD", f"顶层缺少必填字段 {name}")
            )
        elif not _check_type(storyboard[name], expected):
            result.errors.append(
                ValidationIssue(
                    "SCHEMA_WRONG_TYPE", f"顶层字段 {name} 类型应为 {expected}"
                )
            )

    shots = storyboard.get("shots")
    if not isinstance(shots, list):
        return  # 顶层类型错误已记录
    if not shots:
        result.errors.append(ValidationIssue("SCHEMA_EMPTY_SHOTS", "shots 为空"))
        return

    for idx, shot in enumerate(shots):
        label = shot.get("shot_id", f"#{idx}") if isinstance(shot, dict) else f"#{idx}"
        if not isinstance(shot, dict):
            result.errors.append(
                ValidationIssue("SCHEMA_WRONG_TYPE", "镜头不是对象", str(label))
            )
            continue
        for name, expected in REQUIRED_SHOT_FIELDS.items():
            if name not in shot:
                result.errors.append(
                    ValidationIssue(
                        "SCHEMA_MISSING_FIELD", f"镜头缺少必填字段 {name}", str(label)
                    )
                )
            elif not _check_type(shot[name], expected):
                result.errors.append(
                    ValidationIssue(
                        "SCHEMA_WRONG_TYPE",
                        f"镜头字段 {name} 类型应为 {expected}",
                        str(label),
                    )
                )
        # 关键叙述字段不得为空串
        for name in ("visual", "person_action", "location", "script_source", "style_evidence"):
            if isinstance(shot.get(name), str) and not shot[name].strip():
                result.errors.append(
                    ValidationIssue(
                        "SCHEMA_EMPTY_VALUE", f"镜头字段 {name} 不得为空串", str(label)
                    )
                )
        difficulty = shot.get("shooting_difficulty")
        if isinstance(difficulty, str) and difficulty not in ALLOWED_DIFFICULTY:
            result.errors.append(
                ValidationIssue(
                    "SCHEMA_BAD_ENUM",
                    f"shooting_difficulty 须为 {sorted(ALLOWED_DIFFICULTY)} 之一，"
                    f"实为 {difficulty}",
                    str(label),
                )
            )


def check_timeline(storyboard: dict[str, Any], result: ValidationResult) -> None:
    """时间轴连续性：从 0 开始、无重叠无空洞、单镜时长自洽。"""
    shots = storyboard.get("shots")
    if not isinstance(shots, list) or not shots:
        return
    valid_shots = [
        s
        for s in shots
        if isinstance(s, dict)
        and _is_number(s.get("start_time"))
        and _is_number(s.get("end_time"))
    ]
    if len(valid_shots) != len(shots):
        return  # 类型问题已由 schema 检查记录

    first = valid_shots[0]
    if abs(first["start_time"] - 0.0) > EPSILON:
        result.errors.append(
            ValidationIssue(
                "TIMELINE_START_NONZERO",
                f"首镜头 start_time={first['start_time']}，须从 0.0 开始",
                str(first.get("shot_id")),
            )
        )

    prev_end: float | None = None
    prev_id: str | None = None
    for shot in valid_shots:
        sid = str(shot.get("shot_id"))
        start, end = float(shot["start_time"]), float(shot["end_time"])
        if end - start < MIN_SHOT_DURATION_S - EPSILON:
            result.errors.append(
                ValidationIssue(
                    "TIMELINE_SHOT_TOO_SHORT",
                    f"镜头时长 {end - start:.2f}s 低于最小可执行时长 {MIN_SHOT_DURATION_S}s",
                    sid,
                )
            )
        if _is_number(shot.get("duration")):
            if abs(float(shot["duration"]) - (end - start)) > EPSILON:
                result.errors.append(
                    ValidationIssue(
                        "TIMELINE_DURATION_MISMATCH",
                        f"duration={shot['duration']} 与 end-start={end - start:.2f} 不一致",
                        sid,
                    )
                )
        if prev_end is not None:
            if start < prev_end - EPSILON:
                result.errors.append(
                    ValidationIssue(
                        "TIMELINE_OVERLAP",
                        f"与上一镜头 {prev_id} 重叠：start={start} < prev_end={prev_end}",
                        sid,
                    )
                )
            elif start > prev_end + EPSILON:
                result.errors.append(
                    ValidationIssue(
                        "TIMELINE_GAP",
                        f"与上一镜头 {prev_id} 存在空洞：start={start} > prev_end={prev_end}",
                        sid,
                    )
                )
        prev_end, prev_id = end, sid

    declared_total = storyboard.get("actual_total_duration_s")
    if prev_end is not None and _is_number(declared_total):
        if abs(float(declared_total) - prev_end) > EPSILON:
            result.errors.append(
                ValidationIssue(
                    "TIMELINE_TOTAL_MISMATCH",
                    f"actual_total_duration_s={declared_total} 与末镜头 end_time={prev_end} 不一致",
                )
            )


def check_total_duration(storyboard: dict[str, Any], result: ValidationResult,
                         max_deviation_s: float) -> None:
    """成片总时长与目标时长偏差检查。"""
    target = storyboard.get("target_duration_s")
    actual = storyboard.get("actual_total_duration_s")
    if not (_is_number(target) and _is_number(actual)):
        return
    deviation = abs(float(actual) - float(target))
    if deviation > max_deviation_s:
        result.errors.append(
            ValidationIssue(
                "TOTAL_DURATION_DEVIATION",
                f"成片总时长 {actual}s 与目标 {target}s 偏差 {deviation:.2f}s，"
                f"超过允许阈值 {max_deviation_s}s",
            )
        )


def check_executability(storyboard: dict[str, Any], result: ValidationResult) -> None:
    """camera_motion 黑名单与难度提示。"""
    shots = storyboard.get("shots")
    if not isinstance(shots, list):
        return
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        sid = str(shot.get("shot_id"))
        motion = shot.get("camera_motion")
        if isinstance(motion, str):
            hits = [term for term in CAMERA_MOTION_BLACKLIST if term in motion]
            if hits:
                result.errors.append(
                    ValidationIssue(
                        "CAMERA_MOTION_NOT_EXECUTABLE",
                        f"camera_motion「{motion}」命中黑名单词 {'/'.join(hits)}："
                        "单人 + 手机无法执行，须改为固定/手持/缓推等可执行运镜",
                        sid,
                    )
                )
        if shot.get("shooting_difficulty") == "hard":
            result.warnings.append(
                ValidationIssue(
                    "DIFFICULTY_HARD",
                    "标记为 hard 的镜头需在拍摄排期中预留重拍余量",
                    sid,
                )
            )
        props = shot.get("props")
        if isinstance(props, list) and len(props) > 8:
            result.warnings.append(
                ValidationIssue(
                    "PROPS_COUNT_HIGH",
                    f"单镜道具 {len(props)} 件超过 8 件，1 人执行难以兼顾",
                    sid,
                )
            )


def check_product_exposure_timing(
    storyboard: dict[str, Any], script: dict[str, Any] | None, result: ValidationResult
) -> None:
    """产品露出不得早于脚本首次出现时点。

    时点取值优先级：script.product_first_appearance_s >
    storyboard.product_first_appearance_s；两者皆无则跳过。
    """
    first_appearance: float | None = None
    if script is not None and _is_number(script.get("product_first_appearance_s")):
        first_appearance = float(script["product_first_appearance_s"])
    elif _is_number(storyboard.get("product_first_appearance_s")):
        first_appearance = float(storyboard["product_first_appearance_s"])
    if first_appearance is None:
        return

    shots = storyboard.get("shots")
    if not isinstance(shots, list):
        return
    for shot in shots:
        if not isinstance(shot, dict) or not _is_number(shot.get("start_time")):
            continue
        exposing = shot.get("product_exposure") is True or (
            shot.get("product_state") in EXPOSING_PRODUCT_STATES
        )
        if exposing and float(shot["start_time"]) < first_appearance - EPSILON:
            result.errors.append(
                ValidationIssue(
                    "PRODUCT_EXPOSURE_TOO_EARLY",
                    f"产品露出镜头 start_time={shot['start_time']} 早于脚本首次出现时点 "
                    f"{first_appearance}s",
                    str(shot.get("shot_id")),
                )
            )


def check_style_hints(storyboard: dict[str, Any], result: ValidationResult) -> None:
    """非阻断性提示：画幅与镜头平均时长。

    镜头平均时长参考真实证据（data/processed/stage_3_top3_video_timelines.json）：
    欧盈Kelly 2.4s / 小季没烦恼 2.5s / 一只牛 2.0s，可接受区间取 1.0–4.0s。
    """
    aspect = storyboard.get("aspect_ratio")
    if isinstance(aspect, str) and aspect != "9:16":
        result.warnings.append(
            ValidationIssue(
                "ASPECT_RATIO_NOT_9_16", f"aspect_ratio={aspect}，小红书竖屏应为 9:16"
            )
        )
    shots = storyboard.get("shots")
    if not isinstance(shots, list) or not shots:
        return
    durations = [
        float(s["end_time"]) - float(s["start_time"])
        for s in shots
        if isinstance(s, dict)
        and _is_number(s.get("start_time"))
        and _is_number(s.get("end_time"))
    ]
    if not durations:
        return
    avg = sum(durations) / len(durations)
    if not 1.0 <= avg <= 4.0:
        result.warnings.append(
            ValidationIssue(
                "AVG_SHOT_OUT_OF_RANGE",
                f"镜头平均时长 {avg:.2f}s 超出真实证据区间 1.0–4.0s"
                "（欧盈Kelly 2.4s / 小季没烦恼 2.5s / 一只牛 2.0s）",
            )
        )


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def validate_storyboard(
    storyboard: dict[str, Any],
    script: dict[str, Any] | None = None,
    *,
    max_deviation_s: float = DEFAULT_MAX_DEVIATION_S,
) -> ValidationResult:
    """校验一份分镜 JSON；script 提供时以其 product_first_appearance_s 为准。"""
    result = ValidationResult()
    if not isinstance(storyboard, dict):
        result.errors.append(
            ValidationIssue("SCHEMA_WRONG_TYPE", "分镜顶层必须是 JSON 对象")
        )
        return result
    check_schema(storyboard, result)
    check_timeline(storyboard, result)
    check_total_duration(storyboard, result, max_deviation_s)
    check_executability(storyboard, result)
    check_product_exposure_timing(storyboard, script, result)
    check_style_hints(storyboard, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="小红书分镜输出校验器")
    parser.add_argument("storyboard", help="分镜 JSON 文件路径")
    parser.add_argument(
        "--script", default=None, help="对应脚本 JSON（可选，用于产品露出时点校验）"
    )
    parser.add_argument(
        "--max-deviation",
        type=float,
        default=DEFAULT_MAX_DEVIATION_S,
        help=f"成片总时长允许偏差秒数，默认 {DEFAULT_MAX_DEVIATION_S}",
    )
    args = parser.parse_args(argv)

    try:
        storyboard = json.loads(Path(args.storyboard).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [{"code": "IO_ERROR", "message": str(exc)}]},
                         ensure_ascii=False, indent=2))
        return 1

    script = None
    if args.script:
        try:
            script = json.loads(Path(args.script).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(json.dumps({"ok": False, "errors": [{"code": "IO_ERROR",
                              "message": f"script 读取失败: {exc}"}]},
                             ensure_ascii=False, indent=2))
            return 1

    result = validate_storyboard(storyboard, script, max_deviation_s=args.max_deviation)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
