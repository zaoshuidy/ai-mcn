"""专用 Chrome CDP 只读适配器测试。全部离线，不连接真实浏览器。"""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.xhs_cdp_browser_adapter import (
    CdpPolicyViolation,
    CdpUnavailable,
    LoginWaitTimeout,
    XhsCdpBrowserAdapter,
    XhsCdpReadonlyPolicy,
    hash_signed_url,
    is_login_gate,
    is_media_response,
    is_project_chrome_cmdline,
    sanitize_media_record,
    select_note_page,
    url_domain,
    url_has_signature,
    validate_debug_address,
    validate_user_data_dir,
)

ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "config/xhs_cdp_readonly_policy.yaml"


@pytest.fixture(scope="module")
def policy() -> XhsCdpReadonlyPolicy:
    return XhsCdpReadonlyPolicy.load(POLICY_PATH, ROOT)


class FakePage:
    def __init__(self, url: str):
        self.url = url


# ---------- 1. 调试地址只能是 127.0.0.1 ----------


def test_debug_address_localhost_allowed() -> None:
    assert validate_debug_address("127.0.0.1") == "127.0.0.1"
    assert validate_debug_address("localhost") == "localhost"


@pytest.mark.parametrize("addr", ["0.0.0.0", "192.168.1.10", "10.0.0.2", "example.com", ""])
def test_debug_address_rejects_non_loopback(addr: str) -> None:
    with pytest.raises(CdpPolicyViolation):
        validate_debug_address(addr)


def test_policy_endpoint_is_loopback(policy: XhsCdpReadonlyPolicy) -> None:
    assert policy.endpoint.startswith("http://127.0.0.1:")
    assert "0.0.0.0" not in policy.endpoint


# ---------- 2. 禁止使用默认 Chrome User Data 目录 ----------


def test_default_profile_rejected() -> None:
    with pytest.raises(CdpPolicyViolation):
        validate_user_data_dir(r"C:\Users\yang\AppData\Local\Google\Chrome\User Data", ROOT)


def test_profile_outside_tmp_rejected() -> None:
    with pytest.raises(CdpPolicyViolation):
        validate_user_data_dir(ROOT / "data" / "chrome_profile", ROOT)


def test_project_tmp_profile_accepted(policy: XhsCdpReadonlyPolicy) -> None:
    assert "tmp" in str(policy.user_data_dir)
    assert "xhs_cdp_profile" in str(policy.user_data_dir)


# ---------- 3. 专用 Profile 已被 gitignore ----------


def test_cdp_profile_gitignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "tmp/" in gitignore
    assert "tmp/xhs_cdp_profile/" in gitignore


# ---------- 4. CDP 按 URL 选择标签页，不依赖 foreground ----------


def test_select_note_page_by_url() -> None:
    pages = [FakePage("https://www.xiaohongshu.com/explore/aaaa"),
             FakePage("https://www.xiaohongshu.com/explore/6a4903ad000000002003b221?t=1")]
    found = select_note_page(pages, "6a4903ad000000002003b221")
    assert found is pages[1]


def test_select_note_page_returns_none_when_missing() -> None:
    pages = [FakePage("https://www.xiaohongshu.com/explore/aaaa")]
    assert select_note_page(pages, "6a4903ad000000002003b221") is None


# ---------- 5/6. 登录等待：成功自动继续 / 超时诚实停止 ----------


class FakeAdapterPage:
    def __init__(self, url: str):
        self.url = url


def make_adapter(policy: XhsCdpReadonlyPolicy) -> XhsCdpBrowserAdapter:
    return XhsCdpBrowserAdapter(policy=policy, project_root=ROOT)


def test_wait_for_login_success_continues(policy: XhsCdpReadonlyPolicy) -> None:
    adapter = make_adapter(policy)
    policy.login_wait_seconds = 1
    policy.login_poll_seconds = 0
    adapter.login_gate_state = lambda page: {"gated": False, "guest": False}  # type: ignore[method-assign]
    state = adapter.wait_for_login(FakeAdapterPage("https://x"), reporter=lambda m: None)
    assert state["gated"] is False


def test_wait_for_login_timeout_honest_stop(policy: XhsCdpReadonlyPolicy) -> None:
    adapter = make_adapter(policy)
    policy.login_wait_seconds = 0
    policy.login_poll_seconds = 0
    adapter.login_gate_state = lambda page: {"gated": True, "markers": ["扫码登录"]}  # type: ignore[method-assign]
    adapter.find_note_page = lambda: FakeAdapterPage("https://x")  # type: ignore[method-assign]
    with pytest.raises(LoginWaitTimeout, match="WAITING_FOR_MANUAL_LOGIN"):
        adapter.wait_for_login(FakeAdapterPage("https://x"), reporter=lambda m: None)


