"""Stage 3 Top3 重点候选代表视频完整理解管线。

对 Top3 每位处理 1 条代表视频（确定性选题，理由见 TARGET_NOTES）：
页面证据 → 视频下载 → FFprobe 校验+SHA-256 → 音频提取 → faster-whisper small
本地转写 → 每2s抽帧+场景切换抽帧 → 近似去重 → 关键帧manifest+联系表。

风格研究对象（欧盈Kelly）额外记录另外 2 条视频的页面证据
（满足"3条真实视频证据：1条完整处理+2条页面证据"）。

只读：不点赞/收藏/评论/关注/私信/发布，不导出 Cookie，不绕过验证码（退出码5）。
原始视频/音频/逐字稿/关键帧只存 tmp/stage_3_top3_video/，不进 Git。
Git 产物：data/processed/stage_3_top3_video_manifest.json（无签名URL/原始媒体）。

用法：python scripts/run_stage_3_top3_video.py [--creator-id CID]
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
TOP3_PATH = ROOT / "data/processed/stage_3_top3.json"
FINAL_PATH = ROOT / "data/processed/stage_3_final_10.json"
STYLE_PATH = ROOT / "data/processed/stage_3_style_reference.json"
MANIFEST_PATH = ROOT / "data/processed/stage_3_top3_video_manifest.json"
TMP_BASE = ROOT / "tmp/stage_3_top3_video"
WHISPER_MODEL = ROOT / "tmp/whisper_models/small_local"

PAGE_INTERVAL_S = 8
EXIT_CAPTCHA = 5

# 确定性选题（不得更换为未核验笔记）：
TARGET_NOTES = {
    "60bb90f00000000001002887": {  # 欧盈Kelly（风格研究对象）
        "note_id": "6989ab01000000001a0360c5",
        "reason": "非商单上班vlog(153.5s)，避免汽车硬广商单干扰风格研究",
        "extra_page_evidence_count": 2,  # 风格研究对象需3条视频证据
    },
    "586733cd50c4b43cccffc5c8": {  # 小季没烦恼
        "note_id": "6a58b7ea000000001101a7bb",
        "reason": "晚间日记(114s)，含霸王茶姬自然植入，商单脚本研究价值最高",
        "extra_page_evidence_count": 0,
    },
    "5ad034864eacab543fa98374": {  # 一只牛🐮
        "note_id": "6a59b5ac00000000100295fe",
        "reason": "独居早餐(54.7s)，沉浸式字幕型核心场景代表",
        "extra_page_evidence_count": 0,
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_one(adapter, creator: dict, target: dict) -> dict:
    """单候选完整管线，返回 manifest 条目（含失败时已完成部分）。"""
    cid = creator["creator_id"]
    note_id = target["note_id"]
    tmp = TMP_BASE / cid
    tmp.mkdir(parents=True, exist_ok=True)
    entry = {
        "creator_id": cid,
        "nickname": creator["nickname"],
        "note_id": note_id,
        "target_reason": target["reason"],
        "observed_at": utc_now(),
        "usage_scope": "stage_3_style_research",
    }
    note = next((n for n in creator["representative_notes"] if n["note_id"] == note_id), None)
    if not note:
        entry["error"] = "目标笔记不在代表笔记中"
        return entry

    pages = adapter.all_pages()
    if not pages:
        entry["error"] = "无标签页"
        return entry
    page = pages[0]
    adapter.soft_navigate_to(page, creator["profile_url"], "/user/profile/")
    time.sleep(4)
    if adapter.login_gate_state(page).get("gated"):
        entry["error"] = "captcha_or_login_gate"
        return entry
    notes_meta = {n.get("note_id"): n for n in adapter.extract_profile_notes_xsec(page)
                  if n.get("note_id")}
    meta = notes_meta.get(note_id, {})
    url = note["canonical_url"]
    if meta.get("xsec_token"):
        url += f"?xsec_token={meta['xsec_token']}&xsec_source=pc_user"
    time.sleep(PAGE_INTERVAL_S)
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
    adapter.download_via_context(page, stream["master_url"], video_path)
    size = video_path.stat().st_size
    if size <= 0:
        entry["error"] = "下载视频为空"
        return entry
    meta_info = probe_video_metadata(video_path)
    page_dur = page_video_dur_s or note.get("duration_seconds") or 0
    drift = abs((meta_info.get("duration_seconds") or 0) - (page_dur or 0))
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
    video_path.unlink(missing_ok=True)  # 原始视频不进Git且不留存
    entry["status"] = "media_processed"
    print(f"       [OK] {creator['nickname']} {entry['file']['duration_s']:.1f}s "
          f"frames={len(kept_interval)} asr_chars={entry['asr']['transcript_chars']}")

    # 风格研究对象：额外2条视频页面证据
    extra_n = target.get("extra_page_evidence_count", 0)
    if extra_n:
        extras = []
        handled = {note_id, *(n["note_id"] for n in creator["representative_notes"])}
        for nid, m in notes_meta.items():
            if len(extras) >= extra_n:
                break
            if nid in handled or (m.get("type") or "") != "video":
                continue
            eurl = f"https://www.xiaohongshu.com/explore/{nid}"
            if m.get("xsec_token"):
                eurl += f"?xsec_token={m['xsec_token']}&xsec_source=pc_user"
            time.sleep(PAGE_INTERVAL_S)
            try:
                adapter.soft_navigate_to(page, eurl, nid)
                time.sleep(4)
                em = adapter.extract_note_media(page) or {}
                if em.get("type") == "video":
                    extras.append({
                        "note_id": nid,
                        "canonical_url": f"https://www.xiaohongshu.com/explore/{nid}",
                        "title": em.get("title"),
                        "note_type": "video",
                        "duration_seconds": normalize_duration_seconds(em.get("video_duration")),
                        "likes": em.get("likes"),
                        "source": "page_observed",
                        "observed_at": utc_now(),
                    })
                    print(f"       [EXTRA] 页面证据 {nid[:12]} {str(em.get('title'))[:24]}")
            except Exception as exc:  # noqa: BLE001
                print(f"       [EXTRA-FAIL] {nid[:12]} {str(exc)[:80]}")
        entry["extra_video_page_evidence"] = extras
    return entry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--creator-id", default=None)
    args = parser.parse_args()

    top3 = json.loads(TOP3_PATH.read_text(encoding="utf-8"))["top3"]
    final_doc = json.loads(FINAL_PATH.read_text(encoding="utf-8"))
    creators = {c["creator_id"]: c for c in final_doc["finalists"]}
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
        for t in top3:
            cid = t["creator_id"]
            if args.creator_id and cid != args.creator_id:
                continue
            if any(v.get("creator_id") == cid and v.get("status") == "media_processed"
                   for v in manifest["videos"]):
                print(f"[SKIP] {t['nickname']} 已完成")
                continue
            target = TARGET_NOTES[cid]
            print(f"[VIDEO] {t['nickname']} -> {target['note_id'][:12]} ({target['reason']})")
            entry = run_one(adapter, creators[cid], target)
            if entry.get("error") == "captcha_or_login_gate":
                print("[STOP] 登录门/验证码，停止（退出码 5）")
                return EXIT_CAPTCHA
            manifest["videos"] = [v for v in manifest["videos"] if v.get("creator_id") != cid]
            manifest["videos"].append(entry)
            manifest["generated_at"] = utc_now()
            MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
            if entry.get("error"):
                print(f"       [FAIL] {entry['error']}")
            time.sleep(PAGE_INTERVAL_S)
    finally:
        adapter.close()

    # 风格研究对象的3条视频证据回写
    style = json.loads(STYLE_PATH.read_text(encoding="utf-8"))
    ref = style.get("style_reference")
    if ref:
        for v in manifest["videos"]:
            if v.get("creator_id") == ref["creator_id"]:
                ref["video_evidence"] = {
                    "fully_processed_note_id": v.get("note_id"),
                    "representative_note_page_evidence": "见 stage_3_final_10.json 代表笔记",
                    "extra_video_page_evidence": v.get("extra_video_page_evidence", []),
                }
                STYLE_PATH.write_text(json.dumps(style, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    ok = sum(1 for v in manifest["videos"] if v.get("status") == "media_processed")
    print(f"[DONE] 管线完成 {ok}/{len(top3)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
