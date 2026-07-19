"""Stage 3 达人评分模型（纯函数，离线可测，评分可复现）。

总分 100，8 个维度：
- 目标受众匹配 target_audience        20
- 内容赛道匹配 content_track          15
- 早餐/加餐/下午茶场景匹配 scene_match 15
- 视频表达能力 video_expression       10
- 食品自然植入能力 food_integration   15
- 商业内容自然度 commercial_naturalness 10
- 拍摄与脚本可执行性 executability    10
- 合规安全 compliance                  5

分级：90-100 重点候选；85-89 正式研究候选；80-84 仅风格参考；<80 淘汰。
封顶与扣分规则：
- 证据字段缺失率 >20%：总分封顶 84；
- 未完成主页核验：总分封顶 79；
- 身材/减脂/外貌焦虑依赖：按 0/3/5/6 档扣分（bio 人设级 -5，bio 身高体重数字 -3，
  去重后标题命中 >=2 条 -5，1 条 -3；累计封顶 -15，对应任务书 5-15 分档）。

基准分校准说明：进入本评分的 15 位均已完成 113→30→15 的证据链筛选
（真实个人创作者、180 天活跃、场景命中、非营销号），因此各维度基准分
反映"已合格候选池"水平，差异化加减分基于 page_observed / ai_inferred 证据。

输入为 stage_3_deep_review_15.json 中的达人记录（含探测合并后的
primary_format 与代表笔记 has_voiceover/has_on_screen_text 字段）。
"""

from __future__ import annotations

import re
from typing import Any

DIMENSION_MAX = {
    "target_audience": 20,
    "content_track": 15,
    "scene_match": 15,
    "video_expression": 10,
    "food_integration": 15,
    "commercial_naturalness": 10,
    "executability": 10,
    "compliance": 5,
}
TOTAL_MAX = sum(DIMENSION_MAX.values())  # 100

GRADE_KEY_CANDIDATE = "重点候选"      # >= 90
GRADE_FORMAL = "正式研究候选"          # 85-89
GRADE_REFERENCE_ONLY = "仅风格参考"    # 80-84
GRADE_ELIMINATED = "淘汰"             # < 80
MIN_FORMAL_SCORE = 85

# ---- 关键词表（评分依据可追溯） ----
URBAN_JOB_RE = re.compile(
    r"打工人|上班|通勤|电商|互联网|搬砖|职场|下班|私企|HR|hr|杭漂|深漂|北漂|沪漂")
SOLO_LIVING_RE = re.compile(r"独居|一人食|独处|独自|一个人")
LIFESTYLE_VLOG_RE = re.compile(r"vlog|Vlog|VLOG|日常|生活|记录|日记")
PREGNANCY_RE = re.compile(r"孕|产妇|哺乳期")
PARENT_RE = re.compile(r"幼崽|宝妈|带娃|监护人")
FOOD_SCENE_SET = {"早餐", "一人食", "酸奶/轻食"}
SCENE_WEIGHT = {"早餐": 5, "一人食": 5, "酸奶/轻食": 5, "下午茶": 4,
                "通勤/办公室": 3, "健身/运动后": 3}
FOOD_TITLE_RE = re.compile(
    r"吃|餐|食|厨|烹饪|三明治|沙拉|酸奶|咖啡|茶|水果|烘焙|做饭|零食|brunch|Brunch")
DRINK_RE = re.compile(r"咖啡|茶|酸奶|奶昔|饮品|果汁|霸王茶姬|CHAGEE")
BODY_ANXIETY_RE = re.compile(
    r"减肥|减脂|瘦脸|掉秤|暴瘦|燃脂|长胎不长肉|维持体重|瘦身|瘦腿|瘦肚子")
BODY_METRICS_RE = re.compile(r"\d{3}\s*/\s*\d{2,3}\s*(kg|KG|斤)?")  # 如 166/51、163/44kg
AI_CONTENT_RE = re.compile(r"AI生成|AI 生成|ai生成")
SELF_PROMO_RE = re.compile(r"创业|开店")

# 标题场景证据类别（scene_match 加分项，每类 +2，封顶 +5）
TITLE_SCENE_CATEGORIES = {
    "早餐类": re.compile(r"早餐|brunch|Brunch|早午餐|晨间"),
    "一人食/做饭类": re.compile(r"一人食|做饭|厨房|下厨|两餐|三餐"),
    "下午茶/饮品类": re.compile(r"下午茶|喝茶|咖啡|酸奶碗|奶昔"),
}

