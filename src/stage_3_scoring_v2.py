"""Stage 3 v2 达人评分模型（10 维，含粉丝量级与近期互动质量）。

总分 100，10 个维度：
- 目标受众匹配 target_audience              18
- 内容赛道匹配 content_track                13
- 场景匹配 scene_match                      12
- 视频表达能力 video_expression             10
- 食品自然植入能力 food_integration         13
- 商业内容自然度 commercial_naturalness      8
- 拍摄与脚本可执行性 executability           8
- 粉丝量级适配 follower_scale_fit            7
- 近期互动质量 engagement_quality            6
- 合规安全 compliance                        5

v2 相对 v1 的变化（总控复评要求）：
- 新增粉丝量级适配（7 分）：粉丝不是越多越好；品牌预算未确认，
  该维度上限 5/7；under_1k 账号标记 koc_seed_candidate 且总分封顶 84，
  不得进入 Top3 / 正式重点候选；
- 新增近期互动质量（6 分）：基于最近 10 篇笔记的点赞/收藏/评论中位数、
  池内互动率、爆款依赖度；互动率仅用于本候选池内部比较，
  不得称为平台官方互动率；不得根据点赞反推粉丝数；
- 商业内容统计拆分 platform_labeled（page_observed）与
  ai_inferred（软广判断），不得混为同一证据来源；
- 旧 8 维评分（stage_3_scoring.py）标记 superseded，仅供追溯。

输入：stage_3_deep_review_15.json 达人记录 + stage_3_engagement_15.json
互动数据（通过 creator_id 关联）。
"""

from __future__ import annotations

import re
import statistics
from typing import Any

DIMENSION_MAX_V2 = {
    "target_audience": 18,
    "content_track": 13,
    "scene_match": 12,
    "video_expression": 10,
    "food_integration": 13,
    "commercial_naturalness": 8,
    "executability": 8,
    "follower_scale_fit": 7,
    "engagement_quality": 6,
    "compliance": 5,
}
TOTAL_MAX_V2 = sum(DIMENSION_MAX_V2.values())  # 100

# 粉丝量级
TIER_UNDER_1K = "under_1k"
TIER_1K_10K = "1k_to_10k"
TIER_10K_100K = "10k_to_100k"
TIER_100K_500K = "100k_to_500k"
TIER_OVER_500K = "over_500k"
TIER_UNKNOWN = "unknown"

FOLLOWER_SCALE_FIT_CAP = 5          # 预算未确认，量级分上限 5/7
UNDER_1K_TOTAL_CAP = 84             # under_1k 总分上限
UNDER_1K_SELECTION_TIER = "koc_seed_candidate"
TOP3_MIN_FOLLOWERS = 1000           # Top3 粉丝下限
MIN_FORMAL_SCORE_V2 = 85
KEY_CANDIDATE_SCORE = 90

# 组合目标（任务书第八节，软目标，不为凑比例纳入低质量账号）
MIX_TARGET = {
    "1k_to_10k": 3,
    "10k_to_100k": 4,
    "100k_to_500k": (1, 2),
    "under_1k_max": 2,
    "voiceover_min": 3,
    "subtitle_min": 3,
    "commute_office_min": 2,
    "breakfast_solo_min": 2,
    "fitness_min": 2,
}

URBAN_JOB_RE = re.compile(
    r"打工人|上班|通勤|电商|互联网|搬砖|职场|下班|私企|HR|hr|杭漂|深漂|北漂|沪漂")
SOLO_LIVING_RE = re.compile(r"独居|一人食|独处|独自|一个人")
LIFESTYLE_VLOG_RE = re.compile(r"vlog|Vlog|VLOG|日常|生活|记录|日记")
PREGNANCY_RE = re.compile(r"孕|产妇|哺乳期")
FOOD_SCENE_SET = {"早餐", "一人食", "酸奶/轻食"}
SCENE_WEIGHT = {"早餐": 5, "一人食": 5, "酸奶/轻食": 5, "下午茶": 4,
                "通勤/办公室": 3, "健身/运动后": 3}
FOOD_TITLE_RE = re.compile(
    r"吃|餐|食|厨|烹饪|三明治|沙拉|酸奶|咖啡|茶|水果|烘焙|做饭|零食|brunch|Brunch")
