"""Stage 2 只读浏览器 POC 执行脚本。

范围（config/xhs_readonly_policy.yaml）：1 个关键词、≤5 条搜索结果、
≤2 位达人主页、≤1 篇笔记详情；每次页面请求 ≥3 秒；重试 ≤1 次。

人工前置条件：
1. WebBridge 守护进程在线（kimi-webbridge start）且浏览器扩展已连接；
2. 用户已在浏览器中登录小红书；
3. 出现登录/验证码时脚本会立即停止，由人工处理后可重跑。

退出码：0=成功；2=守护进程不可达；3=人工门禁；4=数据提取失败。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.xhs_browser_adapter import (  # noqa: E402
    BridgeUnavailable,
    HumanGateRequired,
    ReadOnlyPolicy,
    XhsReadOnlyBrowserAdapter,
)

OUT_JSON = ROOT / "data/processed/xhs_browser_poc.json"


def main() -> int:
    policy = ReadOnlyPolicy.load(ROOT / "config/xhs_readonly_policy.yaml")
    plan = json.loads((ROOT / "data/processed/creator_search_plan.json").read_text("utf-8"))
    keyword = plan["poc_queries"][0]["query"]
    limits = policy.scope_limits
    print(f"[POC] 关键词={keyword}；上限：结果≤{limits['max_search_results']}、"
          f"主页≤{limits['max_creator_profiles']}、笔记≤{limits['max_notes_detail']}")

    adapter = XhsReadOnlyBrowserAdapter(
        policy=policy,
        session=policy.raw["browser"]["session"],
        daemon_url=policy.raw["browser"]["daemon_url"],
        screenshot_dir=ROOT / policy.raw["outputs"]["screenshots"],
    )
    if not adapter.check_daemon():
        print("[BLOCKED] WebBridge 守护进程不可达：请运行 kimi-webbridge start 后重试")
        return 2
    adapter.ensure_session_tab(group_title="MCN Stage2 只读POC")

    result: dict = {"keyword": keyword, "policy": limits, "search_results": [],
                    "profiles": [], "note": None, "screenshots": [], "errors": []}
    try:
        cards = adapter.search_notes(keyword)
        result["search_results"] = cards
        result["screenshots"].append(adapter.take_screenshot("01_search.png"))
        print(f"[POC] 搜索结果 {len(cards)} 条")

        for card in cards[: limits["max_creator_profiles"]]:
            if not card.get("author_url"):
                continue
            profile = adapter.open_profile(card["author_url"])
            result["profiles"].append(profile)
            result["screenshots"].append(
                adapter.take_screenshot(f"02_profile_{len(result['profiles'])}.png")
            )
            print(f"[POC] 主页 {profile.get('nickname')} fans={profile.get('fans')}")

        video_cards = [c for c in cards if c.get("is_video")]
        target = (video_cards or cards)[0] if cards else None
        if target:
            note = adapter.open_note(target["url"])
            result["note"] = note
            result["screenshots"].append(adapter.take_screenshot("03_note.png"))
            print(f"[POC] 笔记《{note.get('title', '')[:20]}》 "
                  f"赞={note.get('likes')} 藏={note.get('collects')} 评={note.get('comments')}")
    except HumanGateRequired as exc:
        result["errors"].append(f"human_gate: {exc}")
        print(f"[GATE] {exc} —— 停止自动化，由人工处理")
        _save(result)
        return 3
    except BridgeUnavailable as exc:
        result["errors"].append(f"extract_failed: {exc}")
        print(f"[FAIL] {exc}")
        _save(result)
        return 4

    result["actions_log"] = adapter.actions_log
    _save(result)
    print(f"[POC] 完成，元数据已保存：{OUT_JSON}")
    print(f"[AUDIT] 执行的 WebBridge 动作序列：{sorted(set(adapter.actions_log))}")
    return 0


def _rel(path_str: str) -> str:
    """截图证据路径统一存相对路径（公共产物不得含本地绝对路径）。"""
    try:
        return str(Path(path_str).resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return path_str


def _save(result: dict) -> None:
    result["screenshots"] = [_rel(p) for p in result.get("screenshots", [])]
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
