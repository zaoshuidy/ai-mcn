"""Stage 2 专用 Chrome CDP 视频 POC 主脚本（D-0009）。

流程：启动/复用专用 Chrome（tmp/xhs_cdp_profile，127.0.0.1:9222）
→ CDP 连接 → 按 note_id 选页（不依赖 OS 焦点）→ 人工登录等待（≤600s）
→ 页面状态媒体提取 + 被动网络监听 → context 请求栈下载真实视频
→ ffmpeg -i 校验 + SHA-256 → 输出文件清单。

用法：
  python scripts/run_xhs_cdp_video_poc.py --wait-for-login 600

只读：不点赞/收藏/评论/关注/私信/发布，不导出 Cookie，不绕过验证码。
原始签名媒体 URL 只写 tmp/；Git 产物只存哈希/域名/类型/时间。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.xhs_cdp_browser_adapter import (  # noqa: E402
    CdpUnavailable,
    LoginWaitTimeout,
    XhsCdpBrowserAdapter,
    XhsCdpReadonlyPolicy,
    sanitize_media_record,
)
from src.video_analyzer import probe_video_metadata, sha256_file  # noqa: E402

TMP_DIR = ROOT / "tmp/xhs_video_poc"
SESSION_EVIDENCE = ROOT / "data/processed/xhs_cdp_session_evidence.json"
PAGE_EVIDENCE = ROOT / "data/processed/xhs_video_page_evidence.json"
FILE_MANIFEST = ROOT / "data/processed/xhs_video_file_manifest.json"
RAW_MEDIA = TMP_DIR / "page_media_raw.json"


def wait_cdp_endpoint(policy: XhsCdpReadonlyPolicy, timeout_s: int = 90) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{policy.endpoint}/json/version", timeout=5) as r:
                return r.status == 200
        except OSError:
            time.sleep(5)
    return False


def launch_chrome(policy: XhsCdpReadonlyPolicy) -> None:
    ps1 = ROOT / "scripts/start_xhs_cdp_chrome.ps1"
    subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps1),
         "-NoteUrl", policy.canonical_url],
        check=True, capture_output=True, text=True, timeout=60,
    )


def normalize_duration_seconds(value) -> "float | None":
    """XHS videoDuration 可能为毫秒；归一化为秒。"""
    if value is None:
        return None
    v = float(value)
    if v > 10000:  # 明显是毫秒
        return round(v / 1000.0, 3)
    return v


def pick_stream(media: dict) -> "dict | None":
    """优先 h264、带宽最高的流。"""
    streams = [s for s in media.get("streams", []) if s.get("master_url")]
    if not streams:
        return None
    h264 = [s for s in streams if s.get("codec") == "h264"]
    pool = h264 or streams
    pool.sort(key=lambda s: (s.get("videoBitrate") or 0), reverse=True)
    return pool[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-for-login", type=int, default=None,
                        help="人工登录等待秒数（默认取策略 600）")
    args = parser.parse_args()

    policy = XhsCdpReadonlyPolicy.load(ROOT / "config/xhs_cdp_readonly_policy.yaml", ROOT)
    if args.wait_for_login:
        policy.login_wait_seconds = args.wait_for_login
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 启动或复用专用 Chrome
    if not wait_cdp_endpoint(policy, timeout_s=5):
        print("[CHROME] 启动专用 Chrome（tmp/xhs_cdp_profile，127.0.0.1:9222）…")
        launch_chrome(policy)
    if not wait_cdp_endpoint(policy, timeout_s=90):
        print("[STOP] CDP 端点 90s 内未就绪")
        return 2
    print(f"[CHROME] CDP 端点就绪：{policy.endpoint}")

    adapter = XhsCdpBrowserAdapter(policy=policy, project_root=ROOT)
    try:
        adapter.connect()
        contexts = adapter.contexts()
        pages = adapter.all_pages()
        print(f"[CDP] contexts={len(contexts)} pages={len(pages)}")
        for p in pages:
            print(f"  page: {(p.url or '')[:100]}")

        # 2. 定位目标页：未登录会被重定向到 feed，先记录当前页；登录等待在目标页上进行
        try:
            page = adapter.find_note_page()
        except CdpUnavailable:
            pages = adapter.all_pages()
            if not pages:
                print("[STOP] 专用 Chrome 中没有任何标签页")
                return 3
            page = pages[0]
            print(f"[NAV] 当前页非目标笔记（{(page.url or '')[:60]}），"
                  "将在登录后软导航到 canonical URL")

        # 3. 登录门禁（人工，≤600s，不自动填写任何凭据）
        try:
            adapter.wait_for_login(page)
        except LoginWaitTimeout as exc:
            print(f"[STOP] {exc}")
            return 10

        # 4. 登录后取 xsecToken（该笔记直连返回 300031，需公开分享令牌）
        candidate = json.loads(
            (ROOT / "data/processed/xhs_video_candidate.json").read_text("utf-8"))
        profile_url = candidate["creator_profile_url"]
        pages = adapter.all_pages()
        page = pages[0]
        adapter.soft_navigate_to(page, profile_url, "user/profile")
        notes = adapter.extract_profile_notes_xsec(page)
        target = next((n for n in notes if n.get("note_id") == policy.note_id), None)
        if not target or not target.get("xsec_token"):
            print(f"[STOP] 主页笔记列表中未找到目标笔记或缺 xsecToken（{len(notes)} 条）")
            return 3
        note_url = (f"{policy.canonical_url}?xsec_token={target['xsec_token']}"
                    "&xsec_source=pc_user")
        print(f"[NAV] 取得 xsecToken，软导航到笔记页（type={target.get('type')}）")
        adapter.soft_navigate_to(page, note_url, policy.note_id, max_polls=25)
        state = adapter.page_state(page)
        if policy.note_id not in state.get("url", ""):
            print(f"[STOP] 目标页 URL 不含 note_id：{state.get('url')}")
            return 3

        # 5. 等待笔记数据水合（SPA 异步拉取，note_id 可能短暂为 undefined）
        media = None
        for _ in range(12):
            media = adapter.extract_note_media(page)
            if media and media.get("note_id") == policy.note_id:
                break
            gate = adapter.login_gate_state(page)
            if gate.get("gated"):
                print(f"[STOP] 笔记页出现登录/验证门禁：{gate.get('markers')}")
                return 10
            time.sleep(5)
        if not media or media.get("note_id") != policy.note_id:
            print(f"[STOP] 笔记数据水合超时或 note_id 不符："
                  f"{(media or {}).get('note_id')}")
            return 4
        print(f"[NOTE] 数据就绪：{media.get('nickname')}《{media.get('title')}》")

        # 3. 会话证据（不含 Cookie/storage）
        version = {}
        try:
            with urllib.request.urlopen(f"{policy.endpoint}/json/version", timeout=5) as r:
                version = json.loads(r.read())
        except OSError:
            pass
        session_evidence = {
            "cdp_endpoint": policy.endpoint,
            "browser_type": version.get("Browser", ""),
            "browser_version": version.get("Browser", "").split("/")[-1],
            "context_count": len(contexts),
            "page_count": len(pages),
            "matched_page_url": page.url.split("?")[0],
            "matched_note_id": policy.note_id,
            "logged_in": True,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "source": "cdp_page_observed",
        }
        SESSION_EVIDENCE.write_text(json.dumps(session_evidence, ensure_ascii=False,
                                               indent=2), "utf-8")
        print(f"[EVIDENCE] 会话证据：{SESSION_EVIDENCE}")

        # 4. 页面状态媒体提取 + 被动网络监听
        media_bucket: list[dict] = []
        adapter.attach_media_sniffer(page, media_bucket)
        media = adapter.extract_note_media(page)
        if not media:
            print("[STOP] 页面状态无笔记数据（__INITIAL_STATE__.note 为空）")
            return 4
        if media.get("note_id") != policy.note_id:
            print(f"[STOP] 页面 note_id 不符：{media.get('note_id')}")
            return 3
        if media.get("type") != "video":
            print(f"[STOP] note_type 不是 video：{media.get('type')}")
            return 4
        print(f"[NOTE] {media.get('nickname')}《{media.get('title')}》 "
              f"type={media.get('type')} 时长={media.get('video_duration')}")

        # 原始签名 URL 只写 tmp/
        RAW_MEDIA.write_text(json.dumps(
            {"page_state": media, "network_media": media_bucket,
             "captured_at": datetime.now(timezone.utc).isoformat()},
            ensure_ascii=False, indent=2), "utf-8")

        # Git 侧证据：无签名 URL
        page_duration = normalize_duration_seconds(media.get("video_duration"))
        page_evidence = {
            "note_id": media["note_id"],
            "canonical_url": policy.canonical_url,
            "creator_name": media.get("nickname", ""),
            "title": media.get("title", ""),
            "note_type": media.get("type", ""),
            "page_video_duration_seconds": page_duration,
            "interactions": {"likes": media.get("likes", ""),
                             "collects": media.get("collects", ""),
                             "comments": media.get("comments", "")},
            "streams": [{
                "codec": s.get("codec"), "quality": s.get("quality"),
                "width": s.get("width"), "height": s.get("height"),
                "duration_seconds": normalize_duration_seconds(s.get("duration")),
                "master_url_sha256": sanitize_media_record(
                    s["master_url"], "page_state",
                    datetime.now(timezone.utc).isoformat())["url_sha256"],
                "domain": sanitize_media_record(s["master_url"], "page_state", "")["domain"],
                "has_signature": sanitize_media_record(s["master_url"], "page_state", "")[
                    "has_signature"],
            } for s in media.get("streams", []) if s.get("master_url")],
            "network_media": [sanitize_media_record(m["url"], "network", m["found_at"])
                              for m in media_bucket],
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "source": "cdp_page_observed",
        }
        PAGE_EVIDENCE.write_text(json.dumps(page_evidence, ensure_ascii=False,
                                            indent=2), "utf-8")
        print(f"[EVIDENCE] 页面媒体证据：{PAGE_EVIDENCE}"
              f"（流 {len(page_evidence['streams'])} 个，网络媒体 {len(media_bucket)} 条）")

        # 5. 下载真实视频（页面直链 + context 请求栈）
        stream = pick_stream(media)
        if not stream:
            print("[STOP] 页面状态无可用视频流地址")
            return 5
        out_video = ROOT / policy.output_video
        print(f"[DL] 下载 {stream.get('codec')}/{stream.get('quality')} "
              f"{stream.get('width')}x{stream.get('height')} …")
        adapter.download_via_context(page, stream["master_url"], out_video)
        size = out_video.stat().st_size
        if size <= 0:
            print("[STOP] 下载文件为空")
            return 5

        # 6. 校验
        meta = probe_video_metadata(out_video)
        duration = meta["duration_seconds"]
        drift = abs((duration or 0) - (page_duration or 0))
        print(f"[CHECK] {size} bytes / {duration}s / {meta['resolution']} / "
              f"{meta['video_codec']} / 与页面时长差 {drift:.2f}s")
        if duration is None or duration <= 0:
            print("[STOP] FFprobe 无法读取有效时长")
            return 6
        if page_duration and drift > policy.max_duration_drift:
            print(f"[STOP] 页面时长与文件时长差异 {drift:.1f}s 超过阈值")
            return 6
        sha = sha256_file(out_video)
        manifest = {
            "note_id": policy.note_id,
            "canonical_url": policy.canonical_url,
            "local_tmp_path": "tmp/xhs_video_poc/source_video.mp4",
            "acquired_by": "cdp_context_request",
            "acquired_at": datetime.now(timezone.utc).isoformat(),
            "bytes": size,
            "sha256": sha,
            "duration_seconds": duration,
            "resolution": meta["resolution"],
            "video_codec": meta["video_codec"],
            "audio_codec": meta["audio_codec"],
            "ffmpeg_version": meta["ffmpeg_version"],
            "page_duration_seconds": page_duration,
            "duration_drift_seconds": round(drift, 3),
            "usage_scope": "technical_poc_only",
            "selection_status": "excluded_from_creator_selection",
        }
        FILE_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
        print(f"[DONE] 视频就绪：{FILE_MANIFEST}")
        print("[NEXT] python scripts/analyze_xhs_video.py "
              "--video-file tmp/xhs_video_poc/source_video.mp4")
        return 0
    finally:
        adapter.close()


if __name__ == "__main__":
    sys.exit(main())
