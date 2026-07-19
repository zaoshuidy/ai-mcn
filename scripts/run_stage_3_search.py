"""Stage 3 达人搜索采集：8 个关键词真实搜索，建立 ≥20 位原始候选池。

复用冻结的专用 Chrome CDP 只读会话（不新增浏览器能力）。
每个关键词查看前 10—20 条结果，按真实 user_id 去重，记录完整搜索日志。

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
    XhsCdpBrowserAdapter,
    XhsCdpReadonlyPolicy,
    is_login_gate,
)

POLICY_PATH = ROOT / "config/xhs_cdp_readonly_policy.yaml"
SEARCH_LOG_PATH = ROOT / "data/raw/stage_3_search_log.json"
POOL_PATH = ROOT / "data/processed/stage_3_creator_pool.json"
TMP_DIR = ROOT / "tmp/xhs_stage_3"

QUERIES = [
    "独居女生早餐vlog",
    "通勤女生早餐vlog",
    "上班族女生晨间vlog",
    "沉浸式一人食vlog",
    "办公室下午茶vlog",
    "健身女生运动后加餐vlog",
    "酸奶碗女生日常",
    "都市女生生活vlog",
]

RESULTS_PER_QUERY = 20
TARGET_POOL_SIZE = 26  # 目标 ≥20，预留淘汰余量
PAGE_INTERVAL_S = 3.0


def main() -> int:
    policy = XhsCdpReadonlyPolicy.load(POLICY_PATH, ROOT)
    adapter = XhsCdpBrowserAdapter(policy, ROOT)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    if not adapter.chrome_reachable():
        print("[FAIL] CDP 端点不可达")
        return 2
    adapter.connect()
    try:
        pages = adapter.all_pages()
        page = pages[0]
        gate = adapter.login_gate_state(page)
        if is_login_gate(gate):
            print("[FAIL] 未登录，请人工登录后重跑")
            return 3
        print(f"[LOGIN] logged_in={gate.get('logged_in')}")

        pool: dict[str, dict] = {}  # user_id -> candidate
        search_log: list[dict] = []

        for query in QUERIES:
            search_url = (
                "https://www.xiaohongshu.com/search_result?keyword="
                + urllib.parse.quote(query)
                + "&source=web_explore_feed"
            )
            started = datetime.now(timezone.utc).isoformat()
            adapter.soft_navigate_to(page, search_url, "search_result")
            time.sleep(PAGE_INTERVAL_S)

            notes: list[dict] = []
            for _ in range(6):
                notes = adapter.extract_search_notes(page)
                if notes:
                    break
                time.sleep(2)

            viewed = notes[:RESULTS_PER_QUERY]
            new_creators = 0
            skipped_dup = 0
            for n in viewed:
                uid = n.get("user_id")
                if not uid:
                    continue
                if uid in pool:
                    skipped_dup += 1
                    continue
                pool[uid] = {
                    "creator_id": uid,
                    "nickname": n.get("nickname"),
                    "profile_url": f"https://www.xiaohongshu.com/user/profile/{uid}",
                    "source_query": query,
                    "first_note": {
                        "note_id": n.get("note_id"),
                        "title": n.get("title"),
                        "note_type": n.get("type"),
                    },
                    "source": "page_observed",
                    "human_verified": False,
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                }
                new_creators += 1
            # 池可超过 TARGET_POOL_SIZE（淘汰余量），8 词全部执行保证召回多样性

            entry = {
                "query": query,
                "searched_at": started,
                "results_returned": len(notes),
                "results_checked": len(viewed),
                "new_creators": new_creators,
                "skipped_duplicate_user_id": skipped_dup,
                "pool_size_after": len(pool),
            }
            search_log.append(entry)
            print(f"[SEARCH] {query}: 返回{len(notes)} 新增{new_creators} "
                  f"重复{skipped_dup} 池={len(pool)}")

        SEARCH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        SEARCH_LOG_PATH.write_text(json.dumps({
            "stage": "stage_3",
            "queries_executed": len(search_log),
            "log": search_log,
            "notes": "每词查看前10—20条；user_id去重；不含xsec_token",
        }, ensure_ascii=False, indent=2), "utf-8")

        pool_list = list(pool.values())
        POOL_PATH.parent.mkdir(parents=True, exist_ok=True)
        POOL_PATH.write_text(json.dumps({
            "pool_size": len(pool_list),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "candidates": pool_list,
        }, ensure_ascii=False, indent=2), "utf-8")
        print(f"[OK] 原始候选池 {len(pool_list)} 位 -> {POOL_PATH}")
        return 0 if len(pool_list) >= 20 else 4
    finally:
        adapter.close()


if __name__ == "__main__":
    raise SystemExit(main())