DRINK_RE = re.compile(r"咖啡|茶|酸奶|奶昔|饮品|果汁|霸王茶姬|CHAGEE")
BODY_ANXIETY_RE = re.compile(
    r"减肥|减脂|瘦脸|掉秤|暴瘦|燃脂|长胎不长肉|维持体重|瘦身|瘦腿|瘦肚子")
BODY_METRICS_RE = re.compile(r"\d{3}\s*/\s*\d{2,3}\s*(kg|KG|斤)?")
COMMERCIAL_BONUS_RULES = [
    ("霸王茶姬", 3, "饮品商单融入晚间生活场景，植入自然"),
    ("AI搜索", 2, "App推广植入翻包场景，自然度中等"),
    ("雅顿", 2, "护肤品商单常规口播植入，自然度中等"),
    ("自动泊车", 1, "汽车商单卖点口播，硬广感较强"),
]
TITLE_SCENE_CATEGORIES = {
    "早餐类": re.compile(r"早餐|brunch|Brunch|早午餐|晨间"),
    "一人食/做饭类": re.compile(r"一人食|做饭|厨房|下厨|两餐|三餐"),
    "下午茶/饮品类": re.compile(r"下午茶|喝茶|咖啡|酸奶碗|奶昔"),
}


def parse_followers(value) -> int | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    try:
        if text.endswith(("万", "w")):
            return round(float(text[:-1]) * 10000)
        return int("".join(ch for ch in text if ch.isdigit()) or 0)
    except (ValueError, TypeError):
        return None


def creator_tier(followers: int | None) -> str:
    if followers is None:
        return TIER_UNKNOWN
    if followers < 1_000:
        return TIER_UNDER_1K
    if followers < 10_000:
        return TIER_1K_10K
    if followers < 100_000:
        return TIER_10K_100K
    if followers < 500_000:
        return TIER_100K_500K
    return TIER_OVER_500K


# ---------- 互动统计（纯函数，可复现） ----------

def engagement_stats(notes: list[dict], followers: int | None) -> dict[str, Any]:
    """由最近 N 篇笔记的 page_observed 互动数计算统计指标。"""
    valid = [
        n for n in notes
        if n.get("likes") is not None
    ]
    totals = []
    for n in valid:
        total = (n.get("likes") or 0) + (n.get("collects") or 0) + (n.get("comments") or 0)
        totals.append(total)

    def _median(values: list[int], key: str) -> float | None:
        vals = [n.get(key) for n in valid if n.get(key) is not None]
        return statistics.median(vals) if vals else None

    stats: dict[str, Any] = {
        "notes_with_engagement": len(valid),
        "median_likes": _median(valid, "likes"),
        "median_collects": _median(valid, "collects"),
        "median_comments": _median(valid, "comments"),
        "median_total_engagement": statistics.median(totals) if totals else None,
        "highest_post_engagement": max(totals) if totals else None,
        "lowest_post_engagement": min(totals) if totals else None,
    }
    med_total = stats["median_total_engagement"]
    if followers and med_total is not None:
        # 仅用于本候选池内部比较，非平台官方互动率
        stats["median_engagement_rate"] = round(med_total / followers, 6)
    else:
        stats["median_engagement_rate"] = None
    highest = stats["highest_post_engagement"]
    if med_total and highest is not None and med_total > 0:
        stats["viral_dependency_ratio"] = round(highest / med_total, 3)
    else:
        stats["viral_dependency_ratio"] = None

    organic = [
        (n.get("likes") or 0) + (n.get("collects") or 0) + (n.get("comments") or 0)
        for n in valid
        if not n.get("is_platform_labeled_commercial")
        and not n.get("ai_inferred_commercial_signal")
    ]
    commercial = [
        (n.get("likes") or 0) + (n.get("collects") or 0) + (n.get("comments") or 0)
        for n in valid
        if n.get("is_platform_labeled_commercial")
        or n.get("ai_inferred_commercial_signal")
    ]
    stats["organic_post_median_engagement"] = (
        statistics.median(organic) if organic else None)
    stats["commercial_post_median_engagement"] = (
        statistics.median(commercial) if commercial else None)
    return stats


