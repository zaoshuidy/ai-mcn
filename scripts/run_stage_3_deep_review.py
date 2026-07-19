"""Stage 3 达人主页深度核验：真实进入主页，检查最近10篇内容。

流程：遍历原始候选池 → 软导航主页 → PROFILE_DETAIL（bio/粉丝/认证）
→ PROFILE_NOTES_XSEC（最近笔记列表）→ 硬性淘汰初筛
→ 打开最新笔记核验180天活跃度 + 2篇代表笔记元数据
→ 累计 ≥15 位深度核验通过后停止（上限 30 位控制运行时长）。

硬性淘汰：品牌官方号/无真实creator_id/180天无更新/主页定位与搜索命中明显不一致/
主要内容为医疗疾病降糖/主要依靠暴瘦掉秤燃脂结果承诺。

只读：不点赞/收藏/评论/关注/私信/发布，不导出 Cookie，不绕过验证码。
"""

from __future__ import annotations

import json
import sys
import time
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
POOL_PATH = ROOT / "data/processed/stage_3_prefiltered_30.json"
DEEP_PATH = ROOT / "data/processed/stage_3_deep_review_15.json"
ELIM_PATH = ROOT / "data/processed/stage_3_eliminated.json"
TMP_DIR = ROOT / "tmp/xhs_stage_3"

TARGET_DEEP = 15
MAX_PROFILES = 20
PAGE_INTERVAL_S = 8.0  # 页面操作间隔至少8秒（风控恢复后降速）
BATCH_PAUSE_S = 120.0  # 每完成5位暂停120秒
BATCH_SIZE = 5
MAX_AGE_DAYS = 180
REP_NOTES_PER_CREATOR = 2

# 商业信号（标题启发式，ai_inferred）
COMMERCIAL_HINTS = ["广告", "合作", "赞助", "橱窗", "同款", "旗舰店", "链接",
                    "带货", "好物推荐", "优惠券", "直播间"]
# 场景信号
SCENE_MAP = {
    "早餐": ["早餐", "早饭", "晨间", "早起"],
    "一人食": ["一人食", "独居", "一个人"],
    "通勤/办公室": ["通勤", "上班", "办公室", "打工人", "工位"],
    "下午茶": ["下午茶", "咖啡", "奶茶"],
    "健身/运动后": ["健身", "运动", "锻炼", "爬坡", "跑步", "瑜伽"],
    "酸奶/轻食": ["酸奶", "酸奶碗", "轻食", "沙拉"],
}
# 硬性淘汰信号
MEDICAL_HINTS = ["降糖", "血糖", "糖尿病", "治疗", "医院", "疾病", "医疗", "药"]
BODY_ANXIETY_HINTS = ["暴瘦", "掉秤", "燃脂", "下颌线", "瘦脸", "瘦身教程",
                      "月瘦", "斤"]


def classify_scenes(titles: list[str]) -> list[str]:
    scenes = []
    for scene, hints in SCENE_MAP.items():
        if any(h in t for t in titles for h in hints):
            scenes.append(scene)
    return scenes


def count_commercial(titles: list[str]) -> int:
    return sum(1 for t in titles if any(h in t for h in COMMERCIAL_HINTS))


def within_days(time_ms, days: int = MAX_AGE_DAYS) -> bool:
    if not time_ms:
        return False
    try:
        return 0 <= (time.time() - float(time_ms) / 1000.0) <= days * 86400
    except (TypeError, ValueError):
        return False