# 视觉确认的商单植入自然度加分（证据文本关键词 -> 加分）
COMMERCIAL_BONUS_RULES = [
    ("霸王茶姬", 3, "饮品商单融入晚间生活场景，植入自然"),
    ("AI搜索", 2, "App推广植入翻包场景，自然度中等"),
    ("雅顿", 2, "护肤品商单常规口播植入，自然度中等"),
    ("自动泊车", 1, "汽车商单卖点口播，硬广感较强"),
]

# 证据完整性检查清单（creator级6项 + 每篇代表笔记8项）
CREATOR_EVIDENCE_FIELDS = (
    "bio", "followers", "latest_post_time", "posts_reviewed_count",
    "primary_format", "main_scenes",
)
NOTE_EVIDENCE_FIELDS = (
    "note_id", "title", "publish_time", "note_type", "duration_seconds",
    "likes", "has_voiceover", "has_on_screen_text",
)
EVIDENCE_MISSING_CAP_RATIO = 0.2
EVIDENCE_CAP_SCORE = 84
NO_DEEP_REVIEW_CAP = 79


def _text_corpus(creator: dict) -> str:
    parts = [creator.get("bio") or ""]
    parts.extend(creator.get("recent_titles_sample") or [])
    for n in creator.get("representative_notes", []):
        parts.append(n.get("title") or "")
    return "\n".join(parts)


def _fmt_pct(value: float) -> str:
    return f"{value:.0%}"


def score_target_audience(creator: dict) -> tuple[int, str]:
    """目标受众匹配（20）：一二线城市20-35岁都市女性，轻健康生活。

    基准14：已通过 113→30→15 证据链筛选的真实个人年轻女性生活创作者。
    """
    bio = creator.get("bio") or ""
    corpus = _text_corpus(creator)
    if PREGNANCY_RE.search(bio):
        return 6, "孕产特殊人群，与轻醒核心受众（都市年轻女性轻生活）偏离，封顶低分"
    scenes = set(creator.get("main_scenes") or [])
    score, reasons = 14, ["合格候选池基准（真实个人年轻女性生活创作者）"]
    if URBAN_JOB_RE.search(corpus) or "通勤/办公室" in scenes:
        score += 3
        reasons.append("都市职场受众信号（打工人/通勤/下班）")
    if SOLO_LIVING_RE.search(corpus):
        score += 2
        reasons.append("独居/一人食/独处生活形态")
    if LIFESTYLE_VLOG_RE.search(bio):
        score += 1
        reasons.append("生活方式vlog定位明确")
    if PARENT_RE.search(bio):
        score -= 3
        reasons.append("宝妈身份，受众年龄层上移（-3）")
    score = max(0, min(DIMENSION_MAX["target_audience"], score))
    return score, "；".join(reasons)


def score_content_track(creator: dict) -> tuple[int, str]:
    """内容赛道匹配（15）：美食+生活方式vlog为核心赛道。"""
    scenes = set(creator.get("main_scenes") or [])
    if scenes & FOOD_SCENE_SET:
        score, base = 14, f"食品场景赛道（{'/'.join(sorted(scenes & FOOD_SCENE_SET))}）"
    elif "下午茶" in scenes:
        score, base = 12, "下午茶饮品场景赛道"
    elif "通勤/办公室" in scenes:
        score, base = 11, "通勤/办公室都市生活赛道"
    elif scenes == {"健身/运动后"}:
        score, base = 6, "健身主导赛道，偏离美食生活核心赛道"
    else:
        score, base = 5, "赛道证据不足"
    if len(scenes) >= 2:
        score += 1
        base += f"；多场景生活记录（{len(scenes)}类）"
    return min(DIMENSION_MAX["content_track"], score), base


def score_scene_match(creator: dict) -> tuple[int, str]:
    """早餐/加餐/下午茶场景匹配（15）：场景权重和（封顶12）+标题场景证据（封顶+5）。"""
    scenes = set(creator.get("main_scenes") or [])
    raw = sum(SCENE_WEIGHT[s] for s in scenes if s in SCENE_WEIGHT)
    base_score = min(12, raw)
    hits = [s for s in scenes if s in SCENE_WEIGHT]
    titles = (creator.get("recent_titles_sample") or []) + [
        n.get("title") or "" for n in creator.get("representative_notes", [])]
    title_cats = [name for name, rex in TITLE_SCENE_CATEGORIES.items()
                  if any(rex.search(t) for t in titles)]
    bonus = min(5, 2 * len(title_cats))
    score = min(DIMENSION_MAX["scene_match"], base_score + bonus)
    reason = f"场景命中：{'/'.join(sorted(hits)) or '无'}"
    if title_cats:
        reason += f"；标题场景证据（{'/'.join(title_cats)}）+{bonus}"
    return score, reason


