"""Stage 3 候选筛选与产物合规测试（离线，不依赖小红书）。

覆盖：结构平衡、creator_id/note_id 唯一性、canonical URL 清洗、
Top3 包含关系、风格研究对象边界、禁词状态、human_verified、
敏感信息扫描、截图证据一致性。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"

CANONICAL_RE = re.compile(r"^https://www\.xiaohongshu\.com/explore/[0-9a-f]{24}$")
PROFILE_RE = re.compile(r"^https://www\.xiaohongshu\.com/user/profile/[0-9a-f]{24}$")
FORBIDDEN_SELECTION_STATUS = {
    "commercially_selected",
    "confirmed_collaboration",
    "brand_approved",
}
SENSITIVE_PATTERNS = [
    re.compile(r"xsec_token\s*[=:]"),
    re.compile(r'"xsec_token"\s*:\s*"A'),
    re.compile(r"web_session"),
    re.compile(r"sessionid\s*=", re.IGNORECASE),
]


@pytest.fixture(scope="module")
def artifacts() -> dict:
    def load(name: str):
        return json.loads((PROC / name).read_text(encoding="utf-8"))

    return {
        "pool": load("stage_3_creator_pool.json"),
        "deep": load("stage_3_deep_review_15.json"),
        "scores": load("stage_3_scores.json"),
        "final": load("stage_3_final_10.json"),
        "top3": load("stage_3_top3.json"),
        "style": load("stage_3_style_reference.json"),
        "manifest": load("stage_3_evidence_manifest.json"),
        "timelines": load("stage_3_top3_video_timelines.json"),
    }


# ---- 数量与唯一性 ----

def test_pool_size_meets_minimum(artifacts) -> None:
    candidates = artifacts["pool"].get("candidates", [])
    assert len(candidates) >= 20


def test_pool_creator_ids_unique(artifacts) -> None:
    ids = [c["creator_id"] for c in artifacts["pool"]["candidates"]]
    assert len(ids) == len(set(ids))


def test_deep_review_count_meets_minimum(artifacts) -> None:
    assert len(artifacts["deep"]["creators"]) >= 15


def test_final_count_within_target(artifacts) -> None:
    finalists = artifacts["final"]["finalists"]
    assert 1 <= len(finalists) <= 10


def test_final_creator_ids_unique(artifacts) -> None:
    ids = [c["creator_id"] for c in artifacts["final"]["finalists"]]
    assert len(ids) == len(set(ids))


def test_note_ids_unique_across_finalists(artifacts) -> None:
    ids = [
        n["note_id"]
        for c in artifacts["final"]["finalists"]
        for n in c["representative_notes"]
    ]
    assert len(ids) == len(set(ids))


# ---- URL 与清洗 ----

def test_profile_urls_legal_and_not_nickname_concat(artifacts) -> None:
    for c in artifacts["final"]["finalists"]:
        assert PROFILE_RE.match(c["profile_url"]), c["profile_url"]
        assert c["creator_id"] in c["profile_url"]


def test_canonical_urls_cleaned(artifacts) -> None:
    for c in artifacts["final"]["finalists"]:
        for n in c["representative_notes"]:
            assert CANONICAL_RE.match(n["canonical_url"]), n["canonical_url"]
            assert n["canonical_url"].endswith(n["note_id"])
            assert "xsec_token" not in n["canonical_url"]


def test_each_finalist_has_two_representative_notes(artifacts) -> None:
    for c in artifacts["final"]["finalists"]:
        assert len(c["representative_notes"]) >= 2, c["nickname"]


# ---- 包含关系 ----

def test_top3_subset_of_final(artifacts) -> None:
    final_ids = {c["creator_id"] for c in artifacts["final"]["finalists"]}
    top3_ids = {c["creator_id"] for c in artifacts["top3"]["top3"]}
    assert top3_ids <= final_ids
    assert len(top3_ids) == 3


def test_style_reference_in_top3(artifacts) -> None:
    top3_ids = {c["creator_id"] for c in artifacts["top3"]["top3"]}
    style_id = artifacts["style"]["style_reference"]["creator_id"]
    assert style_id in top3_ids


def test_style_reference_status_boundary(artifacts) -> None:
    sr = artifacts["style"]["style_reference"]
    assert sr["selection_status"] == "research_style_reference"
    assert sr["selection_status"] not in FORBIDDEN_SELECTION_STATUS


def test_style_reference_has_three_video_evidence(artifacts) -> None:
    ev = artifacts["style"]["style_reference"]["video_evidence"]
    count = (1 if ev.get("fully_processed_note_id") else 0) + len(
        ev.get("extra_video_page_evidence", [])
    )
    assert count >= 3


# ---- 禁词与真实性标记 ----

def _walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def test_no_forbidden_selection_status_anywhere(artifacts) -> None:
    for name in ("final", "top3", "style"):
        for k, v in _walk(artifacts[name]):
            if k == "selection_status":
                assert v not in FORBIDDEN_SELECTION_STATUS, f"{name}: {v}"


def test_human_verified_all_false(artifacts) -> None:
    for name in ("pool", "deep", "final"):
        for k, v in _walk(artifacts[name]):
            if k == "human_verified":
                assert v is False, f"{name} 存在 human_verified={v}"


def test_source_separation(artifacts) -> None:
    for c in artifacts["deep"]["creators"]:
        assert c["source"] == "page_observed"
        assert c["audience_inference_source"] == "ai_inferred"


# ---- 结构平衡 ----

def test_structure_balance_recomputed(artifacts) -> None:
    finalists = artifacts["final"]["finalists"]
    voiceover = sum(1 for c in finalists if c["primary_format"] == "voiceover")
    subtitle = sum(1 for c in finalists if c["primary_format"] == "subtitle_immersive")
    commute = sum(
        1 for c in finalists if "通勤/办公室" in (c.get("main_scenes") or [])
    )
    breakfast = sum(
        1
        for c in finalists
        if {"早餐", "一人食"} & set(c.get("main_scenes") or [])
    )
    assert voiceover >= 3
    assert subtitle >= 3
    assert commute >= 2
    assert breakfast >= 2
    # 单一形式不超过 50%
    assert max(voiceover, subtitle) <= len(finalists) / 2


def test_structure_balance_record_matches_recompute(artifacts) -> None:
    recorded = artifacts["final"]["structure_balance"]
    assert recorded["voiceover_min3"]["met"] is True
    assert recorded["subtitle_min3"]["met"] is True
    assert recorded["commute_office_min2"]["met"] is True
    assert recorded["breakfast_solo_min2"]["met"] is True
    # 健身场景未达标须如实记录，不得篡改
    assert recorded["fitness_min2"]["met"] is False
    assert recorded["all_met"] is False


# ---- 敏感信息扫描 ----

@pytest.mark.parametrize(
    "name",
    [
        "stage_3_creator_pool.json",
        "stage_3_prefiltered_30.json",
        "stage_3_deep_review_15.json",
        "stage_3_scores.json",
        "stage_3_final_10.json",
        "stage_3_top3.json",
        "stage_3_style_reference.json",
        "stage_3_top3_video_timelines.json",
        "stage_3_verification_events.json",
    ],
)
def test_no_sensitive_data_in_artifacts(name: str) -> None:
    text = (PROC / name).read_text(encoding="utf-8")
    for pat in SENSITIVE_PATTERNS:
        for m in pat.finditer(text):
            ctx = text[max(0, m.start() - 30): m.end() + 10]
            if re.search(r"(不含|未保存|无)\s*xsec_token", ctx):
                continue
            if re.search(r'xsec_token"?\s*:\s*(null|false|"")', ctx):
                continue
            pytest.fail(f"{name} 命中敏感模式 {pat.pattern}: {ctx}")


# ---- 截图证据 ----

def test_screenshots_exist_and_match_manifest(artifacts) -> None:
    groups = artifacts["manifest"]["screenshots"]
    entries = [e for g in groups.values() for e in g]
    assert len(entries) == 18  # 6 主页 + 12 笔记
    for e in entries:
        path = ROOT / e["path"]
        assert path.is_file(), e["path"]
        assert path.stat().st_size <= 300 * 1024, f"{e['path']} 超过 300KB"


def test_final_screenshot_paths_in_manifest(artifacts) -> None:
    groups = artifacts["manifest"]["screenshots"]
    manifest_paths = {e["path"] for g in groups.values() for e in g}
    for c in artifacts["final"]["finalists"]:
        assert c["profile_screenshot"] in manifest_paths
        for n in c["representative_notes"]:
            assert n["evidence_screenshot"] in manifest_paths


# ---- Top3 视频时间线 ----

def test_top3_video_timelines_complete(artifacts) -> None:
    timelines = artifacts["timelines"]["timelines"]
    assert len(timelines) == 3
    top3_ids = {c["creator_id"] for c in artifacts["top3"]["top3"]}
    finalist_note_ids = {
        n["note_id"]
        for c in artifacts["final"]["finalists"]
        if c["creator_id"] in top3_ids
        for n in c.get("representative_notes", [])
    }
    timeline_creators = set()
    for tl in timelines:
        assert tl["note_id"] in finalist_note_ids
        timeline_creators.add(tl["creator_id"])
        assert len(tl["segments"]) >= 5
        assert tl["file"]["bytes"] > 0
        assert tl["file"]["duration_s"] > 0
        assert re.fullmatch(r"[0-9a-f]{64}", tl["file"]["sha256"])
        assert tl["keyframes"]["valid_interval"] >= 10
    # 每位 Top3 达人各处理 1 条视频
    assert timeline_creators == top3_ids


def test_unreliable_asr_not_fabricated(artifacts) -> None:
    for tl in artifacts["timelines"]["timelines"]:
        if tl["asr_reliability"] == "unreliable":
            for seg in tl["segments"]:
                assert seg.get("transcript_summary") is None, (
                    f"{tl['note_id']} ASR 不可靠但 transcript_summary 非 null"
                )