def commercial_breakdown(notes: list[dict]) -> dict[str, Any]:
    """商业内容统计：平台标识（page_observed）与 AI 软广（ai_inferred）分离。"""
    platform = sum(1 for n in notes if n.get("is_platform_labeled_commercial"))
    ai_soft = sum(
        1 for n in notes
        if not n.get("is_platform_labeled_commercial")
        and n.get("ai_inferred_commercial_signal"))
    total = len(notes)
    return {
        "platform_labeled_commercial_posts": platform,
        "platform_labeled_source": "page_observed",
        "ai_inferred_commercial_posts": ai_soft,
        "ai_inferred_source": "ai_inferred",
        "total_commercial_signals": platform + ai_soft,
        "commercial_signal_ratio": round((platform + ai_soft) / total, 3) if total else None,
    }


# ---------- 10 维评分 ----------

def _text_corpus(creator: dict) -> str:
    parts = [creator.get("bio") or ""]
    parts.extend(creator.get("recent_titles_sample") or [])
    for n in creator.get("representative_notes", []):
        parts.append(n.get("title") or "")
    return " ".join(parts)


def score_target_audience_v2(creator: dict) -> tuple[int, str]:
    base, reasons = 12, ["合格候选池基准（真实个人年轻女性生活创作者）"]
    corpus = _text_corpus(creator)
    if URBAN_JOB_RE.search(corpus):
        base += 3
        reasons.append("都市职场受众信号")
    if SOLO_LIVING_RE.search(corpus):
        base += 2
        reasons.append("独居/一人食/独处生活形态")
    if LIFESTYLE_VLOG_RE.search(corpus):
        base += 1
        reasons.append("生活方式vlog定位")
    if PREGNANCY_RE.search(creator.get("bio") or ""):
        base = min(base, 8)
        reasons.append("孕期/哺乳期人设，与轻醒核心受众偏差，受众分封顶8")
    return min(18, base), "；".join(reasons)


def score_content_track_v2(creator: dict) -> tuple[int, str]:
    cats = set(creator.get("content_categories") or [])
    scenes = set(creator.get("main_scenes") or [])
    base, reasons = 6, []
    if cats & FOOD_SCENE_SET or scenes & FOOD_SCENE_SET:
        base += 4
        reasons.append("食品场景赛道")
    if len(set(cats) | set(scenes)) >= 3:
        base += 3
        reasons.append("多场景生活记录")
    if not reasons:
        return 4, "赛道证据不足"
    return min(13, base), "；".join(reasons) or "赛道证据不足"


def score_scene_match_v2(creator: dict) -> tuple[int, str]:
    scenes = set(creator.get("main_scenes") or [])
    weight = sum(SCENE_WEIGHT.get(s, 0) for s in scenes)
    base = min(8, weight)
    titles = creator.get("recent_titles_sample") or []
    hits = sum(1 for r in TITLE_SCENE_CATEGORIES.values()
               if any(r.search(t) for t in titles))
    base += min(4, hits * 2)
    scene_str = "/".join(sorted(scenes)) if scenes else "无"
    return min(12, base), f"场景命中：{scene_str}；标题场景证据 {hits} 类"


def score_video_expression_v2(creator: dict) -> tuple[int, str]:
    total = creator.get("posts_reviewed_count") or 0
    videos = creator.get("video_posts_in_recent10") or 0
    ratio = videos / total if total else 0
    base = round(ratio * 6)
    reasons = [f"近{total}篇视频占比{ratio:.0%}"]
    fmt = creator.get("primary_format")
    if fmt == "voiceover":
        base += 3
        reasons.append("实测真人口播/旁白")
    elif fmt == "subtitle_immersive":
        base += 2
        reasons.append("沉浸式字幕型")
    notes = creator.get("representative_notes") or []
    durations = [n.get("duration_seconds") for n in notes
                 if n.get("note_type") == "video" and n.get("duration_seconds")]
    if durations and max(durations) >= 30:
        base += 1
        reasons.append("代表视频时长适合脚本拆解")
    return min(10, base), "；".join(reasons)


