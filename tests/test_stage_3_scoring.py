"""Stage 3 评分模型单元测试（离线，不依赖小红书）。

覆盖：8 维度边界、身材焦虑扣分档、证据缺失封顶、未深核封顶、
孕晚期受众封顶、分级边界、评分可复现性。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.stage_3_scoring import (
    DIMENSION_MAX,
    EVIDENCE_CAP_SCORE,
    MIN_FORMAL_SCORE,
    NO_DEEP_REVIEW_CAP,
    TOTAL_MAX,
    body_anxiety_penalty,
    evidence_completeness,
    grade_of,
    score_creator,
    score_target_audience,
)

ROOT = Path(__file__).resolve().parent.parent


def _base_creator(**overrides) -> dict:
    """构造一位完整证据的合格候选（所有维度可得分的最小输入）。"""
    creator = {
        "creator_id": "a" * 24,
        "nickname": "测试达人",
        "bio": "独居打工人，记录一人食与日常vlog",
        "followers": "10000",
        "latest_post_time": "2026-07-01T00:00:00+00:00",
        "posts_reviewed_count": 10,
        "video_posts_in_recent10": 9,
        "commercial_posts_count": 0,
        "commercial_post_ratio": 0.0,
        "content_categories": ["一人食", "早餐"],
        "main_scenes": ["一人食", "早餐", "下午茶"],
        "primary_format": "voiceover",
        "recent_titles_sample": ["独居早餐vlog｜三明治与咖啡", "一人食日常记录"],
        "representative_notes": [
            {
                "note_id": "b" * 24,
                "title": "独居早餐vlog｜三明治与咖啡",
                "publish_time": "2026-07-01T00:00:00+00:00",
                "note_type": "video",
                "duration_seconds": 60.0,
                "likes": "100",
                "has_voiceover": True,
                "has_on_screen_text": True,
            },
            {
                "note_id": "c" * 24,
                "title": "一人食日常记录",
                "publish_time": "2026-06-20T00:00:00+00:00",
                "note_type": "video",
                "duration_seconds": 90.0,
                "likes": "80",
                "has_voiceover": True,
                "has_on_screen_text": False,
            },
        ],
    }
    creator.update(overrides)
    return creator


# ---- 分级边界 ----

@pytest.mark.parametrize(
    ("total", "expected"),
    [
        (100, "重点候选"),
        (90, "重点候选"),
        (89, "正式研究候选"),
        (85, "正式研究候选"),
        (84, "仅风格参考"),
        (80, "仅风格参考"),
        (79, "淘汰"),
        (0, "淘汰"),
    ],
)
def test_grade_boundaries(total: int, expected: str) -> None:
    assert grade_of(total) == expected


def test_dimension_max_sums_to_100() -> None:
    assert TOTAL_MAX == 100
    assert sum(DIMENSION_MAX.values()) == 100


# ---- 身材焦虑扣分档 ----

def test_penalty_none_for_clean_creator() -> None:
    penalty, reason = body_anxiety_penalty(_base_creator())
    assert penalty == 0
    assert reason == ""


def test_penalty_bio_anxiety_keyword_minus5() -> None:
    penalty, _ = body_anxiety_penalty(_base_creator(bio="减脂期也要好好吃饭"))
    assert penalty == 5


def test_penalty_bio_body_metrics_minus3() -> None:
    penalty, _ = body_anxiety_penalty(_base_creator(bio="166/51 记录日常"))
    assert penalty == 3


def test_penalty_bio_anxiety_plus_metrics_minus8() -> None:
    # 白菜张张型：bio 人设级 -5 + 身高体重数字 -3
    penalty, _ = body_anxiety_penalty(_base_creator(bio="维持体重中 166/51"))
    assert penalty == 8


def test_penalty_single_title_minus3() -> None:
    creator = _base_creator(recent_titles_sample=["维持体重的一天吃什么"])
    creator["representative_notes"] = []
    penalty, _ = body_anxiety_penalty(creator)
    assert penalty == 3


def test_penalty_two_distinct_titles_minus5() -> None:
    creator = _base_creator(
        recent_titles_sample=["掉秤日记day1", "暴瘦食谱分享"],
    )
    creator["representative_notes"] = []
    penalty, _ = body_anxiety_penalty(creator)
    assert penalty == 5


def test_penalty_duplicate_titles_deduped() -> None:
    creator = _base_creator(
        recent_titles_sample=["掉秤日记", "掉秤日记"],
        representative_notes=[{"title": "掉秤日记"}],
    )
    penalty, _ = body_anxiety_penalty(creator)
    assert penalty == 3  # 去重后仅 1 条


def test_penalty_tiers_sum_and_never_exceed_15() -> None:
    # 全部档位同时命中：bio 人设级 -5 + 身高体重 -3 + 标题内容级 -5 = 13（上限 15 内）
    creator = _base_creator(
        bio="减脂瘦身 166/51",
        recent_titles_sample=["掉秤日记", "暴瘦食谱", "燃脂打卡"],
    )
    penalty, _ = body_anxiety_penalty(creator)
    assert penalty == 13
    assert penalty <= 15


# ---- 封顶规则 ----

def test_no_deep_review_cap_79() -> None:
    creator = _base_creator(posts_reviewed_count=0)
    result = score_creator(creator)
    assert result["total"] <= NO_DEEP_REVIEW_CAP
    assert any("封顶" in c for c in result["caps_applied"])


def test_evidence_missing_cap_84() -> None:
    creator = _base_creator()
    # 删除超过 20% 的证据字段
    for note in creator["representative_notes"]:
        for key in ("duration_seconds", "likes", "has_voiceover", "has_on_screen_text"):
            note[key] = None
    creator["bio"] = ""
    creator["main_scenes"] = []
    result = score_creator(creator)
    assert result["evidence_completeness"] < 0.8
    assert result["total"] <= EVIDENCE_CAP_SCORE


def test_evidence_completeness_full() -> None:
    ratio, missing = evidence_completeness(_base_creator())
    assert ratio == 1.0
    assert missing == []


# ---- 孕晚期/特殊人设 ----

def test_pregnancy_caps_audience_dimension() -> None:
    normal, _ = score_target_audience(_base_creator())
    pregnant, reason = score_target_audience(_base_creator(bio="孕晚期独居记录日常"))
    assert pregnant <= 8
    assert pregnant < normal
    assert "孕" in reason


# ---- 总分与可复现 ----

def test_score_creator_total_consistency() -> None:
    creator = _base_creator()
    result = score_creator(creator)
    dim_sum = sum(d["score"] for d in result["dimensions"].values())
    assert result["raw_total"] == dim_sum
    expected = max(0, min(100, dim_sum - result["body_anxiety_penalty"]))
    assert result["total"] == expected


def test_score_creator_deterministic() -> None:
    creator = _base_creator()
    assert score_creator(creator) == score_creator(creator)


def test_score_creator_total_never_exceeds_bounds() -> None:
    for creator in (_base_creator(), _base_creator(bio="减脂 166/51")):
        result = score_creator(creator)
        assert 0 <= result["total"] <= TOTAL_MAX


# ---- 真实产物回归（离线读取 JSON）----

def test_archived_scores_reproducible_from_deep_review() -> None:
    deep = json.loads(
        (ROOT / "data/processed/stage_3_deep_review_15.json").read_text(encoding="utf-8")
    )
    scores = json.loads(
        (ROOT / "data/processed/stage_3_scores.json").read_text(encoding="utf-8")
    )
    saved = {x["creator_id"]: x["total"] for x in scores["scores"]}
    for creator in deep["creators"]:
        assert score_creator(creator)["total"] == saved[creator["creator_id"]]


def test_archived_finalists_all_meet_formal_line() -> None:
    final = json.loads(
        (ROOT / "data/processed/stage_3_final_10.json").read_text(encoding="utf-8")
    )
    scores = json.loads(
        (ROOT / "data/processed/stage_3_scores.json").read_text(encoding="utf-8")
    )
    saved = {x["creator_id"]: x["total"] for x in scores["scores"]}
    for creator in final["finalists"]:
        assert saved[creator["creator_id"]] >= MIN_FORMAL_SCORE
