"""只读策略与浏览器适配器测试。全部离线，不连接真实浏览器。"""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.xhs_browser_adapter import (
    EXTRACT_NOTE_DETAIL_JS,
    HUMAN_GATE_CHECK_JS,
    HumanGateRequired,
    PolicyViolation,
    RateLimiter,
    ReadOnlyPolicy,
    XhsReadOnlyBrowserAdapter,
)

ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "config/xhs_readonly_policy.yaml"


@pytest.fixture(scope="module")
def policy() -> ReadOnlyPolicy:
    return ReadOnlyPolicy.load(POLICY_PATH)


def make_adapter(policy: ReadOnlyPolicy) -> XhsReadOnlyBrowserAdapter:
    return XhsReadOnlyBrowserAdapter(policy=policy, clock=lambda: 0.0, sleeper=lambda s: None)


# ---------- 策略加载与白名单 ----------


def test_policy_loads(policy: ReadOnlyPolicy) -> None:
    assert policy.min_interval == 3
    assert policy.max_retries == 1


def test_scope_limits(policy: ReadOnlyPolicy) -> None:
    limits = policy.scope_limits
    assert limits["max_keywords"] == 1
    assert limits["max_search_results"] == 5
    assert limits["max_creator_profiles"] == 2
    assert limits["max_notes_detail"] == 1
    assert limits["max_videos"] == 1


def test_allowed_bridge_actions_pass(policy: ReadOnlyPolicy) -> None:
    for action in ["navigate", "snapshot", "screenshot", "evaluate", "find_tab", "list_tabs"]:
        policy.check_bridge_action(action)


@pytest.mark.parametrize("action", ["click", "fill", "upload", "cdp", "network",
                                    "save_as_pdf", "close_tab", "close_session"])
def test_forbidden_bridge_actions_rejected(policy: ReadOnlyPolicy, action: str) -> None:
    with pytest.raises(PolicyViolation):
        policy.check_bridge_action(action)


def test_unlisted_action_rejected(policy: ReadOnlyPolicy) -> None:
    """未列明即禁止（白名单语义）。"""
    with pytest.raises(PolicyViolation):
        policy.check_bridge_action("execute_script_arbitrary")


def test_write_behaviors_in_forbidden_list(policy: ReadOnlyPolicy) -> None:
    for behavior in ["like", "collect", "comment", "follow", "dm", "publish",
                     "bypass_captcha", "infinite_scroll"]:
        assert behavior in policy.forbidden_behaviors


def test_cookie_export_forbidden(policy: ReadOnlyPolicy) -> None:
    assert policy.raw["browser"]["cookie_export"] == "forbidden"
    assert policy.raw["browser"]["credential_read"] == "forbidden"


# ---------- 适配器表面：无写操作方法 ----------


def test_adapter_has_no_write_methods(policy: ReadOnlyPolicy) -> None:
    adapter = make_adapter(policy)
    for name in ["click", "fill", "upload", "like", "collect", "comment",
                 "follow", "dm", "publish", "cdp"]:
        assert not hasattr(adapter, name), f"适配器不应提供 {name}"


def test_adapter_rejects_arbitrary_evaluate(policy: ReadOnlyPolicy) -> None:
    adapter = make_adapter(policy)
    with pytest.raises(PolicyViolation):
        adapter._evaluate_readonly("document.querySelector('.like').click()")


def test_adapter_command_logs_actions(policy: ReadOnlyPolicy, monkeypatch) -> None:
    """所有经适配器的动作必须进审计日志（无写操作）。"""
    adapter = make_adapter(policy)

    class FakeResponse:
        def read(self):
            return b'{"ok":true,"data":{"success":true,"tabs":[]}}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse())
    assert adapter.check_daemon() is True
    assert "list_tabs" in adapter.actions_log
    assert not set(adapter.actions_log) & {"click", "fill", "cdp", "upload"}


def test_forbidden_action_never_reaches_network(policy: ReadOnlyPolicy) -> None:
    adapter = make_adapter(policy)
    with pytest.raises(PolicyViolation):
        adapter._command("click", {"selector": "@e1"})
    with pytest.raises(PolicyViolation):
        adapter._command("cdp", {"method": "Input.dispatchMouseEvent"})


# ---------- 限速与重试 ----------


def test_rate_limiter_sleeps_when_fast() -> None:
    now = [0.0]
    slept: list[float] = []
    limiter = RateLimiter(3.0, clock=lambda: now[0], sleeper=slept.append)
    limiter.wait()
    now[0] = 1.0
    limiter.wait()
    assert slept == [2.0]


def test_rate_limiter_no_sleep_after_interval() -> None:
    now = [0.0]
    slept: list[float] = []
    limiter = RateLimiter(3.0, clock=lambda: now[0], sleeper=slept.append)
    limiter.wait()
    now[0] = 5.0
    limiter.wait()
    assert slept == []


# ---------- 人工门禁 ----------


def test_human_gate_detection(policy: ReadOnlyPolicy, monkeypatch) -> None:
    adapter = make_adapter(policy)
    monkeypatch.setattr(adapter, "_evaluate_readonly",
                        lambda s: {"gated": True, "markers": ["扫码登录"]})
    with pytest.raises(HumanGateRequired):
        adapter.check_human_gate()


def test_human_gate_pass_when_clean(policy: ReadOnlyPolicy, monkeypatch) -> None:
    adapter = make_adapter(policy)
    monkeypatch.setattr(adapter, "_evaluate_readonly",
                        lambda s: {"gated": False, "markers": []})
    adapter.check_human_gate()


def test_gate_markers_configured(policy: ReadOnlyPolicy) -> None:
    assert "扫码登录" in policy.gate_markers
    assert "安全验证" in policy.gate_markers


def test_readonly_snippets_are_constants() -> None:
    """内置提取脚本为模块常量，不接受外部注入。"""
    assert "__INITIAL_STATE__" in EXTRACT_NOTE_DETAIL_JS
    assert "innerText" in HUMAN_GATE_CHECK_JS


# ---------- gitignore 覆盖 ----------


def test_gitignore_covers_login_state() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in ["cookies.json", "storage_state.json", ".env", "tmp/"]:
        assert pattern in gitignore
