"""Stage 3 v2 评分模型（src/stage_3_scoring_v2.py）单元与回归测试。

合成输入为主：10 维权重、粉丝分层、互动统计、商业内容来源分离、
under_1k 封顶/降级/禁 Top3 逻辑等；
真实产物回归为辅：对 data/processed 的 deep_review + engagement 重算，
与 stage_3_scores_v2.json 存档比对（可复现性）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.stage_3_scoring_v2 import (
    DIMENSION_MAX_V2,
    FOLLOWER_SCALE_FIT_CAP,
    KEY_CANDIDATE_SCORE,
    TIER_UNDER_1K,
    TIER_UNKNOWN,
    TOP3_MIN_FOLLOWERS,
    TOTAL_MAX_V2,
    UNDER_1K_SELECTION_TIER,
    UNDER_1K_TOTAL_CAP,
    commercial_breakdown,
    creator_tier,
    engagement_stats,
    grade_of_v2,
    parse_followers,
    score_creator_v2,
    score_engagement_quality,
    score_follower_scale_fit,
)

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
SCORES_V2 = PROC / "stage_3_scores_v2.json"
FINAL_V2 = PROC / "stage_3_final_candidates_v2.json"
DEEP_15 = PROC / "stage_3_deep_review_15.json"
ENG_15 = PROC / "stage_3_engagement_15.json"


# ---------- 合成输入构造 ----------

def make_note(i: int, likes=100, collects=50, comments=10, commercial=False,
              ai_signal=False) -> dict:
    return {
        "note_id": f"n{i:02d}",
        "title": f"早餐酸奶碗vlog{i}",
        "publish_time": "2026-06-01",
        "note_type": "video",
        "duration_seconds": 60,
        "likes": likes,
        "collects": collects,
        "comments": comments,
        "is_platform_labeled_commercial": commercial,
        "ai_inferred_commercial_signal": ["软广信号"] if ai_signal else [],
        "has_voiceover": True,
        "has_on_screen_text": True,
    }


def make_creator(**overrides) -> dict:
    creator = {
        "creator_id": "abc123def456",
        "nickname": "测试达人",
        "bio": "独居打工人下班后的生活vlog记录",
        "followers": "5.6万",
        "latest_post_time": "2026-07-01",
        "posts_reviewed_count": 10,
        "video_posts_in_recent10": 10,
        "primary_format": "voiceover",
        "main_scenes": ["早餐", "一人食", "酸奶/轻食", "下午茶"],
        "content_categories": ["早餐", "一人食", "酸奶/轻食"],
        "recent_titles_sample": ["早餐吃什么", "一人食brunch", "下午茶酸奶咖啡"],
        "representative_notes": [make_note(i) for i in range(3)],
    }
    creator.update(overrides)
    return creator


def make_engagement(n: int = 10, likes: int = 1000, collects: int = 200,
                    comments: int = 50) -> dict:
    return {
        "creator_id": "abc123def456",
        "notes": [make_note(i, likes=likes + i, collects=collects,
                            comments=comments) for i in range(n)],
    }


# ---------- 权重与常量 ----------

def test_dimension_weights_sum_to_100():
    assert len(DIMENSION_MAX_V2) == 10
    assert TOTAL_MAX_V2 == 100
    assert sum(DIMENSION_MAX_V2.values()) == 100


def test_dimension_weights_include_new_v2_dimensions():
    assert "follower_scale_fit" in DIMENSION_MAX_V2
    assert "engagement_quality" in DIMENSION_MAX_V2
    assert DIMENSION_MAX_V2["follower_scale_fit"] == 7
    assert DIMENSION_MAX_V2["engagement_quality"] == 6


def test_follower_scale_fit_cap_is_5():
    assert FOLLOWER_SCALE_FIT_CAP == 5


# ---------- parse_followers / creator_tier ----------

def test_parse_followers_wan_suffix():
    assert parse_followers("5.6万") == 56000
    assert parse_followers("1.2w") == 12000


def test_parse_followers_plain_and_invalid():
    assert parse_followers("56000") == 56000
    assert parse_followers(139) == 139
    assert parse_followers(None) is None
    assert parse_followers("") is None
    assert parse_followers("未知") == 0


def test_creator_tier_boundaries():
    assert creator_tier(None) == TIER_UNKNOWN
    assert creator_tier(999) == "under_1k"
    assert creator_tier(1000) == "1k_to_10k"
    assert creator_tier(9999) == "1k_to_10k"
    assert creator_tier(10000) == "10k_to_100k"
    assert creator_tier(99999) == "10k_to_100k"
    assert creator_tier(100000) == "100k_to_500k"
    assert creator_tier(499999) == "100k_to_500k"
    assert creator_tier(500000) == "over_500k"


# ---------- engagement_stats ----------

def test_engagement_stats_medians():
    notes = [make_note(i, likes=100 + i * 10, collects=10, comments=5)
             for i in range(10)]
    stats = engagement_stats(notes, followers=10000)
    totals = sorted((100 + i * 10) + 10 + 5 for i in range(10))
    expected_median = (totals[4] + totals[5]) / 2
    assert stats["median_total_engagement"] == expected_median
    assert stats["highest_post_engagement"] == totals[-1]
    assert stats["lowest_post_engagement"] == totals[0]
    assert stats["notes_with_engagement"] == 10
    assert stats["median_likes"] == (100 + 40 + 100 + 50) / 2


def test_engagement_stats_skips_notes_without_likes():
    notes = [make_note(0), {**make_note(1), "likes": None}]
    stats = engagement_stats(notes, followers=1000)
    assert stats["notes_with_engagement"] == 1
    assert stats["median_total_engagement"] == 160


def test_engagement_rate_null_when_followers_none():
    stats = engagement_stats([make_note(0)], followers=None)
    assert stats["median_total_engagement"] == 160
    assert stats["median_engagement_rate"] is None


def test_engagement_rate_null_when_followers_zero():
    stats = engagement_stats([make_note(0)], followers=0)
    assert stats["median_engagement_rate"] is None


def test_engagement_rate_computed_when_followers_present():
    stats = engagement_stats([make_note(0)], followers=1000)
    assert stats["median_engagement_rate"] == pytest.approx(160 / 1000, abs=1e-6)


def test_engagement_stats_empty_notes_all_null():
    stats = engagement_stats([], followers=1000)
    assert stats["median_total_engagement"] is None
    assert stats["median_engagement_rate"] is None
    assert stats["viral_dependency_ratio"] is None
    assert stats["highest_post_engagement"] is None


def test_viral_dependency_ratio_computed():
    notes = [make_note(i, likes=100, collects=0, comments=0) for i in range(9)]
    notes.append(make_note(9, likes=910, collects=0, comments=0))
    stats = engagement_stats(notes, followers=10000)
    # 10 篇中位数 = 100，最高 = 910
    assert stats["median_total_engagement"] == 100
    assert stats["viral_dependency_ratio"] == pytest.approx(9.1, abs=1e-3)


def test_viral_dependency_null_when_median_zero():
    notes = [make_note(i, likes=0, collects=0, comments=0) for i in range(10)]
    stats = engagement_stats(notes, followers=1000)
    assert stats["median_total_engagement"] == 0
    assert stats["viral_dependency_ratio"] is None


def test_engagement_stats_organic_commercial_split():
    notes = [make_note(i, likes=100) for i in range(8)]
    notes.append(make_note(8, likes=500, commercial=True))
    notes.append(make_note(9, likes=300, ai_signal=True))
    stats = engagement_stats(notes, followers=10000)
    assert stats["organic_post_median_engagement"] is not None
    assert stats["commercial_post_median_engagement"] is not None


# ---------- commercial_breakdown ----------

def test_commercial_breakdown_separation():
    notes = [make_note(i) for i in range(7)]
    notes.append(make_note(7, commercial=True))
    notes.append(make_note(8, ai_signal=True))
    notes.append(make_note(9, commercial=True, ai_signal=True))
    bd = commercial_breakdown(notes)
    # 平台标识 2 条；AI 软广仅统计未被平台标识的 1 条，不得重复计数
    assert bd["platform_labeled_commercial_posts"] == 2
    assert bd["ai_inferred_commercial_posts"] == 1
    assert bd["total_commercial_signals"] == 3
    assert bd["commercial_signal_ratio"] == pytest.approx(0.3, abs=1e-3)


def test_commercial_breakdown_source_fields():
    bd = commercial_breakdown([make_note(0)])
    assert bd["platform_labeled_source"] == "page_observed"
    assert bd["ai_inferred_source"] == "ai_inferred"
    assert "platform_labeled_commercial_posts" in bd
    assert "ai_inferred_commercial_posts" in bd


def test_commercial_breakdown_empty_notes():
    bd = commercial_breakdown([])
    assert bd["total_commercial_signals"] == 0
    assert bd["commercial_signal_ratio"] is None


# ---------- engagement_quality 维度 ----------

def test_engagement_quality_no_data():
    score, reason = score_engagement_quality({}, followers=1000)
    assert score == 0
    assert "无互动数据" in reason


def test_engagement_quality_high_median_stable():
    stats = {"median_total_engagement": 1500, "median_engagement_rate": 0.03,
             "viral_dependency_ratio": 2.0}
    score, reason = score_engagement_quality(stats, followers=50000)
    assert score == 6  # 3（中位>=1000）+ 2（率>=2%）+ 1（爆款依赖<=5）
    assert "互动稳定" in reason


def test_engagement_quality_rate_missing_reason():
    stats = {"median_total_engagement": 400, "median_engagement_rate": None,
             "viral_dependency_ratio": None}
    score, reason = score_engagement_quality(stats, followers=None)
    assert score == 2  # 仅中位 300-1000 档
    assert "粉丝数缺失" in reason


def test_engagement_quality_viral_risk_no_bonus():
    stats = {"median_total_engagement": 1500, "median_engagement_rate": 0.03,
             "viral_dependency_ratio": 9.0}
    score, reason = score_engagement_quality(stats, followers=50000)
    assert score == 5  # 爆款依赖>5 不加稳定性分
    assert "爆款驱动风险" in reason


def test_engagement_quality_capped_at_6():
    stats = {"median_total_engagement": 99999, "median_engagement_rate": 0.5,
             "viral_dependency_ratio": 1.0}
    score, _ = score_engagement_quality(stats, followers=1000)
    assert score == 6


# ---------- follower_scale_fit 维度 ----------

def test_follower_scale_fit_never_exceeds_cap():
    for followers in ("500", "5000", "5万", "20万", "80万"):
        score, _, _ = score_follower_scale_fit({"followers": followers})
        assert score <= FOLLOWER_SCALE_FIT_CAP


def test_follower_scale_fit_unknown_followers():
    score, tier, reason = score_follower_scale_fit({"followers": None})
    assert score == 2
    assert tier == TIER_UNKNOWN
    assert "无法确认" in reason


def test_follower_scale_fit_under_1k_low_score():
    score, tier, _ = score_follower_scale_fit({"followers": "500"})
    assert tier == TIER_UNDER_1K
    assert score == 2


# ---------- under_1k 封顶 / 降级 / 禁 Top3 ----------

def test_under_1k_total_capped_at_84():
    creator = make_creator(followers="500")
    result = score_creator_v2(creator, make_engagement(likes=5000))
    assert result["creator_tier"] == TIER_UNDER_1K
    assert result["raw_total"] > UNDER_1K_TOTAL_CAP  # 未封顶前确实超过 84
    assert result["total"] == UNDER_1K_TOTAL_CAP
    assert any("封顶" in c for c in result["caps_applied"])


def test_under_1k_selection_tier_is_koc_seed_candidate():
    creator = make_creator(followers="500")
    result = score_creator_v2(creator, make_engagement())
    assert result["selection_tier"] == UNDER_1K_SELECTION_TIER


def test_under_1k_grade_never_formal():
    creator = make_creator(followers="500")
    result = score_creator_v2(creator, make_engagement(likes=5000))
    assert result["grade"] not in ("重点候选", "正式研究候选")


def test_under_1k_excluded_by_top3_gate():
    creator = make_creator(followers="500")
    result = score_creator_v2(creator, make_engagement(likes=5000))
    followers = result["followers"]
    total = result["total"]
    top3_eligible = followers >= TOP3_MIN_FOLLOWERS and total >= KEY_CANDIDATE_SCORE
    assert not top3_eligible


def test_non_under_1k_high_scorer_keeps_formal_grade():
    creator = make_creator(followers="5.6万")
    result = score_creator_v2(creator, make_engagement(likes=5000))
    assert result["creator_tier"] != TIER_UNDER_1K
    assert result["selection_tier"] is None
    assert result["total"] >= 90
    assert result["grade"] == "重点候选"


def test_grade_of_v2_boundaries():
    assert grade_of_v2(90) == "重点候选"
    assert grade_of_v2(85) == "正式研究候选"
    assert grade_of_v2(80) == "仅风格参考"
    assert grade_of_v2(79) == "淘汰"


# ---------- 整体评分结构 ----------

def test_score_creator_v2_has_exactly_10_dimensions():
    result = score_creator_v2(make_creator(), make_engagement())
    assert set(result["dimensions"]) == set(DIMENSION_MAX_V2)
    for name, dim in result["dimensions"].items():
        assert dim["max"] == DIMENSION_MAX_V2[name]
        assert 0 <= dim["score"] <= dim["max"]


def test_score_creator_v2_total_never_exceeds_100():
    result = score_creator_v2(make_creator(), make_engagement(likes=9000))
    assert 0 <= result["total"] <= TOTAL_MAX_V2


def test_score_creator_v2_without_engagement_record():
    result = score_creator_v2(make_creator(), None)
    assert result["dimensions"]["engagement_quality"]["score"] == 0
    assert result["commercial_breakdown"]["total_commercial_signals"] == 0


def test_body_anxiety_penalty_applied():
    creator = make_creator(bio="减肥打卡 170/50kg 维持体重")
    result = score_creator_v2(creator, make_engagement())
    assert result["body_anxiety_penalty"] >= 5
    assert result["total"] == result["raw_total"] - result["body_anxiety_penalty"]


# ---------- 真实产物回归（可复现性） ----------

@pytest.fixture(scope="module")
def real_artifacts():
    for p in (SCORES_V2, FINAL_V2, DEEP_15, ENG_15):
        if not p.is_file():
            pytest.skip(f"真实产物缺失：{p.name}")
    scores_v2 = json.loads(SCORES_V2.read_text(encoding="utf-8"))
    final_v2 = json.loads(FINAL_V2.read_text(encoding="utf-8"))
    deep = json.loads(DEEP_15.read_text(encoding="utf-8"))["creators"]
    eng = {e["creator_id"]: e
           for e in json.loads(ENG_15.read_text(encoding="utf-8"))["creators"]}
    return scores_v2, final_v2, deep, eng


def test_real_scores_v2_dimension_weights(real_artifacts):
    scores_v2, _, _, _ = real_artifacts
    assert scores_v2["dimension_weights"] == DIMENSION_MAX_V2
    for s in scores_v2["scores"]:
        assert set(s["dimensions"]) == set(DIMENSION_MAX_V2)
        for name, dim in s["dimensions"].items():
            assert dim["max"] == DIMENSION_MAX_V2[name]


def test_real_scores_v2_fully_reproducible(real_artifacts):
    scores_v2, _, deep, eng = real_artifacts
    deep_by_id = {c["creator_id"]: c for c in deep}
    # 深核名单可能被总控继续扩充；此处校验存档每位均可复现，
    # 不要求存档人数与深核当前人数相等
    for s in scores_v2["scores"]:
        creator = deep_by_id.get(s["creator_id"])
        assert creator is not None, f"{s['nickname']} 深核记录缺失"
        r = score_creator_v2(creator, eng.get(s["creator_id"]))
        assert r["total"] == s["total"], s["nickname"]
        assert r["grade"] == s["grade"], s["nickname"]
        for name in DIMENSION_MAX_V2:
            assert r["dimensions"][name]["score"] == s["dimensions"][name]["score"], (
                f"{s['nickname']}.{name}")


def test_real_engagement_stats_reproducible(real_artifacts):
    scores_v2, _, _, eng = real_artifacts
    for s in scores_v2["scores"]:
        recomputed = engagement_stats(
            eng[s["creator_id"]]["notes"], s["followers"])
        saved = s["engagement_stats"]
        for key in ("median_total_engagement", "median_engagement_rate",
                    "viral_dependency_ratio"):
            if saved[key] is None:
                assert recomputed[key] is None, f"{s['nickname']}.{key}"
            else:
                assert recomputed[key] == pytest.approx(saved[key], abs=1e-3), (
                    f"{s['nickname']}.{key}")


def test_real_under_1k_rules(real_artifacts):
    scores_v2, _, _, _ = real_artifacts
    under_1k = [s for s in scores_v2["scores"]
                if s["creator_tier"] == TIER_UNDER_1K]
    assert under_1k, "存档中应至少存在 1 位 under_1k 候选"
    for s in under_1k:
        assert s["total"] <= UNDER_1K_TOTAL_CAP
        assert s["selection_tier"] == UNDER_1K_SELECTION_TIER
        assert s["grade"] not in ("重点候选", "正式研究候选")


def test_real_final_candidates_v2_no_under_1k_key_candidate(real_artifacts):
    _, final_v2, _, _ = real_artifacts
    for f in final_v2["finalists"]:
        if f["selection_status"] == "key_candidate":
            assert f["followers"] >= TOP3_MIN_FOLLOWERS, f["nickname"]


def test_real_final_candidates_v2_supersedes_v1(real_artifacts):
    _, final_v2, _, _ = real_artifacts
    assert final_v2["supersedes"] == "data/processed/stage_3_final_10.json"


def test_real_commercial_breakdown_sources(real_artifacts):
    scores_v2, final_v2, _, _ = real_artifacts
    entries = list(scores_v2["scores"]) + list(final_v2["finalists"])
    for e in entries:
        bd = e["commercial_breakdown"]
        assert "platform_labeled_commercial_posts" in bd
        assert bd["platform_labeled_source"] == "page_observed"
        assert "ai_inferred_commercial_posts" in bd
        assert bd["ai_inferred_source"] == "ai_inferred"


def test_real_top_candidates_meet_v2_expectation(real_artifacts):
    scores_v2, _, _, _ = real_artifacts
    totals = {s["nickname"]: s["total"] for s in scores_v2["scores"]}
    assert totals["欧盈Kelly"] == 93
    assert totals["小季没烦恼"] == 85
    others = [t for n, t in totals.items() if n not in ("欧盈Kelly", "小季没烦恼")]
    assert all(t < 85 for t in others)
