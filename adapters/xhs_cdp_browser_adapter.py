"""专用 Chrome CDP 只读适配器（Stage 2 D-0009 方向B）。

与 WebBridge 前台借用方案的区别：
- 通过 Playwright connect_over_cdp 连接专用 user-data-dir 的可见 Chrome；
- 按 URL 中的 note_id 选择标签页，不依赖操作系统窗口焦点；
- 专用 Profile 位于项目 tmp/xhs_cdp_profile/，不读默认 Profile、不导出 Cookie；
- evaluate 仅允许本模块内置只读模板；写交互在策略层拒绝。
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml


class CdpPolicyViolation(Exception):
    """违反 CDP 只读策略。"""


class CdpUnavailable(Exception):
    """CDP 端点不可达或页面不可用。"""


class LoginWaitTimeout(Exception):
    """登录等待超时（诚实停止，不绕过）。"""


# ---------- 内置只读 JS 模板（唯一允许执行的脚本） ----------

PAGE_STATE_JS = (
    "(()=>{return JSON.stringify({url:location.href,ready:document.readyState,"
    "title:document.title||''});})()"
)

LOGIN_GATE_JS = (
    "(()=>{const t=document.body?document.body.innerText:'';"
    "const marks=['扫码登录','登录后查看','手机号登录','验证码','安全验证','拖动滑块'];"
    "const hit=marks.filter(m=>t.includes(m));"
    "const modal=!!document.querySelector('.login-container');"
    "const s=window.__INITIAL_STATE__;"
    "let loggedIn=null;try{const rw=o=>o&&o._value!==undefined?o._value:o;"
    "loggedIn=rw(s&&s.user&&s.user.loggedIn);}catch(e){}"
    "return JSON.stringify({gated:modal||hit.length>0||loggedIn===false,"
    "markers:hit,modal:modal,logged_in:loggedIn});})()"
)

# 主页笔记列表（含 xsecToken）：用于在笔记需要分享令牌时构造可访问 URL
PROFILE_NOTES_XSEC_JS = (
    "(()=>{const rw=o=>o&&o._value!==undefined?o._value:o;"
    "const s=window.__INITIAL_STATE__;const ns=rw(s&&s.user&&s.user.notes);"
    "if(!ns)return JSON.stringify([]);const out=[];"
    "ns.flat().forEach(n=>{const item=rw(n)||{};const c=rw(item.noteCard)||{};"
    "out.push({note_id:item.id||c.noteId||'',title:c.displayTitle||c.title||'',"
    "type:c.type||'',xsec_token:item.xsecToken||c.xsecToken||''})});"
    "return JSON.stringify(out);})()"
)

NOTE_MEDIA_JS = (
    "(()=>{const rw=o=>o&&o._value!==undefined?o._value:o;"
    "const s=window.__INITIAL_STATE__;"
    "if(!s||!s.note)return JSON.stringify(null);"
    "const m=rw(s.note.noteDetailMap);if(!m)return JSON.stringify(null);"
    "const k=Object.keys(m)[0];const d=rw(m[k]);const n=rw(d&&d.note)||{};"
    "const user=rw(n.user)||{};const ii=rw(n.interactInfo)||{};"
    "let vdur=null,streams=[],cover='';"
    "try{const v=rw(n.video)||{};const media=rw(v.media)||{};"
    "vdur=media.videoDuration!==undefined?media.videoDuration:(v.duration||null);"
    "const st=rw(media.stream)||{};"
    "const caps=rw(v.image)||[];"
    "if(caps.length){const c0=rw(caps[0])||{};cover=c0.url||c0.urlDefault||'';}"
    "['h264','h265','av1'].forEach(codec=>{const arr=rw(st[codec])||[];"
    "arr.forEach(e=>{const ee=rw(e)||{};"
    "streams.push({codec:codec,quality:ee.qualityType||ee.videoQuality||'',"
    "master_url:ee.masterUrl||'',"
    "backup_urls:(rw(ee.backupUrls)||[]).slice(0,3),"
    "width:ee.width||null,height:ee.height||null,duration:ee.duration||null,"
    "size:ee.size||null,videoBitrate:ee.videoBitrate||null});});});"
    "if(vdur===null||vdur===undefined){"
    "const sd=streams.find(x=>x.duration!==null&&x.duration!==undefined);"
    "if(sd)vdur=sd.duration;}"
    "}catch(e){}"
    "return JSON.stringify({note_id:k,title:n.title||'',desc:(n.desc||'').slice(0,120),"
    "type:n.type||'',nickname:user.nickname||user.nickName||'',"
    "user_id:user.userId||'',time:n.time||null,"
    "official_verify:rw(user.redOfficialVerifyType)!==undefined?rw(user.redOfficialVerifyType):null,"
    "likes:ii.likedCount||'',collects:ii.collectedCount||'',comments:ii.commentCount||'',"
    "video_duration:vdur,cover:cover,streams:streams});})()"
)

# 搜索结果列表：用于代表性样本筛选（只读，含 xsecToken 供构造笔记 URL）
SEARCH_NOTES_JS = (
    "(()=>{const rw=o=>o&&o._value!==undefined?o._value:o;"
    "const s=window.__INITIAL_STATE__;const fs=rw(s&&s.search&&s.search.feeds);"
    "if(!fs)return JSON.stringify([]);const out=[];"
    "fs.flat().forEach(f=>{const item=rw(f)||{};const c=rw(item.noteCard)||{};"
    "const u=rw(c.user)||{};"
    "out.push({note_id:item.id||c.noteId||'',title:c.displayTitle||c.title||'',"
    "type:c.type||'',nickname:u.nickname||u.nickName||'',user_id:u.userId||'',"
    "xsec_token:item.xsecToken||c.xsecToken||''})});"
    "return JSON.stringify(out);})()"
)

# 达人主页详情：bio/粉丝/关注/获赞与收藏/认证信息（只读）
PROFILE_DETAIL_JS = (
    "(()=>{const rw=o=>o&&o._value!==undefined?o._value:o;"
    "const s=window.__INITIAL_STATE__;const us=rw(s&&s.user);"
    "if(!us)return JSON.stringify(null);"
    "const pd=rw(us.userPageData)||{};const bi=rw(pd.basicInfo)||{};"
    "const ui=rw(us.userInfo)||{};"
    "const nick=bi.nickname||ui.nickname||'';"
    "let followers=null,following=null,liked=null;"
    "const ia=rw(pd.interactions)||[];"
    "ia.forEach(x=>{const e=rw(x)||{};const t=e.type||'';const c=e.count||null;"
    "if(t==='fans')followers=c;else if(t==='follow')following=c;"
    "else if(t==='liked')liked=c;});"
    "const tags=(rw(pd.tags)||[]).map(t=>{const e=rw(t)||{};"
    "return e.name||e.tagName||'';}).filter(Boolean);"
    "return JSON.stringify({nickname:nick,"
    "red_id:bi.redId||bi.red_id||'',"
    "desc:bi.desc||'',gender:bi.gender!==undefined?bi.gender:null,"
    "ip_location:bi.ipLocation||'',"
    "official_verify:bi.redOfficialVerifyType!==undefined?bi.redOfficialVerifyType:null,"
    "official_verify_name:bi.redOfficialVerifyName||'',"
    "followers:followers,following:following,likes_and_collects:liked,"
    "tags:tags});})()"
)

_READ_ONLY_TEMPLATES = frozenset(
    {PAGE_STATE_JS, LOGIN_GATE_JS, NOTE_MEDIA_JS, PROFILE_NOTES_XSEC_JS,
     SEARCH_NOTES_JS, PROFILE_DETAIL_JS}
)

# 软导航前缀：等价于用户在地址栏输入 URL（只读跳转），目标 URL 由适配器内部构造
SOFT_NAVIGATE_JS_PREFIX = "location.href = "


# ---------- 纯函数（离线可测） ----------


def validate_debug_address(address: str) -> str:
    """调试地址只允许环回，拒绝 0.0.0.0 / 局域网 / 域名。"""
    if address in {"127.0.0.1", "localhost", "::1"}:
        return address
    raise CdpPolicyViolation(f"CDP 调试地址必须是 127.0.0.1，拒绝: {address}")


DEFAULT_PROFILE_MARKERS = (
    r"Google\Chrome\User Data",
    r"Google/Chrome/User Data",
    "chrome_user_data",
)


def validate_user_data_dir(path: str | Path, project_root: str | Path) -> Path:
    """user-data-dir 必须位于项目 tmp/ 内，禁止默认 Chrome 配置目录。"""
    p = Path(path)
    abs_p = p if p.is_absolute() else (Path(project_root) / p).resolve()
    root = Path(project_root).resolve()
    text = str(abs_p)
    for marker in DEFAULT_PROFILE_MARKERS:
        if marker.lower() in text.lower():
            raise CdpPolicyViolation(f"禁止使用默认 Chrome 配置目录: {abs_p}")
    try:
        abs_p.relative_to(root / "tmp")
    except ValueError as exc:
        raise CdpPolicyViolation(f"user-data-dir 必须在项目 tmp/ 内: {abs_p}") from exc
    return abs_p


def select_note_page(pages: list[Any], note_id: str) -> Optional[Any]:
    """按 URL 中的 note_id 选择标签页（不依赖 OS 窗口焦点）。"""
    for page in pages:
        try:
            if note_id in (page.url or ""):
                return page
        except Exception:  # noqa: BLE001 - 单个页面异常不阻塞枚举
            continue
    return None


def is_login_gate(state: dict) -> bool:
    """根据登录门禁脚本结果判断是否需要人工登录。"""
    return bool(state.get("gated"))


def hash_signed_url(url: str) -> str:
    """签名媒体 URL 的 SHA-256（Git 只存哈希）。"""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def url_domain(url: str) -> str:
    return urllib.parse.urlparse(url).netloc


def url_has_signature(url: str) -> bool:
    """判断 URL 是否带临时签名参数（粗略：含长签名样式查询串）。"""
    query = urllib.parse.urlparse(url).query
    if not query:
        return False
    return any(
        len(v) >= 16 and re.fullmatch(r"[A-Za-z0-9_\-%.=]+", v)
        for pair in query.split("&") for v in [pair.split("=")[-1]]
    )


def is_media_response(content_type: str, resource_type: str, url: str,
                      url_hints: list[str]) -> bool:
    """网络事件筛选：仅媒体类型或视频 CDN 特征。"""
    ct = (content_type or "").lower()
    rt = (resource_type or "").lower()
    u = (url or "").lower()
    if rt == "media":
        return True
    if ct.startswith("video/") or "mpegurl" in ct:
        return True
    return any(h in u for h in url_hints) and ("video" in ct or ".mp4" in u or ".m3u8" in u)


def sanitize_media_record(url: str, source: str, found_at: str) -> dict:
    """Git 侧媒体记录：不含原始签名 URL。"""
    return {
        "url_sha256": hash_signed_url(url),
        "domain": url_domain(url),
        "has_signature": url_has_signature(url),
        "source": source,
        "found_at": found_at,
    }


def is_project_chrome_cmdline(cmdline: str, profile_dir: str | Path) -> bool:
    """判断进程命令行是否属于本项目专用 Chrome（用于限制关闭范围）。"""
    text = cmdline.replace("/", "\\").lower()
    needle = str(profile_dir).replace("/", "\\").lower()
    return "chrome" in text and f"--user-data-dir={needle}" in text


# ---------- 策略 ----------


@dataclass
class XhsCdpReadonlyPolicy:
    debug_address: str
    debug_port: int
    user_data_dir: Path
    headless: bool
    note_id: str
    canonical_url: str
    login_wait_seconds: int
    login_poll_seconds: int
    gate_markers: list[str]
    media_url_hints: list[str]
    output_video: str
    max_duration_drift: float
    raw: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path, project_root: str | Path) -> "XhsCdpReadonlyPolicy":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        cdp = raw["cdp"]
        address = validate_debug_address(cdp["debug_address"])
        profile = validate_user_data_dir(cdp["user_data_dir"], project_root)
        return cls(
            debug_address=address,
            debug_port=int(cdp["debug_port"]),
            user_data_dir=profile,
            headless=bool(cdp.get("headless", False)),
            note_id=raw["target"]["note_id"],
            canonical_url=raw["target"]["canonical_url"],
            login_wait_seconds=int(raw["login"]["wait_seconds"]),
            login_poll_seconds=int(raw["login"]["poll_interval_seconds"]),
            gate_markers=list(raw["login"]["gate_markers"]),
            media_url_hints=list(raw["network_capture"]["media_url_hints"]),
            output_video=raw["download"]["output"],
            max_duration_drift=float(raw["download"]["max_duration_drift_seconds"]),
            raw=raw,
        )

    @property
    def endpoint(self) -> str:
        return f"http://{self.debug_address}:{self.debug_port}"

    def check_eval_template(self, snippet: str) -> None:
        if snippet in _READ_ONLY_TEMPLATES:
            return
        if snippet.startswith(SOFT_NAVIGATE_JS_PREFIX):
            return
        raise CdpPolicyViolation("CDP evaluate 仅允许内置只读模板")


# ---------- 适配器 ----------


class XhsCdpBrowserAdapter:
    """Playwright CDP 只读适配器。所有页面动作经过策略与模板校验。"""

    def __init__(self, policy: XhsCdpReadonlyPolicy, project_root: str | Path):
        self.policy = policy
        self.root = Path(project_root)
        self._playwright = None
        self._browser = None
        self.actions_log: list[str] = []

    # ---- 生命周期 ----

    def chrome_reachable(self) -> bool:
        try:
            with urllib.request.urlopen(
                f"{self.policy.endpoint}/json/version", timeout=5
            ) as resp:
                return resp.status == 200
        except OSError:
            return False

    def connect(self) -> None:
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.connect_over_cdp(self.policy.endpoint)
        except Exception as exc:  # noqa: BLE001
            self.close()
            raise CdpUnavailable(f"CDP 连接失败: {exc}") from exc
        self.actions_log.append("connect_over_cdp")

    def close(self) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
        finally:
            if self._playwright is not None:
                self._playwright.stop()
            self._browser = None
            self._playwright = None

    # ---- 页面枚举与选择 ----

    def contexts(self) -> list[Any]:
        if self._browser is None:
            raise CdpUnavailable("尚未连接 CDP")
        return list(self._browser.contexts)

    def all_pages(self) -> list[Any]:
        pages: list[Any] = []
        for ctx in self.contexts():
            pages.extend(ctx.pages)
        return pages

    def find_note_page(self) -> Any:
        page = select_note_page(self.all_pages(), self.policy.note_id)
        if page is None:
            raise CdpUnavailable(f"未找到 note_id={self.policy.note_id} 的标签页")
        return page

    def soft_navigate_to(self, page: Any, url: str, wait_for: str,
                         max_polls: int = 20) -> Any:
        """在当前标签页内软导航并等待目标 URL 片段出现（不创建新标签页）。"""
        import time

        snippet = f"{SOFT_NAVIGATE_JS_PREFIX}{json.dumps(url)}"
        self.policy.check_eval_template(snippet)
        self.actions_log.append("soft_navigate")
        page.evaluate(snippet)
        for _ in range(max_polls):
            time.sleep(1)
            try:
                state = self.page_state(page)
            except Exception:  # noqa: BLE001 - 导航期间 evaluate 可能瞬时失败
                continue
            if wait_for in str(state.get("url", "")) and state.get("ready") in (
                "interactive", "complete"
            ):
                return page
        raise CdpUnavailable(f"软导航等待超时: {url}")

    def find_or_soft_navigate(self, url: str, max_polls: int = 20) -> Any:
        """找到目标标签页；不存在时在当前唯一页面内软导航到目标 URL。

        不创建新标签页；软导航等价于用户在地址栏输入网址（只读跳转）。
        """
        pages = self.all_pages()
        page = select_note_page(pages, self.policy.note_id)
        if page is not None:
            return page
        if not pages:
            raise CdpUnavailable("专用 Chrome 中没有任何标签页")
        return self.soft_navigate_to(pages[0], url, self.policy.note_id, max_polls)

    # ---- 只读 evaluate（仅内置模板） ----

    def evaluate_readonly(self, page: Any, snippet: str) -> Any:
        self.policy.check_eval_template(snippet)
        self.actions_log.append("evaluate_readonly")
        value = page.evaluate(snippet)
        if isinstance(value, str) and value.startswith(("{", "[")):
            return json.loads(value)
        return value

    def page_state(self, page: Any) -> dict:
        data = self.evaluate_readonly(page, PAGE_STATE_JS)
        return dict(data) if isinstance(data, dict) else {}

    def login_gate_state(self, page: Any) -> dict:
        data = self.evaluate_readonly(page, LOGIN_GATE_JS)
        return dict(data) if isinstance(data, dict) else {"gated": True}

    def extract_note_media(self, page: Any) -> Optional[dict]:
        data = self.evaluate_readonly(page, NOTE_MEDIA_JS)
        return dict(data) if isinstance(data, dict) else None

    def extract_profile_notes_xsec(self, page: Any) -> list[dict]:
        data = self.evaluate_readonly(page, PROFILE_NOTES_XSEC_JS)
        return list(data) if isinstance(data, list) else []

    def extract_search_notes(self, page: Any) -> list[dict]:
        data = self.evaluate_readonly(page, SEARCH_NOTES_JS)
        return list(data) if isinstance(data, list) else []

    def extract_profile_detail(self, page: Any) -> Optional[dict]:
        data = self.evaluate_readonly(page, PROFILE_DETAIL_JS)
        return dict(data) if isinstance(data, dict) else None

    # ---- 登录等待 ----

    def wait_for_login(self, page: Any, reporter=print) -> dict:
        """轮询登录状态；人工登录期间脚本持续运行，超时诚实停止。"""
        deadline = self.policy.login_wait_seconds
        interval = self.policy.login_poll_seconds
        waited = 0
        prompted = False
        while True:
            state = self.login_gate_state(page)
            if not is_login_gate(state):
                reporter(f"[LOGIN] 已登录（logged_in={state.get('logged_in')}）")
                return state
            if waited >= deadline:
                raise LoginWaitTimeout(
                    f"等待人工登录超时（{deadline}s），标记 WAITING_FOR_MANUAL_LOGIN")
            if not prompted:
                reporter("[LOGIN] 请在新打开的专用Chrome窗口完成小红书登录，"
                         "脚本将自动继续，无需返回对话。")
                prompted = True
            import time

            time.sleep(max(interval, 0.1))
            waited += interval
            try:
                page = self.find_note_page()
            except CdpUnavailable:
                pass

    # ---- 媒体下载（经页面所在 context 的请求栈） ----

    def download_via_context(self, page: Any, url: str, out_path: str | Path) -> Path:
        """用页面所属 BrowserContext 的请求能力下载媒体（不导出 Cookie）。"""
        self.actions_log.append("context_request_get")
        response = page.context.request.get(url, timeout=120_000)
        if not response.ok:
            raise CdpUnavailable(f"媒体下载失败 HTTP {response.status}")
        body = response.body()
        if not body:
            raise CdpUnavailable("媒体下载为空")
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(body)
        return out

    # ---- 网络事件（被动监听，仅媒体） ----

    def attach_media_sniffer(self, page: Any, bucket: list[dict]) -> None:
        """被动记录媒体响应元数据；原始签名 URL 不进 bucket。"""
        def on_response(response: Any) -> None:
            try:
                ctype = response.headers.get("content-type", "")
                rtype = response.request.resource_type
                url = response.url
                if is_media_response(ctype, rtype, url, self.policy.media_url_hints):
                    self.actions_log.append("network_media_observed")
                    bucket.append({
                        "url": url,  # 调用方负责只写 tmp/
                        "content_type": ctype,
                        "resource_type": rtype,
                        "status": response.status,
                        "found_at": datetime.now(timezone.utc).isoformat(),
                    })
            except Exception:  # noqa: BLE001 - 单个响应异常不阻塞监听
                return

        page.on("response", on_response)