def score_food_integration_v2(creator: dict) -> tuple[int, str]:
    base, reasons = 0, []
    scenes = set(creator.get("main_scenes") or [])
    if scenes & FOOD_SCENE_SET:
        base += 6
        reasons.append("食品核心场景")
    titles = list(creator.get("recent_titles_sample") or [])
    titles.extend(n.get("title") or "" for n in creator.get("representative_notes", []))
    food_titles = sum(1 for t in titles if t and FOOD_TITLE_RE.search(t))
    base += min(4, food_titles * 2)
    if food_titles:
        reasons.append(f"食品相关标题{food_titles}条")
    corpus = _text_corpus(creator)
    if DRINK_RE.search(corpus):
        base += 3
        reasons.append("存在咖啡/茶/酸奶等饮品植入空间")
    return min(13, base), "；".join(reasons) if reasons else "食品植入证据不足"


def score_commercial_naturalness_v2(
    creator: dict, breakdown: dict[str, Any] | None = None,
) -> tuple[int, str]:
    """商业自然度：结合商业内容实际表现，不得仅凭平台标识为 0 判自然。

    有真实植入且商业内容互动不弱于自然内容 = 植入能力已被验证（高分）；
    无商业信号 = 内容自然但植入能力未验证（中高分）；
    商业内容互动显著塌落 = 硬广感（低分）。
    """
    reasons = []
    if breakdown is not None:
        platform_n = breakdown["platform_labeled_commercial_posts"]
        ai_n = breakdown["ai_inferred_commercial_posts"]
        organic = breakdown.get("organic_median")
        commercial = breakdown.get("commercial_median")
        if platform_n == 0 and ai_n == 0:
            base = 6
            reasons.append("近10篇无平台标识商单且无AI识别软广信号，内容自然")
        else:
            if platform_n:
                reasons.append(f"平台标识商单{platform_n}条（page_observed）")
            if ai_n:
                reasons.append(f"AI识别软广信号{ai_n}条（ai_inferred）")
            if organic and commercial:
                if commercial >= organic * 0.8:
                    base = 8
                    reasons.append("商业内容互动与自然内容相当，植入自然度已被验证")
                elif commercial >= organic * 0.5:
                    base = 6
                    reasons.append("商业内容互动略低于自然内容")
                else:
                    base = 4
                    reasons.append("商业内容互动明显塌落，硬广感")
            else:
                base = 6
                reasons.append("商业互动对照数据不足，按中性评分")
    else:
        base = 4
        reasons.append("无商业内容统计数据")
    corpus = _text_corpus(creator)
    for keyword, bonus, reason in COMMERCIAL_BONUS_RULES:
        if keyword in corpus:
            base = min(8, base + bonus - 2)  # 关键词证据微调，不与互动证据双重加分
            reasons.append(reason)
            break
    return min(8, base), "；".join(reasons)


def score_executability_v2(creator: dict) -> tuple[int, str]:
    base, reasons = 5, ["居家vlog轻制作形态（候选池共性）"]
    if creator.get("primary_format") == "voiceover":
        base += 2
        reasons.append("口播型脚本可控性强")
    elif creator.get("primary_format") == "subtitle_immersive":
        base += 1
        reasons.append("沉浸字幕型制作流程标准化")
    scenes = set(creator.get("main_scenes") or [])
    if scenes & {"通勤/办公室", "下午茶"}:
        base += 1
        reasons.append("多场景调度经验")
    return min(8, base), "；".join(reasons)


def score_follower_scale_fit(creator: dict) -> tuple[int, str, str]:
    """粉丝量级适配：不是越多越好；预算未确认，上限 5/7。

    返回 (score, tier, reason)。
    """
    followers = parse_followers(creator.get("followers"))
    tier = creator_tier(followers)
    if tier == TIER_UNKNOWN:
        return 2, tier, "粉丝数未获取，量级适配无法确认，保守给分"
    table = {
        TIER_UNDER_1K: (2, "粉丝<1000（KOC种子级）：自然种草真实感强但传播能力有限，"
                          "仅作种子铺量或风格参考"),
        TIER_1K_10K: (4, "粉丝1k-10k（KOC腰部）：种草性价比高、互动真实，"
                        "适合自然植入，传播力有限"),
        TIER_10K_100K: (5, "粉丝1万-10万（腰部达人）：传播与种草平衡最佳区间，"
                          "预算适配性好"),
        TIER_100K_500K: (5, "粉丝10万-50万（头部腰部）：传播能力强，"
                           "需确认预算适配（预算未定，不给满7分）"),
        TIER_OVER_500K: (3, "粉丝>50万（头部）：传播强但商单成本高、"
                           "自然种草感下降，预算未确认下适配性中等"),
    }
    score, reason = table[tier]
    return min(FOLLOWER_SCALE_FIT_CAP, score), tier, reason


