"""Stage 4 欧盈Kelly 剩余 2 条视频完整理解管线（CDP 串行）。

对风格研究对象欧盈Kelly（creator_id=60bb90f00000000001002887）的 2 条
已有页面证据的视频执行与 Stage 3 相同的理解管线（模式复用
scripts/run_stage_3_top3_video.py，不开发新架构）：
页面证据（先开主页取 xsec_token 再开笔记，页面间隔>=8s）→ 视频下载
（页面真实 video_url 优先，yt-dlp 备用）→ FFprobe 校验+SHA-256 → 音频提取
→ faster-whisper small 本地转写 → 每2s抽帧+场景切换抽帧 → 近似去重
→ 关键帧 manifest + 联系表（供多模态逐帧读取）。

只读：不点赞/收藏/评论/关注/私信/发布，不导出 Cookie，不绕过验证码（退出码5）。
原始视频/音频/逐字稿/关键帧只存 tmp/stage4_kelly/，不进 Git。
中间 manifest 也只写 tmp/stage4_kelly/（含签名URL哈希，不含签名URL本体）；
Git 产物仅 data/processed/stage_4_kelly_video_timelines.json（由
scripts/build_stage_4_kelly_timelines.py 生成）。

用法：python scripts/run_stage_4_kelly_videos.py [--note-id NID]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_xhs_cdp_video_poc import normalize_duration_seconds  # noqa: E402
from run_xhs_representative_video_poc import make_contact_sheets, pick_stream  # noqa: E402

from adapters.xhs_cdp_browser_adapter import (  # noqa: E402
    XhsCdpBrowserAdapter,
    XhsCdpReadonlyPolicy,
    hash_signed_url,
    url_domain,
)
from src.video_analyzer import (  # noqa: E402
    dedupe_keyframes,
    extract_audio,
    extract_keyframes,
    probe_video_metadata,
    sha256_file,
    transcribe_with_faster_whisper,
)

POLICY_PATH = ROOT / "config/xhs_cdp_readonly_policy.yaml"
FINAL_PATH = ROOT / "data/processed/stage_3_final_10.json"
TMP_BASE = ROOT / "tmp/stage4_kelly"
MANIFEST_PATH = TMP_BASE / "stage_4_kelly_video_manifest.json"
WHISPER_MODEL = ROOT / "tmp/whisper_models/small_local"

PAGE_INTERVAL_S = 8
EXIT_CAPTCHA = 5
CREATOR_ID = "60bb90f00000000001002887"  # 欧盈Kelly（风格研究对象）

# 确定性选题（Stage 3 已落地页面证据的两条，不得更换为未核验笔记）：
TARGET_NOTES = {
    "6a5c556e000000000c0162f5": {
        "reason": "深圳MKTer上班vlog(页面约219.4s)，与已处理6989ab01000000001a0360c5同题材，"
                  "用于验证上班vlog风格稳定性",
    },
    "6a5616b600000000220164a4": {
        "reason": "i人潜水vlog(页面约164.8s)，非上班题材，用于识别风格跨题材迁移性",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def download_with_ytdlp(url: str, out_path: Path) -> bool:
    """yt-dlp 备用下载（不导出 Cookie；失败如实返回 False）。"""
    exe = shutil.which("yt-dlp")
    if not exe:
        return False
    proc = subprocess.run(
        [exe, "--no-playlist", "-f", "bv*+ba/b", "--merge-output-format", "mp4",
         "-o", str(out_path), url],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
        check=False,
    )
    return proc.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0


def run_one(adapter, page, creator: dict, note_id: str, notes_meta: dict) -> dict:
    """单条视频完整管线，返回 manifest 条目（含失败时已完成部分）。"""
    tmp = TMP_BASE / note_id
    tmp.mkdir(parents=True, exist_ok=True)
    target = TARGET_NOTES[note_id]
    entry = {
        "creator_id": CREATOR_ID,
        "nickname": creator["nickname"],
        "note_id": note_id,
        "canonical_url": f"https://www.xiaohongshu.com/explore/{note_id}",
        "target_reason": target["reason"],
        "observed_at": utc_now(),
        "usage_scope": "stage_4_style_research",
    }
    meta = notes_meta.get(note_id, {})
    url = entry["canonical_url"]
    if meta.get("xsec_token"):
        url += f"?xsec_token={meta['xsec_token']}&xsec_source=pc_user"
    adapter.soft_navigate_to(page, url, note_id)
    time.sleep(4)
    if adapter.login_gate_state(page).get("gated"):
        entry["error"] = "captcha_or_login_gate"
        return entry

    media = adapter.extract_note_media(page) or {}
    page_video_dur_s = normalize_duration_seconds(media.get("video_duration"))
    entry["page_evidence"] = {
        "title": media.get("title"),
        "type": media.get("type"),
        "nickname": media.get("nickname"),
        "user_id": media.get("user_id"),
        "video_duration_s": page_video_dur_s,
        "likes": media.get("likes"),
        "collects": media.get("collects"),
        "comments": media.get("comments"),
        "streams_count": len(media.get("streams") or []),
        "source": "page_observed",
    }
    if media.get("type") != "video":
        entry["error"] = f"页面类型非video: {media.get('type')}"
        return entry
    stream = pick_stream(media)
    if not stream:
        entry["error"] = "无可用视频流"
        return entry
    entry["media_url_sha256"] = hash_signed_url(stream["master_url"])
    entry["media_domain"] = url_domain(stream["master_url"])

    video_path = tmp / "source_video.mp4"
    download_source = "page_video_url_via_context"
    try:
        adapter.download_via_context(page, stream["master_url"], video_path)
    except Exception as exc:  # noqa: BLE001 - 主路径失败才走 yt-dlp 备用
        entry["download_primary_error"] = str(exc)[:200]
        download_source = "yt_dlp_fallback"
        if not download_with_ytdlp(url, video_path):
            entry["error"] = "页面流下载与 yt-dlp 备用均失败"
            return entry
    entry["download_source"] = download_source
    size = video_path.stat().st_size
    if size <= 0:
        entry["error"] = "下载视频为空"
        return entry
    meta_info = probe_video_metadata(video_path)
    drift = abs((meta_info.get("duration_seconds") or 0) - (page_video_dur_s or 0))
    entry["file"] = {
        "bytes": size,
        "duration_s": meta_info.get("duration_seconds"),
        "resolution": meta_info.get("resolution"),
        "video_codec": meta_info.get("video_codec"),
        "audio_codec": meta_info.get("audio_codec"),
        "sha256": sha256_file(video_path),
        "page_file_drift_s": round(drift, 3),
    }
    if not meta_info.get("duration_seconds") or drift > 3.0:
        entry["error"] = f"FFprobe校验失败或时长漂移{drift:.2f}s"
        return entry

    audio_path = extract_audio(video_path, tmp / "audio.wav")
    model_ref = str(WHISPER_MODEL) if WHISPER_MODEL.is_dir() else "small"
    txt_path, srt_path = transcribe_with_faster_whisper(audio_path, tmp, model_size=model_ref)
    entry["asr"] = {
        "model": (
            "faster-whisper small (local)" if WHISPER_MODEL.is_dir()
            else "faster-whisper small"
        ),
        "transcript_chars": len("".join(txt_path.read_text(encoding="utf-8").split())),
        "srt_segments": srt_path.read_text(encoding="utf-8").count("\n\n") + 1,
    }

    frames = extract_keyframes(video_path, tmp / "keyframes", interval_seconds=2)
    interval_frames = sorted([f for f in frames if f.kind == "interval"],
                             key=lambda f: f.timestamp)
    scene_frames = [f for f in frames if f.kind == "scene_change"]
    kept = dedupe_keyframes([Path(f.path) for f in interval_frames + scene_frames],
                            max_distance=5)
    kept_set = {str(p) for p in kept}
    kept_interval = [f for f in interval_frames if f.path in kept_set]
    sheets = make_contact_sheets([Path(f.path) for f in kept_interval],
                                 [f.timestamp for f in kept_interval], tmp)
    entry["keyframes"] = {
        "interval_total": len(interval_frames),
        "scene_total": len(scene_frames),
        "deduped_total": len(kept),
        "valid_interval": len(kept_interval),
        "timestamps": [f.timestamp for f in kept_interval],
        "contact_sheets": [s.name for s in sheets],
    }
    (tmp / "keyframe_manifest.json").write_text(json.dumps({
        "valid_interval_frames": [
            {"timestamp": f.timestamp, "file": Path(f.path).name} for f in kept_interval],
    }, ensure_ascii=False, indent=2), "utf-8")
    # 原始视频保留在 tmp/（gitignored），供多模态复读复核；不进 Git。
    entry["status"] = "media_processed"
    print(f"       [OK] {note_id[:12]} {entry['file']['duration_s']:.1f}s "
          f"frames={len(kept_interval)} asr_chars={entry['asr']['transcript_chars']}")
    return entry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--note-id", default=None)
    args = parser.parse_args()

    final_doc = json.loads(FINAL_PATH.read_text(encoding="utf-8"))
    creator = next(c for c in final_doc["finalists"] if c["creator_id"] == CREATOR_ID)
    TMP_BASE.mkdir(parents=True, exist_ok=True)
    manifest = {"generated_at": utc_now(), "videos": []}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    policy = XhsCdpReadonlyPolicy.load(POLICY_PATH, ROOT)
    adapter = XhsCdpBrowserAdapter(policy, ROOT)
    if not adapter.chrome_reachable():
        print("[ERR] CDP 端点不可达")
        return 2
    adapter.connect()

    try:
        pages = adapter.all_pages()
        if not pages:
            print("[ERR] 无标签页")
            return 2
        page = pages[0]
        # 先开主页取 xsec_token（Stage 3 同一顺序）
        adapter.soft_navigate_to(page, creator["profile_url"], "/user/profile/")
        time.sleep(4)
        if adapter.login_gate_state(page).get("gated"):
            print("[STOP] 登录门/验证码，停止（退出码 5）")
            return EXIT_CAPTCHA
        notes_meta = {n.get("note_id"): n for n in adapter.extract_profile_notes_xsec(page)
                      if n.get("note_id")}
        for note_id in TARGET_NOTES:
            if args.note_id and note_id != args.note_id:
                continue
            if any(v.get("note_id") == note_id and v.get("status") == "media_processed"
                   for v in manifest["videos"]):
                print(f"[SKIP] {note_id[:12]} 已完成")
                continue
            print(f"[VIDEO] {note_id[:12]} ({TARGET_NOTES[note_id]['reason'][:24]}...)")
            time.sleep(PAGE_INTERVAL_S)
            entry = run_one(adapter, page, creator, note_id, notes_meta)
            if entry.get("error") == "captcha_or_login_gate":
                print("[STOP] 登录门/验证码，停止（退出码 5）")
                return EXIT_CAPTCHA
            manifest["videos"] = [v for v in manifest["videos"]
                                  if v.get("note_id") != note_id]
            manifest["videos"].append(entry)
            manifest["generated_at"] = utc_now()
            MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
            if entry.get("error"):
                print(f"       [FAIL] {entry['error']}")
                return 1
            time.sleep(PAGE_INTERVAL_S)
    finally:
        adapter.close()

    ok = sum(1 for v in manifest["videos"] if v.get("status") == "media_processed")
    print(f"[DONE] 管线完成 {ok}/{len(TARGET_NOTES)}")
    return 0 if ok == len(TARGET_NOTES) else 1


if __name__ == "__main__":
    sys.exit(main())