def score_video_expression(creator: dict) -> tuple[int, str]:
    """视频表达能力（10）。"""
    reviewed = creator.get("posts_reviewed_count") or 10
    videos = creator.get("video_posts_in_recent10") or 0
    ratio_score = round(6 * videos / max(1, reviewed))
    reasons = [f"近{reviewed}篇视频占比{_fmt_pct(videos / max(1, reviewed))}"]
    fmt = creator.get("primary_format")
    if fmt == "voiceover":
        ratio_score += 2
        reasons.append("实测真人口播/旁白")
    elif fmt == "subtitle_immersive":
        ratio_score += 2
        reasons.append("实测沉浸式字幕型（无口播）")
    durations = [n.get("duration_seconds") for n in creator.get("representative_notes", [])
                 if isinstance(n.get("duration_seconds"), (int, float))]
    if any(30 <= d <= 300 for d in durations):
        ratio_score += 2
        reasons.append("代表视频时长30-300s，适合脚本拆解")
    return min(DIMENSION_MAX["video_expression"], ratio_score), "；".join(reasons)


def score_food_integration(creator: dict) -> tuple[int, str]:
    """食品自然植入能力（15）。"""
    scenes = set(creator.get("main_scenes") or [])
    reasons = []
    if scenes & FOOD_SCENE_SET:
        score = 6
        reasons.append(f"食品核心场景（{'/'.join(sorted(scenes & FOOD_SCENE_SET))}）")
    elif "下午茶" in scenes:
        score = 4
        reasons.append("下午茶饮品场景")
    elif "通勤/办公室" in scenes:
        score = 2
        reasons.append("通勤/办公室场景（工位加餐植入空间）")
    else:
        score = 0
    corpus = _text_corpus(creator)
    titles = (creator.get("recent_titles_sample") or []) + [
        n.get("title") or "" for n in creator.get("representative_notes", [])]
    food_hits = sum(1 for t in titles if FOOD_TITLE_RE.search(t))
    if food_hits >= 4:
        score += 6
        reasons.append(f"食品相关标题{food_hits}条")
    elif food_hits >= 2:
        score += 4
        reasons.append(f"食品相关标题{food_hits}条")
    elif food_hits == 1:
        score += 2
        reasons.append(f"食品相关标题{food_hits}条")
    if DRINK_RE.search(corpus):
        score += 3
        reasons.append("存在咖啡/茶/酸奶等饮品植入空间")
    return min(DIMENSION_MAX["food_integration"], score), "；".join(reasons) or "食品证据弱"


def score_commercial_naturalness(creator: dict) -> tuple[int, str]:
    """商业内容自然度（10）。"""
    ratio = creator.get("commercial_post_ratio")
    reasons = []
    if ratio is None:
        score = 6
        reasons.append("商广比未知（保守给分）")
    elif ratio == 0:
        score = 8
        reasons.append("近10篇无商业笔记，内容自然")
    elif ratio <= 0.2:
        score = 5
        reasons.append(f"商广比{_fmt_pct(ratio)}")
    else:
        score = 2
        reasons.append(f"商广比{_fmt_pct(ratio)}偏高")
    for note in creator.get("representative_notes", []):
        evidence = note.get("commercial_evidence") or ""
        for keyword, bonus, text in COMMERCIAL_BONUS_RULES:
            if keyword in evidence:
                score += bonus
                reasons.append(text)
                break
    if AI_CONTENT_RE.search(_text_corpus(creator)):
        score -= 2
        reasons.append("存在AI生成内容，真实性质疑（-2）")
    if SELF_PROMO_RE.search(creator.get("bio") or ""):
        score -= 2
        reasons.append("bio含创业/开店信息，内容为自有生意引流（-2）")
    return max(0, min(DIMENSION_MAX["commercial_naturalness"], score)), "；".join(reasons)


def score_executability(creator: dict) -> tuple[int, str]:
    """拍摄与脚本可执行性（10）：居家轻制作、系列化模板更易复用。"""
    score, reasons = 9, ["居家vlog轻制作形态（候选池共性）"]
    scenes = set(creator.get("main_scenes") or [])
    if "健身/运动后" in scenes:
        score -= 2
        reasons.append("健身房等外部场景占比高，拍摄门槛高（-2）")
    titles = creator.get("recent_titles_sample") or []
    if titles and len(set(titles)) <= len(titles) / 2:
        score += 1
        reasons.append("标题高度模板化，系列可复用（+1）")
    return max(4, min(DIMENSION_MAX["executability"], score)), "；".join(reasons)