def score_engagement_quality(
    stats: dict[str, Any], followers: int | None,
) -> tuple[int, str]:
    """近期互动质量（6 分）：中位数互动、池内互动率、爆款依赖度。"""
    if not stats or not stats.get("median_total_engagement"):
        return 0, "无互动数据"
    base, reasons = 0, []
    med = stats["median_total_engagement"]
    if med >= 1000:
        base += 3
    elif med >= 300:
        base += 2
    elif med >= 50:
        base += 1
    reasons.append(f"最近10篇中位互动{med:.0f}")
    rate = stats.get("median_engagement_rate")
    if rate is not None:
        if rate >= 0.02:
            base += 2
        elif rate >= 0.005:
            base += 1
        reasons.append(f"池内互动率{rate:.2%}（仅内部比较）")
    else:
        reasons.append("粉丝数缺失，互动率无法计算")
    viral = stats.get("viral_dependency_ratio")
    if viral is not None:
        if viral <= 5:
            base += 1
            reasons.append(f"爆款依赖度{viral:.1f}，互动稳定")
        else:
            reasons.append(f"爆款依赖度{viral:.1f}，存在单篇爆款驱动风险")
    return min(6, base), "；".join(reasons)


def score_compliance_v2(creator: dict) -> tuple[int, str]:
    corpus = _text_corpus(creator)
    risks = []
    if re.search(r"治疗|疗效|降糖|降血糖|胰岛素|糖尿病", corpus):
        risks.append("医疗/降糖类表达")
    if BODY_ANXIETY_RE.search(corpus):
        risks.append("身材/减重结果表达（扣分项已另计）")
    if risks:
        return max(0, 5 - 3 * len([r for r in risks if "医疗" in r])), "；".join(risks)
    return 5, "未见明显合规风险"


def body_anxiety_penalty_v2(creator: dict) -> tuple[int, str]:
    penalty, reasons = 0, []
    bio = creator.get("bio") or ""
    if BODY_ANXIETY_RE.search(bio):
        penalty += 5
        reasons.append("bio含身材/减重表达，人设级依赖 -5")
    if BODY_METRICS_RE.search(bio):
        penalty += 3
        reasons.append("bio标注身高体重数字，身材标签人设 -3")
    titles = {t for t in (creator.get("recent_titles_sample") or [])}
    for n in creator.get("representative_notes", []):
        if n.get("title"):
            titles.add(n["title"])
    title_hits = [t for t in titles if BODY_ANXIETY_RE.search(t)]
    if len(title_hits) >= 2:
        penalty += 5
        reasons.append(f"{len(title_hits)}条不同标题含身材结果表达，内容级依赖 -5")
    elif len(title_hits) == 1:
        penalty += 3
        reasons.append("1条标题轻度提及身材结果表达，非主要依赖 -3")
    return min(15, penalty), "；".join(reasons)


CREATOR_EVIDENCE_FIELDS_V2 = (
    "bio", "followers", "latest_post_time", "posts_reviewed_count",
    "primary_format", "main_scenes",
)
NOTE_EVIDENCE_FIELDS_V2 = (
    "note_id", "title", "publish_time", "note_type", "duration_seconds",
    "likes", "has_voiceover", "has_on_screen_text",
)


def evidence_completeness_v2(creator: dict) -> tuple[float, list[str]]:
    missing = []
    total = len(CREATOR_EVIDENCE_FIELDS_V2)
    for f in CREATOR_EVIDENCE_FIELDS_V2:
        v = creator.get(f)
        if v is None or v == "" or v == []:
            missing.append(f"creator.{f}")
    notes = creator.get("representative_notes", [])[:3]
    total += len(NOTE_EVIDENCE_FIELDS_V2) * len(notes)
    for i, note in enumerate(notes):
        for f in NOTE_EVIDENCE_FIELDS_V2:
            if note.get(f) is None or note.get(f) == "":
                missing.append(f"notes[{i}].{f}")
    if not notes:
        missing.append("representative_notes")
        total += 1
    ratio = 1 - len(missing) / max(1, total)
    return ratio, missing


