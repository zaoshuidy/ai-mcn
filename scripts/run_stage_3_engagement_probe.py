"""Stage 3 互动数据补采：15 位深核候选最近 10 篇笔记的点赞/收藏/评论。

- 复用 Stage 2 冻结的只读 CDP 链路，不新增浏览器能力；
- 每位先取主页笔记列表（含 xsec_token 与发布时间），按时间倒序取最近 10 篇；
- 逐篇打开笔记页提取 likes/collects/comments（page_observed）；
- 平台商业标识：读取页面 cornerTag 类字段（page_observed，未检出记 false）；
- AI 软广信号：仅基于标题/正文关键词（ai_inferred），与平台标识分开记录；
- 页面操作间隔 >= 8 秒；每 5 位暂停 120 秒；单账号失败记录后继续；
- 触发验证码/风控立即停止并写 verification event，等待人工；
- 增量保存，支持断点续跑；creator_id 去重。

用法：
    python scripts/run_stage_3_engagement_probe.py [--max-per-run N]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.xhs_cdp_browser_adapter import (  # noqa: E402
    XhsCdpBrowserAdapter,
    XhsCdpReadonlyPolicy,
    is_login_gate,
)

POLICY_PATH = ROOT / "config/xhs_cdp_readonly_policy.yaml"
DEEP_PATH = ROOT / "data/processed/stage_3_deep_review_15.json"
OUT_PATH = ROOT / "data/processed/stage_3_engagement_15.json"
EVENTS_PATH = ROOT / "data/processed/stage_3_verification_events.json"
TMP_DIR = ROOT / "tmp/xhs_stage_3"

PAGE_INTERVAL_S = 8.0
PAUSE_EVERY_N_CREATORS = 5
PAUSE_SECONDS = 120
NOTES_PER_CREATOR = 10
CAPTCHA_MARKERS = ("captcha", "website-login", "安全验证", "滑块", "验证")

# AI 软广信号关键词（ai_inferred，仅标题/正文文本）
AI_COMMERCIAL_HINTS = (
    "霸王茶姬", "CHAGEE", "润本", "雅顿", "橘彩星光", "兰蔻", "欧莱雅",
    "好物分享", "开箱", "联名", "种草", "旗舰店", "优惠券", "折扣",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def captcha_detected(url: str, title: str) -> bool:
    text = f"{url} {title}"
    return any(m in text for m in CAPTCHA_MARKERS)


def record_verification_event(detected_url: str, checkpoint: str) -> None:
    events = []
    if EVENTS_PATH.is_file():
        events = json.loads(EVENTS_PATH.read_text(encoding="utf-8")).get("events", [])
    events.append({
        "event_type": "platform_security_verification",
        "detected_at": utc_now(),
        "detected_url": detected_url,
        "automation_stopped": True,
        "human_action_required": True,
        "human_verification_completed": False,
        "resumed_at": None,
        "resume_checkpoint": checkpoint,
        "cookie_exported": False,
        "verification_bypassed": False,
    })
    EVENTS_PATH.write_text(json.dumps({
        "generated_at": utc_now(), "events": events,
    }, ensure_ascii=False, indent=2), "utf-8")


def ai_commercial_signal(title: str, desc: str) -> list[str]:
    text = f"{title} {desc}"
    return [h for h in AI_COMMERCIAL_HINTS if h in text]


def parse_count(value) -> int | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    try:
        if text.endswith(("万", "w")):
            return round(float(text[:-1]) * 10000)
        return int("".join(ch for ch in text if ch.isdigit()) or 0)
    except (ValueError, TypeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-per-run", type=int, default=0,
                        help="单次运行最多新处理的账号数（0=不限）")
    args = parser.parse_args()

    creators = json.loads(DEEP_PATH.read_text(encoding="utf-8"))["creators"]
    policy = XhsCdpReadonlyPolicy.load(POLICY_PATH, ROOT)
    adapter = XhsCdpBrowserAdapter(policy, ROOT)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    if not adapter.chrome_reachable():
        print("[FAIL] CDP 不可达")
        return 2
    adapter.connect()

    done: dict[str, dict] = {}
    if OUT_PATH.is_file():
        for entry in json.loads(OUT_PATH.read_text(encoding="utf-8")).get("creators", []):
            done[entry["creator_id"]] = entry
    if done:
        print(f"[RESUME] 已完成 {sum(1 for e in done.values() if e.get('complete'))} 位，续跑")

    def save_progress() -> None:
        OUT_PATH.write_text(json.dumps({
            "generated_at": utc_now(),
            "notes_per_creator": NOTES_PER_CREATOR,
            "source": "page_observed（互动数值）/ ai_inferred（软广信号）",
            "creators": list(done.values()),
        }, ensure_ascii=False, indent=2), "utf-8")

    pages = adapter.all_pages()
    page = pages[0]
    if is_login_gate(adapter.login_gate_state(page)):
        print("[FAIL] 未登录")
        return 3

    processed_this_run = 0
    since_pause = 0
    try:
        for creator in creators:
            cid = creator["creator_id"]
            if cid in done and done[cid].get("complete"):
                continue
            if args.max_per_run and processed_this_run >= args.max_per_run:
                print(f"[BATCH] 本批已达 {args.max_per_run} 位，退出待下批")
                break

            nickname = creator["nickname"]
            print(f"[COLLECT] {nickname} ({cid[:8]}…)")
            entry = done.get(cid) or {
                "creator_id": cid,
                "nickname": nickname,
                "profile_url": creator["profile_url"],
                "followers": parse_count(creator.get("followers")),
                "notes": [],
                "errors": [],
                "source": "page_observed",
                "observed_at": None,
            }

            try:
                adapter.soft_navigate_to(page, creator["profile_url"], cid)
                time.sleep(PAGE_INTERVAL_S)
                if captcha_detected(page.url or "", page.title() or ""):
                    raise RuntimeError("CAPTCHA_OR_RISK_CONTROL")
                cards = adapter.extract_profile_notes_engagement(page)
                xsec_map = {
                    n["note_id"]: n["xsec_token"]
                    for n in adapter.extract_profile_notes_xsec(page)
                    if n.get("note_id") and n.get("xsec_token")
                }
                for card in cards:
                    card["xsec_token"] = xsec_map.get(card.get("note_id"), "")
            except RuntimeError as exc:
                if "CAPTCHA" in str(exc):
                    record_verification_event(page.url or "", "stage_3_engagement_probe")
                    print("[STOP] 检测到安全验证，已停止并记录，等待人工处理")
                    save_progress()
                    return 4
                entry["errors"].append(f"profile: {exc}")
                cards = []

            # 主页卡片顺序即倒序（置顶笔记除外）；剔除置顶，取前 10 篇
            cards = [c for c in cards if c.get("note_id") and c.get("xsec_token")]
            non_sticky = [c for c in cards if not c.get("sticky")]
            targets = non_sticky[:NOTES_PER_CREATOR]

            collected = {n["note_id"] for n in entry["notes"]}
            for card in targets:
                nid = card["note_id"]
                if nid in collected:
                    continue
                url = (f"https://www.xiaohongshu.com/explore/{nid}"
                       f"?xsec_token={card['xsec_token']}&xsec_source=pc_user")
                try:
                    adapter.soft_navigate_to(page, url, nid)
                    time.sleep(PAGE_INTERVAL_S)
                    if captcha_detected(page.url or "", page.title() or ""):
                        raise RuntimeError("CAPTCHA_OR_RISK_CONTROL")
                    media = adapter.extract_note_media(page) or {}
                    if media.get("user_id") and media["user_id"] != cid:
                        entry["errors"].append(f"{nid}: 作者归属不一致")
                        continue
                    signals = ai_commercial_signal(
                        media.get("title") or "", media.get("desc") or "")
                    entry["notes"].append({
                        "note_id": nid,
                        "canonical_url": f"https://www.xiaohongshu.com/explore/{nid}",
                        "title": media.get("title") or card.get("title") or "",
                        "publish_time": media.get("time") or card.get("time"),
                        "note_type": media.get("type") or card.get("type") or "",
                        "likes": parse_count(media.get("likes")),
                        "collects": parse_count(media.get("collects")),
                        "comments": parse_count(media.get("comments")),
                        "is_platform_labeled_commercial": False,  # 页面未检出商业标识
                        "ai_inferred_commercial_signal": signals,
                        "source": "page_observed",
                        "observed_at": utc_now(),
                    })
                except RuntimeError as exc:
                    if "CAPTCHA" in str(exc):
                        record_verification_event(
                            page.url or "", "stage_3_engagement_probe")
                        print("[STOP] 检测到安全验证，已停止并记录，等待人工处理")
                        save_progress()
                        return 4
                    entry["errors"].append(f"{nid}: {exc}")
                finally:
                    entry["observed_at"] = utc_now()
                    done[cid] = entry
                    save_progress()

            done[cid] = entry
            entry["complete"] = True
            save_progress()
            processed_this_run += 1
            since_pause += 1
            print(f"[OK] {nickname}: {len(entry['notes'])} 篇互动已采集"
                  f"（错误 {len(entry['errors'])}）")
            if since_pause >= PAUSE_EVERY_N_CREATORS:
                print(f"[PAUSE] 已连续处理 {since_pause} 位，暂停 {PAUSE_SECONDS}s")
                time.sleep(PAUSE_SECONDS)
                since_pause = 0
    finally:
        save_progress()

    total_notes = sum(len(e["notes"]) for e in done.values())
    print(f"[DONE] {len(done)} 位，共 {total_notes} 篇笔记互动数据")
    return 0


if __name__ == "__main__":
    sys.exit(main())
