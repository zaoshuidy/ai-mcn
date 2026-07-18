"""从已采集的真实达人主页中寻找一条真实视频笔记（Stage 2 真实视频 POC）。

范围：已采集的 5 位达人主页，最多检查 10 条笔记；
优先生活Vlog/早餐Vlog/一人食视频；只读，复用会话标签页。
输出：data/processed/xhs_video_candidate.json（canonical URL 不含 xsec_token）
      tmp/xhs_video_poc/source_url.txt（页面观察到的视频流地址，不提交 Git）
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.xhs_browser_adapter import (  # noqa: E402
    BridgeUnavailable,
    HumanGateRequired,
    ReadOnlyPolicy,
    XhsReadOnlyBrowserAdapter,
)

MAX_NOTES = 10
VLOG_HINTS = ["vlog", "Vlog", "早餐", "一人食", "日常", "吃什么"]
CANDIDATE_JSON = ROOT / "data/processed/xhs_video_candidate.json"
TMP_DIR = ROOT / "tmp/xhs_video_poc"


def canonical_url(note_id: str) -> str:
    """canonical URL 只保留 https://www.xiaohongshu.com/explore/{note_id}。"""
    clean = "".join(c for c in note_id if c.isalnum())
    if not clean:
        raise ValueError(f"非法 note_id: {note_id!r}")
    return f"https://www.xiaohongshu.com/explore/{clean}"


def main() -> int:
    policy = ReadOnlyPolicy.load(ROOT / "config/xhs_readonly_policy.yaml")
    adapter = XhsReadOnlyBrowserAdapter(policy=policy, session=policy.raw["browser"]["session"])
    if not adapter.check_daemon():
        print("[BLOCKED] WebBridge 不可达")
        return 2
    adapter.ensure_session_tab()

    poc = json.loads((ROOT / "data/processed/xhs_browser_poc.json").read_text("utf-8"))
    profiles = [c["author_url"] for c in poc["search_results"] if c.get("author_url")]
    checked = 0
    try:
        for profile_url in profiles:
            if checked >= MAX_NOTES:
                break
            notes = adapter.open_profile_notes_soft(profile_url)
            videos = [n for n in notes if n.get("type") == "video"]
            videos.sort(key=lambda n: any(h in n.get("title", "") for h in VLOG_HINTS),
                        reverse=True)
            for note in videos:
                if checked >= MAX_NOTES:
                    break
                checked += 1
                nid = note.get("note_id", "")
                if not nid:
                    continue
                detail = adapter.open_note_soft(canonical_url(nid))
                if detail.get("type") == "video" and detail.get("video_url"):
                    candidate = {
                        "note_id": nid,
                        "canonical_url": canonical_url(nid),
                        "creator_name": detail.get("nickname", ""),
                        "creator_profile_url": profile_url.split("?")[0],
                        "title": detail.get("title", ""),
                        "note_type": "video",
                        "duration_seconds": None,
                        "observed_at": datetime.now(timezone.utc).isoformat(),
                        "source": "page_observed",
                        "human_verified": False,
                        "likes": detail.get("likes", ""),
                    }
                    CANDIDATE_JSON.write_text(
                        json.dumps(candidate, ensure_ascii=False, indent=2), "utf-8")
                    TMP_DIR.mkdir(parents=True, exist_ok=True)
                    (TMP_DIR / "source_url.txt").write_text(detail["video_url"], "utf-8")
                    print(f"[FOUND] {candidate['creator_name']}《{candidate['title']}》 {nid}")
                    print(f"[URL] {candidate['canonical_url']}")
                    return 0
    except HumanGateRequired as exc:
        print(f"[GATE] {exc}")
        return 3
    except BridgeUnavailable as exc:
        print(f"[FAIL] {exc}")
        return 4
    print(f"[NONE] 检查 {checked} 条笔记后未找到可用视频笔记")
    return 5


if __name__ == "__main__":
    sys.exit(main())