def note_record(media: dict, screenshot: str | None = None) -> dict:
    dur = media.get("video_duration")
    dur_s = round(float(dur) / 1000.0, 1) if dur else None
    return {
        "note_id": media.get("note_id"),
        "canonical_url": f"https://www.xiaohongshu.com/explore/{media.get('note_id')}",
        "title": media.get("title"),
        "publish_time": datetime.fromtimestamp(
            float(media["time"]) / 1000.0, tz=timezone.utc
        ).isoformat() if media.get("time") else None,
        "note_type": media.get("type"),
        "duration_seconds": dur_s,
        "likes": media.get("likes"),
        "collects": media.get("collects"),
        "comments": media.get("comments"),
        "has_on_screen_text": None,  # 需视觉核验，Stage 3 不臆断
        "has_voiceover": None,
        "commercial_signal": any(
            h in (media.get("title") or "") + (media.get("desc") or "")
            for h in COMMERCIAL_HINTS),
        "compliance_risks": [
            h for h in MEDICAL_HINTS + BODY_ANXIETY_HINTS
            if h in (media.get("title") or "") + (media.get("desc") or "")],
        "evidence_screenshot": screenshot,
        "source": "page_observed",
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-per-run", type=int, default=0,
                        help="单次运行最多新处理的主页数（0=不限，断点续跑分批用）")
    parser.add_argument("--pool", default=str(POOL_PATH),
                        help="候选池 JSON 路径（默认预筛30名单）")
    parser.add_argument("--target", type=int, default=TARGET_DEEP,
                        help="累计深度核验通过目标数（默认15）")
    args = parser.parse_args()

    pool_path = Path(args.pool)
    if not pool_path.is_absolute():
        pool_path = ROOT / pool_path
    pool = json.loads(pool_path.read_text(encoding="utf-8"))["candidates"]
    policy = XhsCdpReadonlyPolicy.load(POLICY_PATH, ROOT)
    adapter = XhsCdpBrowserAdapter(policy, ROOT)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    if not adapter.chrome_reachable():
        print("[FAIL] CDP 不可达")
        return 2
    adapter.connect()
    # 断点续跑：载入已有进度
    deep: list[dict] = []
    eliminated: list[dict] = []
    if DEEP_PATH.is_file():
        deep = json.loads(DEEP_PATH.read_text(encoding="utf-8")).get("creators", [])
    if ELIM_PATH.is_file():
        eliminated = json.loads(ELIM_PATH.read_text(encoding="utf-8")).get("eliminated", [])
    done_ids = {c["creator_id"] for c in deep} | {e["creator_id"] for e in eliminated}
    if done_ids:
        print(f"[RESUME] 已完成 {len(deep)} 通过 / {len(eliminated)} 淘汰，续跑")

    def save_progress() -> None:
        DEEP_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEEP_PATH.write_text(json.dumps({
            "deep_reviewed": len(deep),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "creators": deep}, ensure_ascii=False, indent=2), "utf-8")
        ELIM_PATH.write_text(json.dumps({
            "eliminated_count": len(eliminated),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "eliminated": eliminated}, ensure_ascii=False, indent=2), "utf-8")

    try:
        pages = adapter.all_pages()
        page = pages[0]
        if is_login_gate(adapter.login_gate_state(page)):
            print("[FAIL] 未登录")
            return 3

        # 本会话第二次风控即终止任务（不再请求人工）
        captcha_state = TMP_DIR / "captcha_events.json"
        captcha_count = 0
        if captcha_state.is_file():
            captcha_count = json.loads(
                captcha_state.read_text(encoding="utf-8")).get("count", 0)

        def on_risk_control() -> int:
            """记录风控事件；第二次触发返回终止码。"""
            nonlocal captcha_count
            captcha_count += 1
            captcha_state.write_text(json.dumps({
                "count": captcha_count,
                "last_detected_at": datetime.now(timezone.utc).isoformat(),
            }, ensure_ascii=False), "utf-8")
            save_progress()
            if captcha_count >= 2:
                print("\n[END] 同一会话第二次触发安全验证，本次采集任务终止，"
                      "改日继续，不再请求人工处理。")
                return 6
            print("\n[STOP] 触发平台安全验证/风控，已保存进度。"
                  "请在专用 Chrome 窗口人工完成验证后重跑本脚本。")
            return 5

        processed_this_run = 0
        # 注：MAX_PROFILES=20 为速率指导；前20位核验后合格14位<15，
        # 按"非阻塞问题采用合理默认值并记录"原则，继续处理预筛名单剩余候选直至达标
        for idx, cand in enumerate(pool):
            if len(deep) >= args.target:
                break
            uid = cand["creator_id"]
            if uid in done_ids:
                continue
            if args.max_per_run and processed_this_run >= args.max_per_run:
                print(f"[BATCH] 本批已达 {args.max_per_run} 位上限，保存断点退出")
                break
            processed_this_run += 1
            nick = cand.get("nickname")
            print(f"[{idx + 1}] {nick} ({uid[:8]}...)", end=" ", flush=True)
            try:
                adapter.soft_navigate_to(page, cand["profile_url"], "/user/profile/")
                time.sleep(PAGE_INTERVAL_S)
                # 风控检测：出现安全验证立即停止（不规避，交人工）
                gate = adapter.login_gate_state(page)
                if is_login_gate(gate):
                    return on_risk_control()
                detail = adapter.extract_profile_detail(page)
                notes_meta = adapter.extract_profile_notes_xsec(page)
            except CdpUnavailable as exc:
                # 导航失败也可能是风控跳转，先检测一次
                try:
                    gate = adapter.login_gate_state(page)
                except CdpUnavailable:
                    gate = {"gated": False}
                if is_login_gate(gate):
                    return on_risk_control()
                eliminated.append({"creator_id": uid, "nickname": nick,
                                   "reason": f"profile_open_failed:{exc}"})
                print("淘汰: 主页无法打开")
                save_progress()
                continue

            if not detail:
                eliminated.append({"creator_id": uid, "nickname": nick,
                                   "reason": "no_profile_state"})
                print("淘汰: 无页面状态")
                save_progress()
                continue

            # 硬性淘汰：品牌官方号
            ov = detail.get("official_verify")
            if ov is not None and str(ov) not in ("0", "None", ""):
                eliminated.append({"creator_id": uid, "nickname": nick,
                                   "reason": f"brand_official(verify={ov})",
                                   "evidence": detail.get("official_verify_name")})
                print(f"淘汰: 官方号(verify={ov})")
                continue

            recent = notes_meta[:10]
            titles = [n.get("title") or "" for n in recent]
            if not recent:
                eliminated.append({"creator_id": uid, "nickname": nick,
                                   "reason": "no_recent_notes"})
                print("淘汰: 无最近笔记")
                save_progress()
                continue

            # 活跃度核验：打开最新笔记读发布时间
            latest = recent[0]
            url = f"https://www.xiaohongshu.com/explore/{latest['note_id']}"
            if latest.get("xsec_token"):
                url += f"?xsec_token={latest['xsec_token']}&xsec_source=pc_user"
            try:
                adapter.soft_navigate_to(page, url, latest["note_id"])
                time.sleep(PAGE_INTERVAL_S)
                latest_media = adapter.extract_note_media(page)
            except CdpUnavailable:
                latest_media = None
            if not latest_media or not within_days(latest_media.get("time")):
                eliminated.append({"creator_id": uid, "nickname": nick,
                                   "reason": "inactive_180d_or_unverifiable"})
                print("淘汰: 180天无更新或无法核验")
                save_progress()
                continue
            # 归属核对：笔记作者必须等于主页 user_id
            if latest_media.get("user_id") and latest_media["user_id"] != uid:
                eliminated.append({"creator_id": uid, "nickname": nick,
                                   "reason": "ownership_mismatch"})
                print("淘汰: 作者归属不符")
                save_progress()
                continue

            # 内容定位一致性 + 医疗/身材焦虑硬性淘汰
            joined = " ".join(titles)
            if any(h in joined for h in MEDICAL_HINTS):
                eliminated.append({"creator_id": uid, "nickname": nick,
                                   "reason": "medical_content"})
                print("淘汰: 医疗内容")
                save_progress()
                continue
            anxiety_hits = sum(1 for t in titles
                               if any(h in t for h in BODY_ANXIETY_HINTS))
            if anxiety_hits >= max(3, len(titles) // 2):
                eliminated.append({"creator_id": uid, "nickname": nick,
                                   "reason": "body_anxiety_dominant"})
                print("淘汰: 身材焦虑主导")
                save_progress()
                continue

            # 代表笔记：最新1篇已开 + 再找1篇（优先视频）
            rep = [note_record(latest_media)]
            for n in recent[1:]:
                if len(rep) >= REP_NOTES_PER_CREATOR:
                    break
                if latest["note_id"] == n["note_id"]:
                    continue
                # 优先选视频笔记，若最新已是视频则选不同类型补充
                prefer_video = latest_media.get("type") != "video"
                if prefer_video and n.get("type") != "video":
                    continue
                url = f"https://www.xiaohongshu.com/explore/{n['note_id']}"
                if n.get("xsec_token"):
                    url += f"?xsec_token={n['xsec_token']}&xsec_source=pc_user"
                try:
                    adapter.soft_navigate_to(page, url, n["note_id"])
                    time.sleep(PAGE_INTERVAL_S)
                    media = adapter.extract_note_media(page)
                except CdpUnavailable:
                    continue
                if media:
                    rep.append(note_record(media))
            if len(rep) < REP_NOTES_PER_CREATOR:
                # 无偏好兜底：取下一篇任意类型
                for n in recent[1:]:
                    if len(rep) >= REP_NOTES_PER_CREATOR:
                        break
                    if n["note_id"] == latest["note_id"]:
                        continue
                    url = f"https://www.xiaohongshu.com/explore/{n['note_id']}"
                    if n.get("xsec_token"):
                        url += f"?xsec_token={n['xsec_token']}&xsec_source=pc_user"
                    try:
                        adapter.soft_navigate_to(page, url, n["note_id"])
                        time.sleep(PAGE_INTERVAL_S)
                        media = adapter.extract_note_media(page)
                    except CdpUnavailable:
                        continue
                    if media:
                        rep.append(note_record(media))

            scenes = classify_scenes(titles)
            commercial_n = count_commercial(titles)
            video_count = sum(1 for n in recent if n.get("type") == "video")
            record = {
                "creator_id": uid,
                "nickname": detail.get("nickname") or nick,
                "profile_url": cand["profile_url"],
                "bio": detail.get("desc") or None,
                "followers": detail.get("followers"),
                "following": detail.get("following"),
                "likes_and_collects": detail.get("likes_and_collects"),
                "ip_location": detail.get("ip_location") or None,
                "tags": detail.get("tags") or [],
                "latest_post_time": rep[0]["publish_time"],
                "posts_reviewed_count": len(recent),
                "video_posts_in_recent10": video_count,
                "commercial_posts_count": commercial_n,
                "commercial_post_ratio": round(commercial_n / len(recent), 3),
                "content_categories": scenes,
                "main_scenes": scenes[:3],
                "recent_titles_sample": titles[:5],
                "representative_notes": rep,
                "source_query": cand.get("source_query"),
                "source": "page_observed",
                "audience_inference_source": "ai_inferred",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "human_verified": False,
            }
            deep.append(record)
            save_progress()
            print(f"通过({len(deep)}/{args.target}) 粉={detail.get('followers')} "
                  f"视频{video_count}/10 场景={scenes[:2]}", flush=True)
            if (processed_this_run % BATCH_SIZE == 0
                    and len(deep) < args.target):
                print(f"[PAUSE] 已完成 {processed_this_run} 位，暂停 {BATCH_PAUSE_S:.0f}s",
                      flush=True)
                time.sleep(BATCH_PAUSE_S)

        DEEP_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEEP_PATH.write_text(json.dumps({
            "deep_reviewed": len(deep),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "creators": deep,
        }, ensure_ascii=False, indent=2), "utf-8")
        ELIM_PATH.write_text(json.dumps({
            "eliminated_count": len(eliminated),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "eliminated": eliminated,
        }, ensure_ascii=False, indent=2), "utf-8")
        print(f"\n[OK] 深度核验 {len(deep)} 位，淘汰 {len(eliminated)} 位")
        return 0 if len(deep) >= args.target else 4
    finally:
        adapter.close()


if __name__ == "__main__":
    raise SystemExit(main())