def grade_of_v2(total: int) -> str:
    if total >= 90:
        return "重点候选"
    if total >= MIN_FORMAL_SCORE_V2:
        return "正式研究候选"
    if total >= 80:
        return "仅风格参考"
    return "淘汰"


def score_creator_v2(
    creator: dict,
    engagement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """v2 评分主函数。

    creator：深核记录；engagement：stage_3_engagement_15.json 中对应记录
    （含 notes 列表与 followers）。
    """
    followers = parse_followers(creator.get("followers"))
    notes = (engagement or {}).get("notes") or []
    stats = engagement_stats(notes, followers)
    breakdown = commercial_breakdown(notes)
    if stats.get("organic_post_median_engagement") is not None:
        breakdown["organic_median"] = stats["organic_post_median_engagement"]
        breakdown["commercial_median"] = stats["commercial_post_median_engagement"]

    dim_funcs = {
        "target_audience": lambda c: score_target_audience_v2(c),
        "content_track": lambda c: score_content_track_v2(c),
        "scene_match": lambda c: score_scene_match_v2(c),
        "video_expression": lambda c: score_video_expression_v2(c),
        "food_integration": lambda c: score_food_integration_v2(c),
        "commercial_naturalness": lambda c: score_commercial_naturalness_v2(c, breakdown),
        "executability": lambda c: score_executability_v2(c),
        "engagement_quality": lambda c: score_engagement_quality(stats, followers),
        "compliance": lambda c: score_compliance_v2(c),
    }
    dimensions: dict[str, dict] = {}
    for name, func in dim_funcs.items():
        value, reason = func(creator)
        dimensions[name] = {"score": value, "max": DIMENSION_MAX_V2[name],
                            "reason": reason}
    fs_score, tier, fs_reason = score_follower_scale_fit(creator)
    dimensions["follower_scale_fit"] = {
        "score": fs_score, "max": DIMENSION_MAX_V2["follower_scale_fit"],
        "reason": fs_reason}

    raw_total = sum(d["score"] for d in dimensions.values())
    penalty, penalty_reason = body_anxiety_penalty_v2(creator)
    completeness, missing = evidence_completeness_v2(creator)

    caps = []
    total = raw_total - penalty
    if not creator.get("posts_reviewed_count"):
        total = min(total, 79)
        caps.append("未完成主页核验，封顶79")
    elif completeness < 0.8:
        total = min(total, 84)
        caps.append(f"证据缺失率{1 - completeness:.0%}>20%，封顶84")

    selection_tier = None
    if tier == TIER_UNDER_1K:
        selection_tier = UNDER_1K_SELECTION_TIER
        if total > UNDER_1K_TOTAL_CAP:
            total = UNDER_1K_TOTAL_CAP
            caps.append(f"粉丝<1000，KOC种子候选，总分封顶{UNDER_1K_TOTAL_CAP}")
    total = max(0, min(TOTAL_MAX_V2, total))

    grade = grade_of_v2(total)
    if selection_tier == UNDER_1K_SELECTION_TIER and grade in ("重点候选", "正式研究候选"):
        grade = "仅风格参考"
        caps.append("under_1k 不得评为重点/正式候选，降级为仅风格参考")

    return {
        "creator_id": creator["creator_id"],
        "nickname": creator["nickname"],
        "model": "v2_10dim",
        "followers": followers,
        "creator_tier": tier,
        "selection_tier": selection_tier,
        "follower_scale_fit_score": fs_score,
        "follower_scale_fit_reason": fs_reason,
        "dimensions": dimensions,
        "raw_total": raw_total,
        "body_anxiety_penalty": penalty,
        "body_anxiety_reason": penalty_reason,
        "evidence_completeness": round(completeness, 3),
        "evidence_missing": missing,
        "caps_applied": caps,
        "total": total,
        "grade": grade,
        "engagement_stats": stats,
        "commercial_breakdown": breakdown,
    }
