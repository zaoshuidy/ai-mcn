"""商单脚本输出校验器（xhs-commercial-script）。

校验项：
1. schema_valid             输出 JSON 结构（pydantic 模型）
2. internal_consistency     标题/时间轴/植入句内部一致性
3. format_requirements      voiceover/subtitle/hybrid 三种形态的载体完整性
4. claim_evidence_coverage  full_script 全部产品卖点句均被 claim_evidence_map 覆盖，
                            证据 ID 存在于 ProductEvidence，且无禁用解读词
5. duration_deviation       estimated_duration 与 target_duration 偏差 <= 30%
6. verbatim_copy_check      不得复制达人原句（语料来自 --input 风格画像与 --timelines 时间线）

用法：
    python validate_output.py OUTPUT.json [--input INPUT.json]
        [--timelines TIMELINES.json] [--target-duration SECONDS] [--min-copy-len N]

退出码：0 = 全部通过；1 = 存在失败项或文件读取错误。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

FORMATS = ("voiceover", "subtitle", "hybrid")
DURATION_TOLERANCE = 0.30
MIN_COPY_LEN = 6

_SPLIT_RE = re.compile(r"[。！？!?；;\n]+")
_NON_WORD_RE = re.compile(r"[^\w]+")
_QUOTE_RE = re.compile(r"[‘'“\"「](.*?)[’'”\"」]")


def normalize(text: str) -> str:
    """归一化文本：小写并去除所有非文字字符（空白、标点、emoji）。"""
    return _NON_WORD_RE.sub("", text.lower())


def split_sentences(text: str) -> list[str]:
    """按中英文句读切句，返回非空句子。"""
    return [s.strip() for s in _SPLIT_RE.split(text) if s.strip()]


def extract_quoted(text: str) -> list[str]:
    """从 do_not_copy 描述中提取引号包裹的原句片段（按 / 再拆分）。"""
    fragments: list[str] = []
    for match in _QUOTE_RE.findall(text):
        for part in re.split(r"[/／]", match):
            part = part.strip()
            if part:
                fragments.append(part)
    return fragments


class Hook(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str = Field(min_length=1)
    duration_s: float = Field(gt=0)
    design_basis: str | None = None


class Segment(BaseModel):
    model_config = ConfigDict(extra="allow")

    segment_id: int
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)
    voiceover: str | None = None
    on_screen_text: str | None = None
    shot_note: str | None = None
    purpose: str | None = None

    @model_validator(mode="after")
    def _check_time_order(self) -> Segment:
        if self.end_time <= self.start_time:
            raise ValueError("end_time 必须大于 start_time")
        return self


class ProductFirstAppearance(BaseModel):
    model_config = ConfigDict(extra="allow")

    time_s: float = Field(ge=0)
    segment_id: int | None = None
    rationale: str | None = None


class ClaimEvidenceEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    script_sentence: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class StyleSource(BaseModel):
    model_config = ConfigDict(extra="allow")

    creator: str | None = None
    note_id: str | None = None
    evidence: str = Field(min_length=1)


class StyleEvidenceEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    script_element: str = Field(min_length=1)
    borrowed_pattern: str = Field(min_length=1)
    source: StyleSource
    adaptation: str | None = None


class ScriptOutput(BaseModel):
    """商单脚本输出契约（详见 references/output-schema.md）。"""

    model_config = ConfigDict(extra="allow")

    format: str | None = None
    title_options: list[str] = Field(min_length=1)
    selected_title: str = Field(min_length=1)
    hook: Hook
    full_script: list[Segment] = Field(min_length=1)
    product_first_appearance: ProductFirstAppearance
    integration_sentence: str = Field(min_length=1)
    CTA: str = Field(min_length=1)
    estimated_duration: float = Field(gt=0)
    claim_evidence_map: list[ClaimEvidenceEntry]
    style_evidence_map: list[StyleEvidenceEntry] = Field(min_length=1)
    unresolved_questions: list[str]


CheckResult = tuple[str, bool, str]


def iter_segment_texts(output: ScriptOutput) -> list[str]:
    texts: list[str] = []
    for seg in output.full_script:
        if seg.voiceover:
            texts.append(seg.voiceover)
        if seg.on_screen_text:
            texts.append(seg.on_screen_text)
    return texts


# 显式重建模型，保证在 importlib 等非常规加载方式下前向引用也能解析。
for _model in (
    Hook,
    Segment,
    ProductFirstAppearance,
    ClaimEvidenceEntry,
    StyleSource,
    StyleEvidenceEntry,
    ScriptOutput,
):
    _model.model_rebuild()


def script_plain_text(output: ScriptOutput) -> str:
    return "\n".join(iter_segment_texts(output))


def output_all_text(output: ScriptOutput) -> str:
    parts = list(output.title_options)
    parts.append(output.selected_title)
    parts.append(output.hook.text)
    parts.extend(iter_segment_texts(output))
    parts.append(output.integration_sentence)
    parts.append(output.CTA)
    return "\n".join(p for p in parts if p)


def check_schema(raw: Any) -> tuple[ScriptOutput | None, CheckResult]:
    if not isinstance(raw, dict):
        return None, ("schema_valid", False, "输出必须是 JSON 对象")
    try:
        output = ScriptOutput.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(x) for x in first["loc"])
        return None, ("schema_valid", False, f"字段 {loc}: {first['msg']}")
    return output, ("schema_valid", True, f"结构合法，{len(output.full_script)} 个分段")


def check_internal_consistency(output: ScriptOutput) -> CheckResult:
    problems: list[str] = []
    if output.selected_title not in output.title_options:
        problems.append("selected_title 不在 title_options 中")
    prev_end: float | None = None
    for seg in output.full_script:
        if prev_end is not None and seg.start_time < prev_end - 1e-6:
            problems.append(f"分段 {seg.segment_id} 起始时间早于上一段结束时间")
        prev_end = seg.end_time
    pfa = output.product_first_appearance.time_s
    if pfa > output.estimated_duration + 1e-6:
        problems.append("product_first_appearance.time_s 超出 estimated_duration")
    elif not any(s.start_time - 0.5 <= pfa <= s.end_time + 0.5 for s in output.full_script):
        problems.append("product_first_appearance.time_s 未落入任何分段区间")
    if normalize(output.integration_sentence) not in normalize(script_plain_text(output)):
        problems.append("integration_sentence 未在 full_script 中逐字出现")
    if problems:
        return ("internal_consistency", False, "；".join(problems))
    return ("internal_consistency", True, "标题/时间轴/首现/植入句一致")


def check_format_requirements(output: ScriptOutput, effective_format: str | None) -> CheckResult:
    if effective_format not in FORMATS:
        return ("format_requirements", False, f"format 缺失或非法: {effective_format!r}")
    problems: list[str] = []
    for seg in output.full_script:
        has_vo = bool(seg.voiceover and seg.voiceover.strip())
        has_st = bool(seg.on_screen_text and seg.on_screen_text.strip())
        if effective_format in ("voiceover", "hybrid") and not has_vo:
            problems.append(f"分段 {seg.segment_id} 缺少 voiceover")
        if effective_format in ("subtitle", "hybrid") and not has_st:
            problems.append(f"分段 {seg.segment_id} 缺少 on_screen_text")
    if problems:
        return ("format_requirements", False, "；".join(problems[:6]))
    return ("format_requirements", True, f"{effective_format} 载体完整")


def check_claim_evidence_coverage(
    output: ScriptOutput, generation_input: dict | None
) -> CheckResult:
    label = "claim_evidence_coverage"
    if not isinstance(generation_input, dict):
        return (label, False, "缺少生成输入（--input），无法校验卖点-证据映射")
    brief = generation_input.get("brand_brief") or {}
    selling = brief.get("selling_points") or []
    evidence = generation_input.get("product_evidence") or []

    claim_lexicon: set[str] = set()
    forbidden: dict[str, str] = {}
    for sp in selling:
        claim = (sp or {}).get("claim")
        if claim:
            claim_lexicon.add(str(claim))
        for item in (sp or {}).get("forbidden_interpretations") or []:
            if item:
                forbidden[str(item)] = str(claim or "")
    evidence_ids: set[str] = set()
    for ev in evidence:
        claim = (ev or {}).get("claim")
        if claim:
            claim_lexicon.add(str(claim))
        eid = (ev or {}).get("evidence_id")
        if eid:
            evidence_ids.add(str(eid))

    problems: list[str] = []
    full_text_norm = normalize(script_plain_text(output))
    for entry in output.claim_evidence_map:
        if entry.claim not in claim_lexicon:
            problems.append(f"映射了输入中不存在的卖点: {entry.claim}")
        for eid in entry.evidence_ids:
            if eid not in evidence_ids:
                problems.append(f"证据 ID 不存在于 ProductEvidence: {eid}")
        if normalize(entry.script_sentence) not in full_text_norm:
            problems.append(f"映射句未在 full_script 中出现: {entry.script_sentence[:20]}…")

    keywords = sorted(claim_lexicon | set(forbidden), key=len, reverse=True)
    entry_index = [(normalize(e.script_sentence), e.claim) for e in output.claim_evidence_map]
    for text in iter_segment_texts(output):
        for sentence in split_sentences(text):
            hits = [k for k in keywords if k in sentence]
            if not hits:
                continue
            for word in hits:
                if word in forbidden:
                    owner = forbidden[word]
                    problems.append(f"出现禁用解读词「{word}」（卖点「{owner}」禁用解读）")
            claim_hits = [k for k in hits if k in claim_lexicon]
            if not claim_hits:
                continue
            sent_norm = normalize(sentence)
            covered = [
                c for s_norm, c in entry_index if s_norm and (s_norm in sent_norm
                                                              or sent_norm in s_norm)
            ]
            if not covered:
                problems.append(f"卖点句未映射证据: {sentence[:24]}…")
                continue
            for claim in claim_hits:
                if claim not in covered:
                    problems.append(f"卖点「{claim}」未在 claim_evidence_map 中映射")
    if problems:
        dedup = list(dict.fromkeys(problems))
        return (label, False, "；".join(dedup[:6]))
    return (label, True, f"{len(output.claim_evidence_map)} 条映射覆盖全部卖点句")


def check_duration(output: ScriptOutput, target_duration: Any) -> CheckResult:
    label = "duration_deviation"
    if target_duration is None:
        return (label, False, "缺少 target_duration（由 --input 或 --target-duration 提供）")
    try:
        target = float(target_duration)
    except (TypeError, ValueError):
        return (label, False, f"target_duration 非数值: {target_duration!r}")
    if target <= 0:
        return (label, False, "target_duration 必须为正数")
    deviation = abs(output.estimated_duration - target) / target
    ok = deviation <= DURATION_TOLERANCE
    detail = (
        f"estimated={output.estimated_duration}s target={target}s "
        f"偏差={deviation:.1%}（上限 {DURATION_TOLERANCE:.0%}）"
    )
    return (label, ok, detail)


def corpus_from_timelines(timelines_data: dict | None) -> list[str]:
    if not isinstance(timelines_data, dict):
        return []
    items: list[str] = []
    for timeline in timelines_data.get("timelines") or []:
        title = timeline.get("title")
        if title:
            items.append(str(title))
        for seg in timeline.get("segments") or []:
            ost = (seg or {}).get("on_screen_text")
            if ost:
                items.extend(split_sentences(str(ost)))
            summary = (seg or {}).get("transcript_summary")
            if summary:
                items.extend(split_sentences(str(summary)))
        style = timeline.get("style_summary") or {}
        for entry in style.get("do_not_copy") or []:
            items.extend(extract_quoted(str(entry)))
    return items


def corpus_from_profile(generation_input: dict | None) -> list[str]:
    if not isinstance(generation_input, dict):
        return []
    profile = generation_input.get("creator_style_profile") or {}
    items: list[str] = []
    for entry in profile.get("do_not_copy") or []:
        items.extend(extract_quoted(str(entry)))
    for ev in profile.get("evidence") or []:
        quote = (ev or {}).get("quote")
        if quote:
            items.extend(split_sentences(str(quote)))
    return items


def check_verbatim_copy(
    output: ScriptOutput, corpus: list[str], min_copy_len: int
) -> CheckResult:
    haystack = normalize(output_all_text(output))
    hits: list[str] = []
    seen: set[str] = set()
    for item in corpus:
        needle = normalize(item)
        if len(needle) < min_copy_len or needle in seen:
            continue
        seen.add(needle)
        if needle in haystack:
            hits.append(item.strip()[:30])
    if hits:
        return ("verbatim_copy_check", False, "疑似复制达人原句: " + "；".join(hits[:5]))
    return ("verbatim_copy_check", True, f"语料 {len(seen)} 条，未发现原句复制")


def validate(
    output_raw: Any,
    *,
    generation_input: dict | None = None,
    timelines: dict | None = None,
    target_duration: Any = None,
    min_copy_len: int = MIN_COPY_LEN,
) -> list[CheckResult]:
    """运行全部校验，返回 (label, ok, detail) 列表。"""
    results: list[CheckResult] = []
    output, schema_result = check_schema(output_raw)
    results.append(schema_result)
    if output is None:
        return results

    results.append(check_internal_consistency(output))

    effective_format: str | None = None
    if isinstance(generation_input, dict):
        fmt = generation_input.get("format")
        effective_format = str(fmt) if fmt else None
    if effective_format is None:
        effective_format = output.format
    results.append(check_format_requirements(output, effective_format))

    results.append(check_claim_evidence_coverage(output, generation_input))

    target = target_duration
    if target is None and isinstance(generation_input, dict):
        target = generation_input.get("target_duration")
    results.append(check_duration(output, target))

    corpus = corpus_from_profile(generation_input) + corpus_from_timelines(timelines)
    results.append(check_verbatim_copy(output, corpus, min_copy_len))
    return results


def _load_json_file(path: str | None, label: str) -> dict | None:
    if path is None:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[FAIL] 读取{label}失败: {exc}")
        raise SystemExit(1) from exc
    if not isinstance(data, dict):
        print(f"[FAIL] {label}必须是 JSON 对象: {path}")
        raise SystemExit(1)
    return data


def main(argv: list[str] | None = None) -> int:
    # 语料可能含 emoji 等字符，非 UTF-8 控制台下降级为替换输出，避免编码崩溃
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="xhs-commercial-script 商单脚本输出校验器")
    parser.add_argument("output", help="待校验的脚本输出 JSON 文件")
    parser.add_argument("--input", dest="input_path", default=None, help="生成输入 JSON 文件")
    parser.add_argument("--timelines", default=None, help="达人视频时间线 JSON（原句语料）")
    parser.add_argument("--target-duration", type=float, default=None, help="目标时长（秒）")
    parser.add_argument("--min-copy-len", type=int, default=MIN_COPY_LEN, help="原句匹配最小长度")
    args = parser.parse_args(argv)

    try:
        output_raw = json.loads(Path(args.output).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[FAIL] 读取输出文件失败: {exc}")
        return 1

    generation_input = _load_json_file(args.input_path, "生成输入")
    timelines = _load_json_file(args.timelines, "时间线语料")

    results = validate(
        output_raw,
        generation_input=generation_input,
        timelines=timelines,
        target_duration=args.target_duration,
        min_copy_len=args.min_copy_len,
    )
    for label, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {label}" + (f" — {detail}" if detail else ""))
    failed = [label for label, ok, _ in results if not ok]
    if failed:
        print(f"\n共 {len(failed)} 项失败: {', '.join(failed)}")
        return 1
    print(f"\n全部 {len(results)} 项校验通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
