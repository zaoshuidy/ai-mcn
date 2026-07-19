"""Stage 3 v2 重评分：10 维模型（含粉丝量级与互动质量）。

输入：
- data/processed/stage_3_deep_review_15.json（15 位深核）
- data/processed/stage_3_engagement_15.json（15 位最近 10 篇互动）

输出：
- data/processed/stage_3_scores_v2.json（15 位逐项评分，可复现）
- data/processed/stage_3_final_candidates_v2.json（v2 候选，含结构平衡）
- data/processed/stage_3_scores.json 不动（v1 存档，已 superseded）
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.stage_3_scoring_v2 import (  # noqa: E402
    KEY_CANDIDATE_SCORE,
    MIN_FORMAL_SCORE_V2,
    UNDER_1K_SELECTION_TIER,
    score_creator_v2,
)

DEEP = ROOT / "data/processed/stage_3_deep_review_15.json"
ENG = ROOT / "data/processed/stage_3_engagement_15.json"
OUT_SCORES = ROOT / "data/processed/stage_3_scores_v2.json"
OUT_FINAL = ROOT / "data/processed/stage_3_final_candidates_v2.json"
V1_FINAL = ROOT / "data/processed/stage_3_final_10.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def structure_balance(finalists: list[dict]) -> dict:
    voiceover = sum(1 for c in finalists if c.get("primary_format") == "voiceover")
    subtitle = sum(1 for c in finalists if c.get("primary_format") == "subtitle_immersive")
    commute = sum(1 for c in finalists if "通勤/办公室" in (c.get("main_scenes") or []))
    breakfast = sum(
        1 for c in finalists if {"早餐", "一人食"} & set(c.get("main_scenes") or []))
    fitness = sum(1 for c in finalists if "健身/运动后" in (c.get("main_scenes") or []))
    n = len(finalists)
    return {
        "voiceover_min3": {"required": 3, "actual": voiceover, "met": voiceover >= 3},
        "subtitle_min3": {"required": 3, "actual": subtitle, "met": subtitle >= 3},
        "commute_office_min2": {"required": 2, "actual": commute, "met": commute >= 2},
        "breakfast_solo_min2": {"required": 2, "actual": breakfast, "met": breakfast >= 2},
        "fitness_min2": {"required": 2, "actual": fitness, "met": fitness >= 2},
        "single_format_max50pct": {
            "required": "<=50%",
            "actual": f"{max(voiceover, subtitle)}/{n}" if n else "0/0",
            "met": bool(n) and max(voiceover, subtitle) <= n / 2,
        },
    }


def main() -> int:
    deep = json.loads(DEEP.read_text(encoding="utf-8"))["creators"]
    eng = {e["creator_id"]: e
           for e in json.loads(ENG.read_text(encoding="utf-8"))["creators"]}
    v1_lookup = {}
    if V1_FINAL.is_file():
        for c in json.loads(V1_FINAL.read_text(encoding="utf-8"))["finalists"]:
            v1_lookup[c["creator_id"]] = c

    scores = []
    for creator in deep:
        result = score_creator_v2(creator, eng.get(creator["creator_id"]))
        result["profile_url"] = creator["profile_url"]
        result["primary_format"] = creator.get("primary_format")
        result["main_scenes"] = creator.get("main_scenes") or []
        scores.append(result)
    scores.sort(key=lambda s: (-s["total"], s["creator_id"]))

    OUT_SCORES.write_text(json.dumps({
        "generated_at": utc_now(),
        "model": "v2_10dim",
        "supersedes": "data/processed/stage_3_scores.json",
        "dimension_weights": {
            "target_audience": 18, "content_track": 13, "scene_match": 12,
            "video_expression": 10, "food_integration": 13,
            "commercial_naturalness": 8, "executability": 8,
            "follower_scale_fit": 7, "engagement_quality": 6, "compliance": 5,
        },
        "graded_count": len(scores),
        "scores": scores,
    }, ensure_ascii=False, indent=2), "utf-8")

    # v2 候选：>=85 且非 under_1k 硬限（under_1k 已被模型降级/封顶）
    finalists = []
    for s in scores:
        if s["total"] < MIN_FORMAL_SCORE_V2:
            continue
        entry = {
            "creator_id": s["creator_id"],
            "nickname": s["nickname"],
            "profile_url": s["profile_url"],
            "followers": s["followers"],
            "creator_tier": s["creator_tier"],
            "selection_tier": s["selection_tier"],
            "total_score": s["total"],
            "grade": s["grade"],
            "primary_format": s["primary_format"],
            "main_scenes": s["main_scenes"],
            "engagement_stats": s["engagement_stats"],
            "commercial_breakdown": s["commercial_breakdown"],
            "selection_status": (
                "key_candidate" if s["total"] >= KEY_CANDIDATE_SCORE
                and s["selection_tier"] != UNDER_1K_SELECTION_TIER
                else "research_candidate"),
            "representative_notes": v1_lookup.get(s["creator_id"], {}).get(
                "representative_notes", []),
            "human_verified": False,
            "scoring_model": "v2_10dim",
        }
        finalists.append(entry)

    balance = structure_balance(finalists)
    balance["all_met"] = all(
        v["met"] for k, v in balance.items() if isinstance(v, dict) and "met" in v)

    OUT_FINAL.write_text(json.dumps({
        "generated_at": utc_now(),
        "scoring_model": "v2_10dim",
        "supersedes": "data/processed/stage_3_final_10.json",
        "target_count": 10,
        "actual_count": len(finalists),
        "min_formal_score": MIN_FORMAL_SCORE_V2,
        "structure_balance": balance,
        "human_verified": False,
        "finalists": finalists,
    }, ensure_ascii=False, indent=2), "utf-8")

    print(f"v2 评分完成：{len(scores)} 位；候选（>=85）：{len(finalists)} 位")
    for s in scores:
        print(f"  {s['nickname']:<10} total={s['total']:>3} tier={s['creator_tier']:<13} "
              f"grade={s['grade']} med_eng={s['engagement_stats'].get('median_total_engagement')}")
    print(f"结构平衡 all_met={balance['all_met']}: "
          f"口播{balance['voiceover_min3']['actual']} 字幕{balance['subtitle_min3']['actual']} "
          f"通勤{balance['commute_office_min2']['actual']} "
          f"早餐{balance['breakfast_solo_min2']['actual']} "
          f"健身{balance['fitness_min2']['actual']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
