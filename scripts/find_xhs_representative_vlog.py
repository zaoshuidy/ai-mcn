"""Stage 2 代表性生活 Vlog 筛选脚本（30—120 秒真实视频）。

复用专用 Chrome CDP 登录态（D-0009 方向B），不新建浏览器基础设施。
流程：CDP 连接 → 登录门禁检查 → 软导航到搜索页 → SEARCH_NOTES 模板提取
→ 逐个打开视频候选笔记（最多 15 条）→ 按筛选规则判定 → 首个合格者落盘。

筛选规则（全部满足才入选）：
- note_type == video；时长 30—120 秒；最近 180 天发布；
- 真实个人创作者（redOfficialVerifyType 为空/个人，排除品牌官方号）；
- 标题命中早餐/一人食/通勤/下午茶/运动后加餐等食品生活场景；
- 排除纯减肥教程、医疗内容、极端身材表达；
- canonical_url 不含 xsec_token；human_verified 保持 false。

只读：不点赞/收藏/评论/关注/私信/发布，不导出 Cookie，不绕过验证码。
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.xhs_cdp_browser_adapter import (  # noqa: E402
    CdpUnavailable,
    XhsCdpBrowserAdapter,
    XhsCdpReadonlyPolicy,
    is_login_gate,
)

POLICY_PATH = ROOT / "config/xhs_cdp_readonly_policy.yaml"
OUT_PATH = ROOT / "data/processed/xhs_representative_video_candidate.json"
AUDIT_PATH = ROOT / "tmp/xhs_representative_video/search_audit.json"

# 搜索关键词（按优先级；首个产生合格候选即停止）
QUERIES = ["早餐vlog", "一人食vlog", "上班族早餐"]

# 食品生活场景信号（标题命中其一）
SCENE_HINTS = [
    "早餐", "一人食", "下午茶", "通勤", "加餐", "吃什么", "三餐", "便当",
    "做饭", "厨房", "食堂", "带饭",
]

# 排除信号：纯减肥教程 / 医疗 / 极端身材表达
EXCLUDE_HINTS = [
    "下颌线", "暴瘦", "燃脂", "瘦脸", "吸脂", "医疗", "医院", "病",
    "减肥药", "抽脂", "瘦身教程",
]

MAX_CANDIDATES = 15
MIN_DURATION_S = 30.0
MAX_DURATION_S = 120.0
MAX_AGE_DAYS = 180
PAGE_INTERVAL_S = 3.0  # 每次页面请求间隔至少 3 秒


def normalize_duration_seconds(value) -> float | None:
    """页面 video_duration 可能是毫秒或秒，统一到秒。"""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return v / 1000.0 if v > 1000 else v


def title_hits(title: str, hints: list[str]) -> list[str]:
    return [h for h in hints if h in (title or "")]


def is_brand_official(media: dict) -> bool:
    """redOfficialVerifyType: None/0 视为个人；>0 视为官方/品牌号。"""
    v = media.get("official_verify")
    if v is None:
        return False
    try:
        return int(v) > 0
    except (TypeError, ValueError):
        return False


def publish_within_days(time_ms, days: int = MAX_AGE_DAYS) -> bool:
    if not time_ms:
        return False
    try:
        ts = float(time_ms) / 1000.0
    except (TypeError, ValueError):
        return False
    age_s = time.time() - ts
    return 0 <= age_s <= days * 86400


def evaluate_candidate(media: dict) -> tuple[bool, list[str]]:
    """返回 (是否合格, 失败原因列表)。"""
    reasons: list[str] = []
    if media.get("type") != "video":
        reasons.append("not_video")
    dur = normalize_duration_seconds(media.get("video_duration"))
    if dur is None:
        reasons.append("duration_unknown")
    elif not (MIN_DURATION_S <= dur <= MAX_DURATION_S):
        reasons.append(f"duration_out_of_range({dur:.1f}s)")
    if not publish_within_days(media.get("time")):
        reasons.append("not_within_180d")
    if is_brand_official(media):
        reasons.append("brand_official_account")
    title = media.get("title") or ""
    if not title_hits(title, SCENE_HINTS):
        reasons.append("no_food_scene_hint")
    if title_hits(title, EXCLUDE_HINTS):
        reasons.append("excluded_content_signal")
    return (not reasons), reasons


def main() -> int:
    policy = XhsCdpReadonlyPolicy.load(POLICY_PATH, ROOT)
    adapter = XhsCdpBrowserAdapter(policy, ROOT)
    audit: dict = {"queries": [], "checked": [], "actions_log": adapter.actions_log}

    print("[CDP] 连接 127.0.0.1:9222 ...")
    if not adapter.chrome_reachable():
        print("[FAIL] 专用 Chrome CDP 端点不可达，请先运行 scripts/start_xhs_cdp_chrome.ps1")
        return 2
    adapter.connect()
    try:
        pages = adapter.all_pages()
        if not pages:
            print("[FAIL] 专用 Chrome 中没有标签页")
            return 2
        page = pages[0]

        gate = adapter.login_gate_state(page)
        if is_login_gate(gate):
            print("[FAIL] 专用 Chrome 未登录小红书，请人工登录后重跑（不自动登录）")
            return 3
        print(f"[LOGIN] 已登录（logged_in={gate.get('logged_in')}）")

        checked = 0
        winner: dict | None = None
        winner_query = ""

        for query in QUERIES:
            if winner or checked >= MAX_CANDIDATES:
                break
            search_url = (
                "https://www.xiaohongshu.com/search_result?keyword="
                + urllib.parse.quote(query)
                + "&source=web_explore_feed"
            )
            print(f"[SEARCH] {query}")
            adapter.soft_navigate_to(page, search_url, "search_result")
            time.sleep(PAGE_INTERVAL_S)

            notes: list[dict] = []
            for _ in range(6):  # 等待 feeds 异步加载
                notes = adapter.extract_search_notes(page)
                if notes:
                    break
                time.sleep(2)
            videos = [n for n in notes if n.get("type") == "video" and n.get("note_id")]
            audit["queries"].append(
                {"query": query, "total": len(notes), "videos": len(videos)})
            print(f"[SEARCH] 结果 {len(notes)} 条，视频 {len(videos)} 条")

            for item in videos:
                if checked >= MAX_CANDIDATES or winner:
                    break
                checked += 1
                note_id = item["note_id"]
                token = item.get("xsec_token") or ""
                url = f"https://www.xiaohongshu.com/explore/{note_id}"
                if token:
                    url += f"?xsec_token={token}&xsec_source=pc_search"
                try:
                    adapter.soft_navigate_to(page, url, note_id)
                    time.sleep(PAGE_INTERVAL_S)
                    media = adapter.extract_note_media(page)
                except CdpUnavailable as exc:
                    audit["checked"].append(
                        {"note_id": note_id, "ok": False, "reasons": [f"open_failed:{exc}"]})
                    continue
                if not media:
                    audit["checked"].append(
                        {"note_id": note_id, "ok": False, "reasons": ["no_media_state"]})
                    continue
                ok, reasons = evaluate_candidate(media)
                dur = normalize_duration_seconds(media.get("video_duration"))
                audit["checked"].append({
                    "note_id": note_id,
                    "title": media.get("title"),
                    "duration_s": dur,
                    "ok": ok,
                    "reasons": reasons,
                })
                print(f"[CHECK {checked}/{MAX_CANDIDATES}] {media.get('title', '')[:30]} "
                      f"dur={dur} ok={ok} {reasons if not ok else ''}")
                if ok:
                    winner = media
                    winner_query = query

        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2), "utf-8")

        if not winner:
            print(f"[FAIL] 检查 {checked} 条视频候选，无一条满足全部筛选规则（见 {AUDIT_PATH}）")
            return 4

        dur = normalize_duration_seconds(winner.get("video_duration"))
        candidate = {
            "note_id": winner["note_id"],
            "canonical_url": f"https://www.xiaohongshu.com/explore/{winner['note_id']}",
            "creator_name": winner.get("nickname"),
            "creator_profile_url": (
                f"https://www.xiaohongshu.com/user/profile/{winner['user_id']}"
                if winner.get("user_id") else None
            ),
            "title": winner.get("title"),
            "publish_time": datetime.fromtimestamp(
                float(winner["time"]) / 1000.0, tz=timezone.utc
            ).isoformat() if winner.get("time") else None,
            "duration_seconds": round(dur, 1) if dur else None,
            "note_type": "video",
            "selection_reason": (
                f"搜索「{winner_query}」第 {checked} 条候选；type=video；"
                f"时长 {dur:.1f}s 在 30—120s 内；180 天内发布；"
                f"非品牌官方号；标题命中食品生活场景；无排除信号。"
                "口播/字幕与场景段落数以实际转写和抽帧分析为准。"
            ),
            "usage_scope": "stage_2_representative_poc",
            "human_verified": False,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "source": "page_observed",
        }
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), "utf-8")
        print(f"[OK] 代表性候选已保存: {OUT_PATH}")
        print(f"     {candidate['creator_name']}《{candidate['title']}》{dur:.1f}s")
        return 0
    finally:
        adapter.close()


if __name__ == "__main__":
    raise SystemExit(main())
