"""creator-style-distiller 输出校验器。

校验风格蒸馏输出 JSON 是否符合 references/output-schema.md：
必填字段、字段类型、confidence 取值范围、evidence_timestamps 非空，
以及禁复制检查（输出中不得出现与输入 transcript 超过 15 字的连续相同子串）。

独立运行：
    python skills/creator-style-distiller/scripts/validate_output.py <out.json> [--input <in.json>]

退出码：0 = 通过；1 = 校验失败；2 = 用法/文件错误。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

# 禁复制阈值：超过 15 字的连续相同子串即判失败。
MAX_COPIED_RUN = 15

VOICEOVER_MODES = {"voiceover", "subtitle_immersive", "mixed", "none"}
SUBTITLE_LEVELS = {"none", "low", "medium", "high"}

# 输入 JSON 中视为 transcript 类文本的字段名（递归收集）。
TRANSCRIPT_KEYS = {
    "transcript",
    "transcript_summary",
    "on_screen_text",
    "asr_text",
    "subtitle",
    "subtitles",
    "voiceover_text",
}

WHITESPACE_RE = re.compile(r"\s+")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _collect_strings(node: Any, out: list[str]) -> None:
    """递归收集节点中的全部字符串值。"""
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for value in node.values():
            _collect_strings(value, out)
    elif isinstance(node, list):
        for item in node:
            _collect_strings(item, out)


def _collect_transcript_texts(node: Any, out: list[str]) -> None:
    """递归收集输入 JSON 中 transcript 类字段的字符串。"""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in TRANSCRIPT_KEYS and isinstance(value, str):
                out.append(value)
            else:
                _collect_transcript_texts(value, out)
    elif isinstance(node, list):
        for item in node:
            _collect_transcript_texts(item, out)


def _strip_ws(text: str) -> str:
    return WHITESPACE_RE.sub("", text)


def _check_string_list(errors: list[str], field: str, value: Any, *, non_empty: bool) -> None:
    if not isinstance(value, list):
        errors.append(f"{field}: 应为 array<string>")
        return
    if non_empty and not value:
        errors.append(f"{field}: 不允许为空数组")
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field}[{i}]: 应为非空 string")


def _check_pattern_items(
    errors: list[str],
    field: str,
    value: Any,
    required_keys: tuple[str, ...],
    *,
    non_empty: bool,
) -> None:
    if not isinstance(value, list):
        errors.append(f"{field}: 应为 array<object>")
        return
    if non_empty and not value:
        errors.append(f"{field}: 不允许为空数组")
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{field}[{i}]: 应为 object")
            continue
        for key in required_keys:
            if not isinstance(item.get(key), str) or not str(item.get(key, "")).strip():
                errors.append(f"{field}[{i}].{key}: 应为非空 string")
        ts = item.get("timestamps")
        if ts is not None and (
            not isinstance(ts, list) or not all(_is_number(t) for t in ts)
        ):
            errors.append(f"{field}[{i}].timestamps: 应为 array<number>")
        ip = item.get("insertion_point_s")
        if ip is not None and not _is_number(ip):
            errors.append(f"{field}[{i}].insertion_point_s: 应为 number")


def validate_output(data: Any, transcript_texts: list[str] | None = None) -> list[str]:
    """校验输出对象，返回错误信息列表（空列表 = 通过）。"""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["顶层必须是 JSON object"]

    required = [
        "hook_patterns",
        "narrative_structure",
        "sentence_rhythm",
        "voiceover_density",
        "subtitle_density",
        "shot_rhythm",
        "scene_patterns",
        "food_integration_patterns",
        "commercial_integration_patterns",
        "CTA_patterns",
        "reusable_style_rules",
        "creator_specific_elements_not_to_copy",
        "confidence",
        "evidence_timestamps",
    ]
    for field in required:
        if field not in data:
            errors.append(f"缺少必填字段: {field}")
    if errors:
        return errors

    # --- 数组型 pattern 字段 ---
    _check_pattern_items(errors, "hook_patterns", data["hook_patterns"], ("pattern", "evidence"),
                         non_empty=True)
    _check_pattern_items(errors, "scene_patterns", data["scene_patterns"], ("scene",),
                         non_empty=True)
    _check_pattern_items(errors, "food_integration_patterns",
                         data["food_integration_patterns"], ("pattern", "evidence"),
                         non_empty=False)
    _check_pattern_items(errors, "commercial_integration_patterns",
                         data["commercial_integration_patterns"], ("pattern", "evidence"),
                         non_empty=False)
    _check_pattern_items(errors, "CTA_patterns", data["CTA_patterns"], ("pattern",),
                         non_empty=False)

    # --- narrative_structure ---
    ns = data["narrative_structure"]
    if not isinstance(ns, dict):
        errors.append("narrative_structure: 应为 object")
    else:
        if not isinstance(ns.get("arc"), str) or not ns.get("arc", "").strip():
            errors.append("narrative_structure.arc: 应为非空 string")
        phases = ns.get("phases")
        if not isinstance(phases, list) or not phases:
            errors.append("narrative_structure.phases: 应为非空 array")
        elif isinstance(phases, list):
            for i, phase in enumerate(phases):
                if not isinstance(phase, dict):
                    errors.append(f"narrative_structure.phases[{i}]: 应为 object")
                    continue
                for key in ("name", "description"):
                    if not isinstance(phase.get(key), str) or not phase.get(key, "").strip():
                        errors.append(f"narrative_structure.phases[{i}].{key}: 应为非空 string")
                tr = phase.get("time_range_s")
                if tr is not None and (
                    not isinstance(tr, list)
                    or len(tr) != 2
                    or not all(_is_number(t) for t in tr)
                ):
                    errors.append(
                        f"narrative_structure.phases[{i}].time_range_s: 应为 [number, number]"
                    )

    # --- sentence_rhythm ---
    sr = data["sentence_rhythm"]
    if not isinstance(sr, dict):
        errors.append("sentence_rhythm: 应为 object")
    else:
        if not isinstance(sr.get("style"), str) or not sr.get("style", "").strip():
            errors.append("sentence_rhythm.style: 应为非空 string")
        features = sr.get("features")
        if not isinstance(features, list) or not all(isinstance(f, str) for f in features or []):
            errors.append("sentence_rhythm.features: 应为 array<string>")
        avg_len = sr.get("avg_sentence_length_chars")
        if avg_len is not None and not _is_number(avg_len):
            errors.append("sentence_rhythm.avg_sentence_length_chars: 应为 number")

    # --- voiceover_density ---
    vd = data["voiceover_density"]
    if not isinstance(vd, dict):
        errors.append("voiceover_density: 应为 object")
    else:
        if vd.get("mode") not in VOICEOVER_MODES:
            errors.append(
                "voiceover_density.mode: 应为枚举 voiceover/subtitle_immersive/mixed/none"
            )
        ratio = vd.get("estimated_speech_ratio")
        if ratio is not None and (not _is_number(ratio) or not 0 <= ratio <= 1):
            errors.append("voiceover_density.estimated_speech_ratio: 应为 0-1 的 number")

    # --- subtitle_density ---
    sd = data["subtitle_density"]
    if not isinstance(sd, dict):
        errors.append("subtitle_density: 应为 object")
    else:
        if sd.get("level") not in SUBTITLE_LEVELS:
            errors.append("subtitle_density.level: 应为枚举 none/low/medium/high")
        functions = sd.get("functions")
        if not isinstance(functions, list) or not all(isinstance(f, str) for f in functions or []):
            errors.append("subtitle_density.functions: 应为 array<string>")

    # --- shot_rhythm ---
    sh = data["shot_rhythm"]
    if not isinstance(sh, dict):
        errors.append("shot_rhythm: 应为 object")
    else:
        if not _is_number(sh.get("avg_shot_s")) or sh.get("avg_shot_s", 0) <= 0:
            errors.append("shot_rhythm.avg_shot_s: 应为 > 0 的 number")
        if not isinstance(sh.get("pacing"), str) or not sh.get("pacing", "").strip():
            errors.append("shot_rhythm.pacing: 应为非空 string")
        shot_types = sh.get("shot_types")
        if not isinstance(shot_types, list) or not all(
            isinstance(t, str) for t in shot_types or []
        ):
            errors.append("shot_rhythm.shot_types: 应为 array<string>")

    # --- 字符串数组字段 ---
    _check_string_list(errors, "reusable_style_rules", data["reusable_style_rules"],
                       non_empty=True)
    _check_string_list(errors, "creator_specific_elements_not_to_copy",
                       data["creator_specific_elements_not_to_copy"], non_empty=True)

    # --- confidence ---
    confidence = data["confidence"]
    if not _is_number(confidence) or not 0 <= confidence <= 1:
        errors.append("confidence: 应为 0-1 的 number")

    # --- evidence_timestamps ---
    ets = data["evidence_timestamps"]
    if not isinstance(ets, list) or not ets:
        errors.append("evidence_timestamps: 应为非空 array")
    elif isinstance(ets, list):
        for i, item in enumerate(ets):
            if _is_number(item):
                continue
            if isinstance(item, list) and len(item) == 2 and all(_is_number(t) for t in item):
                continue
            errors.append(f"evidence_timestamps[{i}]: 应为 number 或 [number, number]")

    # --- 禁复制检查 ---
    if transcript_texts is not None:
        errors.extend(_check_no_verbatim_copy(data, transcript_texts))

    return errors


def _check_no_verbatim_copy(data: Any, transcript_texts: list[str]) -> list[str]:
    """输出字符串与输入 transcript 不得有 >15 字连续相同子串（剔除空白后比较）。"""
    errors: list[str] = []
    output_strings: list[str] = []
    _collect_strings(data, output_strings)
    sources = [s for s in (_strip_ws(t) for t in transcript_texts) if len(s) > MAX_COPIED_RUN]
    for out in output_strings:
        normalized = _strip_ws(out)
        if len(normalized) <= MAX_COPIED_RUN:
            continue
        for src in sources:
            match = SequenceMatcher(None, normalized, src).find_longest_match()
            if match.size > MAX_COPIED_RUN:
                copied = normalized[match.a: match.a + match.size]
                errors.append(
                    f"禁复制检查失败: 输出含与输入 transcript 连续 {match.size} 字相同子串"
                    f"（阈值 {MAX_COPIED_RUN}）: 「{copied[:40]}…」"
                )
                return errors  # 命中即报，避免刷屏
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="校验 creator-style-distiller 输出 JSON 是否符合 output-schema。"
    )
    parser.add_argument("output", help="待校验的输出 JSON 文件路径")
    parser.add_argument(
        "--input",
        default=None,
        help="可选：蒸馏输入 JSON（含 timeline/transcript），提供时执行禁复制检查",
    )
    args = parser.parse_args(argv)

    output_path = Path(args.output)
    if not output_path.is_file():
        print(f"[FAIL] 输出文件不存在: {output_path}")
        return 2
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"[FAIL] 输出文件无法解析为 JSON: {exc}")
        return 2

    transcript_texts: list[str] | None = None
    if args.input is not None:
        input_path = Path(args.input)
        if not input_path.is_file():
            print(f"[FAIL] 输入文件不存在: {input_path}")
            return 2
        try:
            input_data = json.loads(input_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"[FAIL] 输入文件无法解析为 JSON: {exc}")
            return 2
        transcript_texts = []
        _collect_transcript_texts(input_data, transcript_texts)
        if not transcript_texts:
            print("[WARN] 输入中未找到 transcript 类字段，禁复制检查无对照文本")
    else:
        print("[WARN] 未提供 --input，跳过禁复制检查（交付前必须带 --input 复检）")

    errors = validate_output(data, transcript_texts)
    if errors:
        for line in errors:
            print(f"[FAIL] {line}")
        print(f"\n校验未通过：{len(errors)} 个问题。")
        return 1
    print("[PASS] 输出符合 creator-style-distiller output-schema。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