def test_login_gate_detection() -> None:
    assert is_login_gate({"gated": True}) is True
    assert is_login_gate({"gated": False, "guest": False}) is False


# ---------- 7. 不读取 Cookie 和 storage ----------


def test_adapter_has_no_credential_methods(policy: XhsCdpReadonlyPolicy) -> None:
    adapter = make_adapter(policy)
    for name in ["cookies", "storage_state", "local_storage", "session_storage"]:
        assert not hasattr(adapter, name), f"适配器不应提供 {name}"


def test_policy_forbids_credential_export(policy: XhsCdpReadonlyPolicy) -> None:
    forbidden = policy.raw["readonly"]["forbidden_actions"]
    for item in ["cookie_export", "storage_read", "auto_login", "fill_credential"]:
        assert item in forbidden


def test_eval_templates_only(policy: XhsCdpReadonlyPolicy) -> None:
    adapter = make_adapter(policy)
    with pytest.raises(CdpPolicyViolation):
        adapter.evaluate_readonly(FakeAdapterPage("https://x"),
                                  "document.cookie")


# ---------- 8. 网络事件只筛选 Media ----------


def test_media_response_filter() -> None:
    assert is_media_response("video/mp4", "media", "https://cdn/x.mp4", ["mp4"])
    assert is_media_response("application/vnd.apple.mpegurl", "", "https://cdn/x.m3u8", [])
    assert not is_media_response("text/html", "document", "https://x.com/page", ["mp4"])
    assert not is_media_response("image/jpeg", "image", "https://cdn/x.jpg", ["mp4"])
    assert is_media_response("", "media", "https://sns-video.xhscdn.com/v", ["xhscdn"])


# ---------- 9. 媒体签名 URL 不得提交 ----------


def test_sanitize_media_record_has_no_raw_url() -> None:
    url = "https://sns-video-qc.xhscdn.com/stream/abc.mp4?sign=ABCDEFGHIJKLMNOP0123456789&t=1"
    record = sanitize_media_record(url, "page_state", "2026-07-18T00:00:00Z")
    assert "url" not in record
    assert url not in str(record)
    assert record["url_sha256"] == hash_signed_url(url)
    assert record["domain"] == url_domain(url)
    assert record["has_signature"] is True


def test_url_has_signature_detection() -> None:
    assert url_has_signature("https://cdn/x.mp4?sign=ABCDEFGHIJKLMNOP012345") is True
    assert url_has_signature("https://cdn/x.mp4") is False


# ---------- 10. 不会关闭用户日常 Chrome ----------


def test_is_project_chrome_cmdline_scoped(policy: XhsCdpReadonlyPolicy) -> None:
    ours = (
        r'"C:\Program Files\Google\Chrome\Application\chrome.exe" '
        rf'--user-data-dir={policy.user_data_dir} --remote-debugging-port=9222'
    )
    daily = r'"C:\Program Files\Google\Chrome\Application\chrome.exe" --profile-directory=Default'
    assert is_project_chrome_cmdline(ours, policy.user_data_dir) is True
    assert is_project_chrome_cmdline(daily, policy.user_data_dir) is False


def test_policy_forbids_closing_user_chrome(policy: XhsCdpReadonlyPolicy) -> None:
    assert "close_user_chrome" in policy.raw["readonly"]["forbidden_actions"]


# ---------- 11. 原始视频与转写不得提交 Git ----------


def test_tmp_artifacts_gitignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "tmp/" in gitignore  # source_video/audio/transcript/keyframes 均在 tmp/ 下


def test_no_cdp_adapter_write_actions(policy: XhsCdpReadonlyPolicy) -> None:
    adapter = make_adapter(policy)
    for name in ["click", "fill", "press", "type", "like", "collect", "comment",
                 "follow", "dm", "publish"]:
        assert not hasattr(adapter, name), f"适配器不应提供 {name}"


# ---------- 策略加载完整性 ----------


def test_policy_loads_target(policy: XhsCdpReadonlyPolicy) -> None:
    assert policy.note_id == "6a4903ad000000002003b221"
    assert policy.canonical_url.endswith(policy.note_id)
    assert policy.raw["target"]["usage_scope"] == "technical_poc_only"
    assert policy.raw["target"]["selection_status"] == "excluded_from_creator_selection"
    assert policy.headless is False


def test_find_note_page_requires_connection(policy: XhsCdpReadonlyPolicy) -> None:
    adapter = make_adapter(policy)
    with pytest.raises(CdpUnavailable):
        adapter.contexts()
