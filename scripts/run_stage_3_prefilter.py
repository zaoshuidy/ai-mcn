"""Stage 3 预筛：113 位原始候选 → 最多 30 位进入主页核验（离线，不访问页面）。

只使用搜索结果页已采集证据（标题/类型/昵称/user_id），不新增页面访问。
预筛维度：视频或Vlog内容、食品生活场景、排除官方号/店铺号/纯图文知识号/
减肥结果承诺/医疗降糖内容；creator_id 有效；user_id 去重。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

POOL_PATH = ROOT / "data/processed/stage_3_creator_pool.json"
OUT_PATH = ROOT / "data/processed/stage_3_prefiltered_30.json"
MAX_PREFILTERED = 30

SCENE_HINTS = {
    "早餐": ["早餐", "早饭", "晨间", "早起", "morning"],
    "一人食": ["一人食", "独居", "一个人"],
    "通勤/办公室": ["通勤", "上班", "办公室", "打工人", "工位", "下班"],
    "下午茶": ["下午茶", "咖啡", "奶茶"],
    "健身/运动后": ["健身", "运动", "锻炼", "爬坡", "跑步", "瑜伽", "加餐"],
    "酸奶/轻食": ["酸奶", "酸奶碗", "轻食", "沙拉"],
}
EXCLUDE_TITLE = ["暴瘦", "掉秤", "燃脂", "下颌线", "瘦脸", "月瘦", "瘦身教程",
                 "降糖", "血糖", "糖尿病", "治疗", "医院", "医疗", "减肥药"]
EXCLUDE_NICK = ["旗舰店", "官方", "品牌", "小店", "严选", "优选", "商城",
                "医疗", "医院", " clinic"]
VLOG_HINTS = ["vlog", "Vlog", "VLOG", "日常", "日记", "记录"]


def classify_scene(title: str) -> list[str]:
    return [s for s, hints in SCENE_HINTS.items()
            if any(h in title for h in hints)]


def prefilter_score(cand: dict) -> tuple[int, list[str], list[str]]:
    """返回 (分数, 场景, 风险)。规则透明可复现。"""
    note = cand.get("first_note") or {}
    title = note.get("title") or ""
    ntype = note.get("type") or ""
    nick = cand.get("nickname") or ""
    score = 0
    reasons: list[str] = []
    risks: list[str] = []

    if not cand.get("creator_id"):
        return 0, [], ["invalid_creator_id"]
    if any(h in nick for h in EXCLUDE_NICK):
        return 0, [], ["shop_or_brand_nickname"]
    title_risks = [h for h in EXCLUDE_TITLE if h in title]
    if title_risks:
        return 0, [], [f"excluded_title:{','.join(title_risks)}"]

    scenes = classify_scene(title)
    if ntype == "video":
        score += 40
        reasons.append("视频内容+40")
    else:
        score += 10
        reasons.append("图文内容+10")
    if scenes:
        score += 30
        reasons.append(f"场景命中({','.join(scenes)})+30")
    if any(h in title for h in VLOG_HINTS):
        score += 20
        reasons.append("Vlog/日常属性+20")
    if ntype != "video":
        risks.append("非视频：可能不满足视频脚本研究")
    if not scenes:
        risks.append("场景未命中：可能偏离 Brief")
    return score, scenes, risks


def main() -> int:
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))["candidates"]
    seen: set[str] = set()
    scored: list[dict] = []
    dropped: dict[str, int] = {}
    for cand in pool:
        uid = cand.get("creator_id")
        if not uid or uid in seen:
            continue
        seen.add(uid)
        score, scenes, risks = prefilter_score(cand)
        if score <= 0:
            key = risks[0].split(":")[0] if risks else "score_zero"
            dropped[key] = dropped.get(key, 0) + 1
            continue
        note = cand.get("first_note") or {}
        scored.append({
            "creator_id": uid,
            "nickname": cand.get("nickname"),
            "profile_url": cand.get("profile_url"),
            "source_keyword": cand.get("source_query"),
            "source_note_id": note.get("note_id"),
            "source_note_title": note.get("title"),
            "source_note_type": note.get("type"),
            "publish_time": None,  # 搜索页无发布时间，主页核验时补
            "preliminary_scene": scenes,
            "preliminary_risks": risks,
            "prefilter_score": score,
            "selection_reason": f"搜索「{cand.get('source_query')}」召回；"
                                f"{'/'.join(scenes) or '场景待核验'}；"
                                f"{'视频' if note.get('type') == 'video' else '图文'}",
            "source": "page_observed",
            "human_verified": False,
        })
    scored.sort(key=lambda x: (-x["prefilter_score"], x["creator_id"]))
    selected = scored[:MAX_PREFILTERED]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "pool_size": len(pool),
        "prefiltered": len(selected),
        "dropped_by_reason": dropped,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidates": selected,
    }, ensure_ascii=False, indent=2), "utf-8")
    print(f"[OK] 池 {len(pool)} → 预筛 {len(selected)}；淘汰分布: {dropped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