def score_compliance(creator: dict) -> tuple[int, str]:
    """合规安全（5）。"""
    score, reasons = 5, []
    risks = set()
    for note in creator.get("representative_notes", []):
        risks.update(note.get("compliance_risks") or [])
    if risks:
        cut = min(3, len(risks))
        score -= cut
        reasons.append(f"代表笔记风险词：{'/'.join(sorted(risks))}（-{cut}）")
    if BODY_ANXIETY_RE.search(creator.get("bio") or ""):
        score -= 2
        reasons.append("bio含身材/减重表达（-2）")
    return max(0, score), "；".join(reasons) or "未见明显合规风险"


DIMENSION_FUNCS = {
    "target_audience": score_target_audience,
    "content_track": score_content_track,
    "scene_match": score_scene_match,
    "video_expression": score_video_expression,
    "food_integration": score_food_integration,
    "commercial_naturalness": score_commercial_naturalness,
    "executability": score_executability,
    "compliance": score_compliance,
}


def body_anxiety_penalty(creator: dict) -> tuple[int, str]:
    """身材/减脂/外貌焦虑依赖扣分（累计封顶-15，对应任务书5-15分档）。

    - bio 含减肥/减脂/瘦身类词：-5（人设级依赖）；
    - bio 含身高体重数字（如 166/51）：-3（身材标签人设）；
    - 去重标题命中 >=2 条：-5（内容级依赖）；
    - 去重标题命中 1 条：-3（轻度提及，非主要依赖）。
    """
    penalty, reasons = 0, []
    bio = creator.get("bio") or ""
    if BODY_ANXIETY_RE.search(bio):
        penalty += 5
        hits = sorted(set(BODY_ANXIETY_RE.findall(bio)))
        reasons.append(f"bio含身材/减重表达（{'/'.join(hits)}），人设级依赖 -5")
    if BODY_METRICS_RE.search(bio):
        penalty += 3
        reasons.append("bio标注身高体重数字，身材标签人设 -3")
    titles = set()
    for t in (creator.get("recent_titles_sample") or []):
        titles.add(t)
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


def evidence_completeness(creator: dict) -> tuple[float, list[str]]:
    """证据完整率：creator级6项 + 每篇代表笔记8项（按实际笔记数）。"""
    missing = []
    total = len(CREATOR_EVIDENCE_FIELDS)
    for f in CREATOR_EVIDENCE_FIELDS:
        v = creator.get(f)
        if v is None or v == "" or v == []:
            missing.append(f"creator.{f}")
    notes = creator.get("representative_notes", [])[:3]
    total += len(NOTE_EVIDENCE_FIELDS) * len(notes)
    for i, note in enumerate(notes):
        for f in NOTE_EVIDENCE_FIELDS:
            if note.get(f) is None or note.get(f) == "":
                missing.append(f"notes[{i}].{f}")
    if not notes:
        missing.append("representative_notes")
        total += 1
    ratio = 1 - len(missing) / max(1, total)
    return ratio, missing


def grade_of(total: int) -> str:
    if total >= 90:
        return GRADE_KEY_CANDIDATE
    if total >= MIN_FORMAL_SCORE:
        return GRADE_FORMAL
    if total >= 80:
        return GRADE_REFERENCE_ONLY
    return GRADE_ELIMINATED


def score_creator(creator: dict) -> dict[str, Any]:
    """对单达人输出逐项分数、依据、封顶与总分（可复现）。"""
    dimensions = {}
    for name, func in DIMENSION_FUNCS.items():
        value, reason = func(creator)
        dimensions[name] = {"score": value, "max": DIMENSION_MAX[name], "reason": reason}
    raw_total = sum(d["score"] for d in dimensions.values())
    penalty, penalty_reason = body_anxiety_penalty(creator)
    completeness, missing = evidence_completeness(creator)
    caps = []
    total = raw_total - penalty
    if not creator.get("posts_reviewed_count"):
        total = min(total, NO_DEEP_REVIEW_CAP)
        caps.append(f"未完成主页核验，封顶{NO_DEEP_REVIEW_CAP}")
    elif completeness < 1 - EVIDENCE_MISSING_CAP_RATIO:
        total = min(total, EVIDENCE_CAP_SCORE)
        caps.append(f"证据缺失率{1 - completeness:.0%}>20%，封顶{EVIDENCE_CAP_SCORE}")
    total = max(0, min(TOTAL_MAX, total))
    return {
        "creator_id": creator["creator_id"],
        "nickname": creator["nickname"],
        "dimensions": dimensions,
        "raw_total": raw_total,
        "body_anxiety_penalty": penalty,
        "body_anxiety_reason": penalty_reason,
        "evidence_completeness": round(completeness, 3),
        "evidence_missing": missing,
        "caps_applied": caps,
        "total": total,
        "grade": grade_of(total),
    }
