"""小红书只读浏览器适配器（kimi-webbridge 版）。

通过本地 WebBridge 守护进程（http://127.0.0.1:10086）控制用户真实浏览器，
复用其登录态，仅执行只读动作：搜索、打开笔记、打开主页、复制 URL、
读取页面文字、截图。

强制约束（config/xhs_readonly_policy.yaml 为唯一权威来源）：
- WebBridge 动作白名单：navigate/find_tab/list_tabs/snapshot/evaluate/screenshot；
  click/fill/upload/cdp 等写能力与逃逸通道在适配器层直接拒绝；
- evaluate 只允许本模块内置的只读提取脚本（EXTRACT_* 常量），不接受外部任意代码；
- 每次页面请求间隔 ≥3 秒，自动重试 ≤1 次；
- 检测到登录墙/验证码特征 → 抛 HumanGateRequired，立即停止，不得绕过；
- 不导出、不读取 Cookie/Session/Token。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

DEFAULT_POLICY_PATH = Path("config/xhs_readonly_policy.yaml")
XHS_BASE = "https://www.xiaohongshu.com"

# ---- 适配器内置只读提取脚本（唯一允许经 evaluate 执行的代码） ----

EXTRACT_SEARCH_CARDS_JS = (
    "(()=>{const out=[];"
    "document.querySelectorAll('section.note-item').forEach(s=>{"
    "const a=s.querySelector('a.cover');"
    "const t=s.querySelector('.title');"
    "const u=s.querySelector('.author .name, .author-wrapper .name');"
    "const ua=s.querySelector('a[href*=\"/user/profile/\"]');"
    "const play=s.querySelector('.play-icon, .video-icon');"
    "if(a){out.push({title:t?t.innerText.trim():'',url:a.href,"
    "author:u?u.innerText.trim():'',author_url:ua?ua.href:'',"
    "is_video:!!play})}});return JSON.stringify(out.slice(0,20));})()"
)

EXTRACT_NOTE_DETAIL_JS = (
    "(()=>{const s=window.__INITIAL_STATE__;const m=s&&s.note&&s.note.noteDetailMap;"
    "if(!m)return JSON.stringify(null);const k=Object.keys(m)[0];const n=m[k].note;"
    "let vurl='';try{const st=n.video.media.stream;const arr=(st.h264||[]).concat(st.h265||[]);"
    "vurl=arr.length?arr[0].masterUrl:'';}catch(e){}"
    "return JSON.stringify({title:n.title||'',desc:n.desc||'',time:n.time||'',"
    "type:n.type||'',likes:n.interactInfo?n.interactInfo.likedCount:'',"
    "collects:n.interactInfo?n.interactInfo.collectedCount:'',"
    "comments:n.interactInfo?n.interactInfo.commentCount:'',"
    "nickname:n.user?n.user.nickname:'',user_id:n.user?n.user.userId:'',"
    "video_url:vurl});})()"
)

EXTRACT_PROFILE_JS = (
    "(()=>{const rw=o=>o&&o._value!==undefined?o._value:o;"
    "const s=window.__INITIAL_STATE__;const upd=rw(s&&s.user&&s.user.userPageData);"
    "if(!upd)return JSON.stringify(null);const b=rw(upd.basicInfo)||{};"
    "const its=upd.interactions||[];"
    "const g=t=>{const f=its.filter(i=>i.type===t)[0];return f?f.count:'';};"
    "return JSON.stringify({nickname:b.nickname||'',desc:b.desc||'',fans:g('fans'),"
    "follows:g('follows'),interaction:g('interaction'),red_id:b.redId||''});})()"
)

HUMAN_GATE_CHECK_JS = (
    "(()=>{const t=document.body?document.body.innerText:'';"
    "const marks=['扫码登录','登录后查看','安全验证','拖动滑块'];"
    "const hit=marks.filter(m=>t.includes(m));"
    "const modal=!!document.querySelector('.login-container');"
    "return JSON.stringify({gated:modal||hit.length>0,markers:hit,modal:modal});})()"
)

# 软导航：守护进程 navigate 等待 load 事件，重页面（搜索/Feed）会 30s 超时；
# 改用 location.href 赋值（等同用户输入网址跳转，对平台为只读），随后轮询就绪。
SOFT_NAVIGATE_JS_PREFIX = "location.href = "
PAGE_STATE_JS = (
    "(()=>{return JSON.stringify({url:location.href,ready:document.readyState,"
    "items:document.querySelectorAll('section.note-item').length,"
    "hasState:!!window.__INITIAL_STATE__});})()"
)

_READ_ONLY_SNIPPETS = {
    EXTRACT_SEARCH_CARDS_JS,
    EXTRACT_NOTE_DETAIL_JS,
    EXTRACT_PROFILE_JS,
    HUMAN_GATE_CHECK_JS,
    PAGE_STATE_JS,
}


class PolicyViolation(Exception):
    """违反只读策略。"""


class HumanGateRequired(Exception):
    """遇到登录墙/验证码，必须人工处理，停止自动化。"""


class BridgeUnavailable(Exception):
    """WebBridge 守护进程不可达。"""


@dataclass
class ReadOnlyPolicy:
    """只读策略：白名单动作 + 范围上限 + 人工门禁。"""

    bridge_allowed: set[str]
    bridge_forbidden: set[str]
    forbidden_behaviors: set[str]
    scope_limits: dict[str, int]
    gate_markers: list[str]
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path = DEFAULT_POLICY_PATH) -> "ReadOnlyPolicy":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        browser = data["browser"]
        gates = browser.get("human_gates", {})
        return cls(
            bridge_allowed=set(browser["bridge_allowed_actions"]),
            bridge_forbidden=set(browser["bridge_forbidden_actions"]),
            forbidden_behaviors=set(browser["forbidden_behaviors"]),
            scope_limits=dict(data["scope_limits"]),
            gate_markers=list(gates.get("gate_markers", [])),
            raw=data,
        )

    def check_bridge_action(self, action: str) -> None:
        if action in self.bridge_forbidden:
            raise PolicyViolation(f"WebBridge 动作被策略禁止: {action}")
        if action not in self.bridge_allowed:
            raise PolicyViolation(f"WebBridge 动作不在白名单: {action}")

    @property
    def min_interval(self) -> int:
        return int(self.scope_limits.get("min_request_interval_seconds", 3))

    @property
    def max_retries(self) -> int:
        return int(self.scope_limits.get("max_retries", 1))


class RateLimiter:
    """页面请求最小间隔控制（可注入时钟便于测试）。"""

    def __init__(
        self,
        min_interval: float,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval = min_interval
        self.clock = clock
        self.sleeper = sleeper
        self._last: Optional[float] = None

    def wait(self) -> None:
        now = self.clock()
        if self._last is not None:
            elapsed = now - self._last
            if elapsed < self.min_interval:
                self.sleeper(self.min_interval - elapsed)
        self._last = self.clock()


class XhsReadOnlyBrowserAdapter:
    """小红书只读浏览器适配器。所有动作经策略校验与限速。"""

    def __init__(
        self,
        policy: ReadOnlyPolicy,
        session: str = "mcn-stage2-poc",
        daemon_url: str = "http://127.0.0.1:10086",
        screenshot_dir: str | Path = "screenshots/stage_2_browser_poc",
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        timeout: float = 30.0,
    ) -> None:
        self.policy = policy
        self.session = session
        self.daemon_url = daemon_url.rstrip("/")
        self.screenshot_dir = Path(screenshot_dir)
        self.timeout = timeout
        self._limiter = RateLimiter(policy.min_interval, clock=clock, sleeper=sleeper)
        self.actions_log: list[str] = []  # 审计：记录实际执行的 WebBridge 动作

    # ---- 底层通信 ----

    def _command(
        self, action: str, args: dict[str, Any], timeout: Optional[float] = None
    ) -> dict[str, Any]:
        self.policy.check_bridge_action(action)
        self.actions_log.append(action)
        payload = json.dumps({"action": action, "args": args, "session": self.session})
        req = urllib.request.Request(
            f"{self.daemon_url}/command",
            data=payload.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise BridgeUnavailable(f"WebBridge 不可达: {exc}") from exc
        if not body.get("ok"):
            raise BridgeUnavailable(f"WebBridge 返回错误: {body}")
        return body.get("data", {})

    def _page_request(
        self, action: str, args: dict[str, Any], timeout: Optional[float] = None
    ) -> dict[str, Any]:
        """带限速与 ≤max_retries 次重试的页面请求。"""
        attempts = 1 + self.policy.max_retries
        last_exc: Optional[Exception] = None
        for _ in range(attempts):
            self._limiter.wait()
            try:
                return self._command(action, args, timeout=timeout)
            except BridgeUnavailable as exc:
                last_exc = exc
        raise last_exc  # type: ignore[misc]

    def _evaluate_readonly(self, snippet: str) -> Any:
        """仅允许内置只读脚本（提取/门禁检测/页面状态/软导航）。"""
        is_soft_nav = snippet.startswith(SOFT_NAVIGATE_JS_PREFIX)
        if snippet not in _READ_ONLY_SNIPPETS and not is_soft_nav:
            raise PolicyViolation("evaluate 仅允许适配器内置只读脚本")
        data = self._page_request("evaluate", {"code": snippet})
        value = data.get("value")
        if isinstance(value, str) and value.startswith(("{", "[")):
            return json.loads(value)
        return value

    # ---- 导航 ----

    def check_daemon(self) -> bool:
        try:
            self._command("list_tabs", {})
            return True
        except BridgeUnavailable:
            return False

    def list_tabs(self) -> list[dict]:
        return list(self._command("list_tabs", {}).get("tabs", []))

    def ensure_session_tab(self, group_title: str = "") -> None:
        """确保会话中有一个标签页（先开轻量页，避免重页面 load 超时）。"""
        if self.list_tabs():
            return
        args: dict[str, Any] = {"url": f"{XHS_BASE}/explore", "newTab": True}
        if group_title:
            args["group_title"] = group_title
        try:
            self._page_request("navigate", args, timeout=60.0)
        except BridgeUnavailable:
            if not self.list_tabs():
                raise

    def soft_navigate(self, url: str, wait_items: bool = False, max_polls: int = 20) -> str:
        """location.href 软导航 + 轮询就绪，规避守护进程 load 超时。

        就绪判定：当前 URL 含目标路径末段 ID（跳转可能改写路径/参数），
        且 readyState 为 interactive/complete（wait_items 时还需卡片渲染）。
        """
        self._evaluate_readonly(f"{SOFT_NAVIGATE_JS_PREFIX}{json.dumps(url)}")
        segments = [s for s in url.split("?")[0].split("/") if s]
        target_id = segments[-1] if segments else ""
        for _ in range(max_polls):
            state = self._evaluate_readonly(PAGE_STATE_JS)
            if not state:
                continue
            current = str(state.get("url", ""))
            if target_id not in current:
                continue  # 页面仍在旧地址，等待跳转生效
            if wait_items and not state.get("items"):
                continue  # 等待搜索结果卡片渲染
            if state.get("ready") in ("interactive", "complete"):
                return current
        raise BridgeUnavailable(f"页面就绪等待超时: {url}")

    def current_url(self) -> str:
        state = self._evaluate_readonly(PAGE_STATE_JS)
        return str(state.get("url", "")) if state else ""

    def check_human_gate(self) -> None:
        """检测登录墙/验证码；命中即停止。"""
        result = self._evaluate_readonly(HUMAN_GATE_CHECK_JS)
        if result and result.get("gated"):
            raise HumanGateRequired(
                f"检测到人工门禁（登录/验证码）：{result.get('markers')}，停止自动化"
            )

    def take_screenshot(self, name: str) -> str:
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.screenshot_dir / name
        data = self._page_request(
            "screenshot", {"format": "png", "path": str(path).replace("\\", "/")}
        )
        return str(data.get("path", str(path)))

    def search_notes(self, keyword: str, max_results: Optional[int] = None) -> list[dict]:
        cap = max_results or self.policy.scope_limits["max_search_results"]
        query = urllib.parse.quote(keyword)
        url = f"{XHS_BASE}/search_result?keyword={query}&source=web_explore_feed"
        self.soft_navigate(url, wait_items=True)
        self.check_human_gate()
        cards = self._evaluate_readonly(EXTRACT_SEARCH_CARDS_JS) or []
        return cards[:cap]

    def open_note(self, url: str) -> dict:
        self.soft_navigate(url)
        self.check_human_gate()
        detail = self._evaluate_readonly(EXTRACT_NOTE_DETAIL_JS)
        if not detail:
            raise BridgeUnavailable(f"笔记数据提取失败: {url}")
        detail["url"] = self.current_url() or url
        return detail

    def open_profile(self, url: str) -> dict:
        self.soft_navigate(url)
        self.check_human_gate()
        profile = self._evaluate_readonly(EXTRACT_PROFILE_JS)
        if not profile:
            raise BridgeUnavailable(f"主页数据提取失败: {url}")
        profile["url"] = self.current_url() or url
        return profile
