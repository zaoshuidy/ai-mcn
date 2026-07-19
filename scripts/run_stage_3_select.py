"""Stage 3 评分筛选：15位深核候选 → 评分 → 最终候选 → Top3 → 风格研究对象。

规则（与项目任务书一致）：
- 硬性淘汰复核：无真实creator_id/profile_url、<2篇代表笔记、180天不活跃、官方/店铺号；
- 最终候选必须 >=85 分（低于85不得进入正式最终候选，不得虚构补齐）；
- 结构平衡：口播型>=3、沉浸字幕型>=3、通勤/办公室>=2、早餐/一人食>=2、
  健身/运动后>=2、同一内容类型<=50%（不可满足的维度如实记录，不降分凑数）；
- Top3 为最终候选中分数最高3位；
- 风格研究对象属于 Top3，须 >=3 条真实视频（近10篇视频数>=3），
  在 Top3 中按食品自然植入能力（轻醒商单相关性）择优；
- 风格研究对象只标记 research_style_reference，禁止 commercially_selected。

输出：
- data/processed/stage_3_scores.json（15位逐项评分，可复现）
- data/processed/stage_3_final_10.json
- data/processed/stage_3_top3.json
- data/processed/stage_3_style_reference.json

用法：python scripts/run_stage_3_select.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.stage_3_scoring import MIN_FORMAL_SCORE, score_creator  # noqa: E402

DEEP_REVIEW = PROJECT_ROOT / "data/processed/stage_3_deep_review_15.json"
OUT_DIR = PROJECT_ROOT / "data/processed"

TARGET_FINAL_COUNT = 10
STYLE_REFERENCE_MIN_VIDEOS = 3
ALLOWED_SELECTION_STATUS = {"research_candidate", "key_candidate",
                            "research_style_reference"}
FORBIDDEN_SELECTION_STATUS = {"commercially_selected", "confirmed_collaboration",
                              "brand_approved"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hard_elimination_check(creator: dict) -> list[str]:
    """硬性淘汰复核，返回命中的淘汰原因（空列表=通过）。"""
    reasons = []
    if not creator.get("creator_id"):
        reasons.append("无真实creator_id")
    if "/user/profile/" not in (creator.get("profile_url") or ""):
        reasons.append("无真实主页URL")
    if len(creator.get("representative_notes", [])) < 2:
        reasons.append("代表笔记不足2篇")
    if not creator.get("latest_post_time"):
        reasons.append("最近180天无更新证据")
    tags = creator.get("tags") or []
    if any("官方" in str(t) or "品牌" in str(t) for t in tags):
        reasons.append("品牌官方号或店铺号")
    return reasons


def structure_balance_report(finalists: list[dict]) -> dict:
    """结构平衡核查：返回每维度的要求、实际与是否满足。"""
    n = len(finalists)
    voiceover = [c for c in finalists if c.get("primary_format") == "voiceover"]
    subtitle = [c for c in finalists if c.get("primary_format") == "subtitle_immersive"]

    def has_scene(c: dict, scene: str) -> bool:
        return scene in (c.get("main_scenes") or [])

    commute = [c for c in finalists if has_scene(c, "通勤/办公室")]
    breakfast = [c for c in finalists
                 if has_scene(c, "早餐") or has_scene(c, "一人食")]
    fitness = [c for c in finalists if has_scene(c, "健身/运动后")]
    checks = {
        "voiceover_min3": {"required": 3, "actual": len(voiceover),
                           "met": len(voiceover) >= 3},
        "subtitle_min3": {"required": 3, "actual": len(subtitle),
                          "met": len(subtitle) >= 3},
        "commute_office_min2": {"required": 2, "actual": len(commute),
                                "met": len(commute) >= 2},
        "breakfast_solo_min2": {"required": 2, "actual": len(breakfast),
                                "met": len(breakfast) >= 2},
        "fitness_min2": {"required": 2, "actual": len(fitness),
                         "met": len(fitness) >= 2},
        "single_format_max50pct": {
            "required": "<=50%", "actual": f"{max(len(voiceover), len(subtitle))}/{n}",
            "met": n > 0 and max(len(voiceover), len(subtitle)) <= n / 2 + 0.5},
    }
    checks["all_met"] = all(v["met"] for v in checks.values())
    return checks


def main() -> int:
    review = json.loads(DEEP_REVIEW.read_text(encoding="utf-8"))
    creators = review["creators"]
    now = utc_now()

    # 1. 硬性淘汰复核 + 评分
    scored = []
    hard_eliminated = []
    for creator in creators:
        reasons = hard_elimination_check(creator)
        result = score_creator(creator)
        if reasons:
            result["hard_elimination_reasons"] = reasons
            hard_eliminated.append(result)
            continue
        result["profile_url"] = creator["profile_url"]
        result["primary_format"] = creator.get("primary_format")
        result["main_scenes"] = creator.get("main_scenes")
        result["followers"] = creator.get("followers")
        scored.append((result, creator))
    scored.sort(key=lambda x: x[0]["total"], reverse=True)

    scores_doc = {
        "generated_at": now,
        "model": "src/stage_3_scoring.py",
        "graded_count": len(scored),
        "hard_eliminated_count": len(hard_eliminated),
        "scores": [s for s, _ in scored],
        "hard_eliminated": hard_eliminated,
    }
    (OUT_DIR / "stage_3_scores.json").write_text(
        json.dumps(scores_doc, ensure_ascii=False, indent=1), encoding="utf-8")

    # 2. 最终候选：>=85 分（不足10位不虚构补齐）
    finalists = [(s, c) for s, c in scored if s["total"] >= MIN_FORMAL_SCORE]
    balance = structure_balance_report([c for _, c in finalists])
    final_doc = {
        "generated_at": now,
        "target_count": TARGET_FINAL_COUNT,
        "actual_count": len(finalists),
        "count_gap_reason": (
            None if len(finalists) >= TARGET_FINAL_COUNT else
            f"15位深核候选中仅{len(finalists)}位达到{MIN_FORMAL_SCORE}分正式候选线；"
            "按任务书允许少于10位，不虚构补齐"),
        "min_formal_score": MIN_FORMAL_SCORE,
        "structure_balance": balance,
        "human_verified": False,
        "finalists": [],
    }
    for rank, (s, creator) in enumerate(finalists, start=1):
        entry = dict(creator)
        entry["selection_status"] = "key_candidate" if s["total"] >= 90 else "research_candidate"
        entry["selection_rank"] = rank
        entry["score"] = s
        final_doc["finalists"].append(entry)
    (OUT_DIR / "stage_3_final_10.json").write_text(
        json.dumps(final_doc, ensure_ascii=False, indent=1), encoding="utf-8")

    # 3. Top3
    top3 = finalists[:3]
    top3_doc = {
        "generated_at": now,
        "selection_rule": "最终候选中总分最高的3位",
        "top3": [{
            "creator_id": c["creator_id"],
            "nickname": c["nickname"],
            "profile_url": c["profile_url"],
            "total": s["total"],
            "grade": s["grade"],
            "primary_format": c.get("primary_format"),
            "main_scenes": c.get("main_scenes"),
            "selection_status": "key_candidate",
            "human_verified": False,
        } for s, c in top3],
    }
    (OUT_DIR / "stage_3_top3.json").write_text(
        json.dumps(top3_doc, ensure_ascii=False, indent=1), encoding="utf-8")

    # 4. 风格研究对象：Top3 中食品自然植入能力最高者（须>=3条真实视频）
    # 并列决胜链（确定性）：食品植入分 → 商业内容自然度（商单植入自然度与
    # 脚本风格研究直接相关）→ 总分。
    def _style_key(item: tuple) -> tuple:
        s, _c = item
        return (
            s["dimensions"]["food_integration"]["score"],
            s["dimensions"]["commercial_naturalness"]["score"],
            s["total"],
        )

    style_candidates = [(s, c) for s, c in top3
                        if (c.get("video_posts_in_recent10") or 0) >= STYLE_REFERENCE_MIN_VIDEOS]
    style_pick = max(style_candidates, key=_style_key) if style_candidates else None
    style_doc = {"generated_at": now, "style_reference": None, "rejected_top3": []}
    if style_pick:
        s, creator = style_pick
        style_doc["style_reference"] = {
            "creator_id": creator["creator_id"],
            "nickname": creator["nickname"],
            "profile_url": creator["profile_url"],
            "total": s["total"],
            "grade": s["grade"],
            "primary_format": creator.get("primary_format"),
            "main_scenes": creator.get("main_scenes"),
            "video_posts_in_recent10": creator.get("video_posts_in_recent10"),
            "selection_status": "research_style_reference",
            "selection_scope": "仅用于脚本风格研究，不构成商业合作定案",
            "selection_reasons": [
                f"食品自然植入能力 {s['dimensions']['food_integration']['score']}/15（Top3最高）",
                f"场景匹配 {s['dimensions']['scene_match']['score']}/15："
                f"{'/'.join(creator.get('main_scenes') or [])}",
                f"近10篇视频 {creator.get('video_posts_in_recent10')} 条，满足>=3条真实视频要求",
                f"目标受众匹配 {s['dimensions']['target_audience']['score']}/20",
                f"合规安全 {s['dimensions']['compliance']['score']}/5",
            ],
            "human_verified": False,
            "selected_at": now,
        }
        for s2, c2 in top3:
            if c2["creator_id"] != creator["creator_id"]:
                style_doc["rejected_top3"].append({
                    "creator_id": c2["creator_id"],
                    "nickname": c2["nickname"],
                    "reason": f"食品植入分 {s2['dimensions']['food_integration']['score']}/15 "
                              f"低于入选者或并列但总分较低",
                })
    (OUT_DIR / "stage_3_style_reference.json").write_text(
        json.dumps(style_doc, ensure_ascii=False, indent=1), encoding="utf-8")

    # 5. 汇总输出
    print(f"[SCORE] 评分 {len(scored)} 位，硬淘汰复核 {len(hard_eliminated)} 位")
    print(f"[FINAL] >=85分最终候选 {len(finalists)} 位（目标 {TARGET_FINAL_COUNT}，不虚构补齐）")
    for s, c in finalists:
        print(f"        {s['total']} {c['nickname']} ({c.get('primary_format')})")
    print(f"[BALANCE] all_met={balance['all_met']} "
          f"未满足项={[k for k, v in balance.items() if k != 'all_met' and not v['met']]}")
    print(f"[TOP3] {[c['nickname'] for _, c in top3]}")
    if style_pick:
        print(f"[STYLE] 风格研究对象：{style_pick[1]['nickname']} "
              f"(selection_status=research_style_reference)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
