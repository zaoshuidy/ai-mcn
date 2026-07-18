"""Stage 2 代表性生活 Vlog 完整理解管线（30—120 秒真实视频）。

输入：data/processed/xhs_representative_video_candidate.json（筛选脚本产出）。
流程：CDP 复用已登录专用 Chrome → 定位候选笔记标签页 → 页面媒体提取
→ context 请求栈下载 → FFprobe 校验 + SHA-256 → 音频提取
→ faster-whisper small 本地转写 → 每 2s 抽帧 + 场景切换抽帧 → 近似去重
→ 关键帧 manifest + 联系表（contact sheet）→ 文件清单落盘。

只读：不点赞/收藏/评论/关注/私信/发布，不导出 Cookie，不绕过验证码。
原始视频/音频/完整逐字稿/关键帧只存 tmp/，不进 Git。
Git 产物：data/processed/xhs_representative_video_manifest.json。
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.xhs_cdp_browser_adapter import (  # noqa: E402
    XhsCdpBrowserAdapter,
    XhsCdpReadonlyPolicy,
    is_login_gate,
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
CANDIDATE_PATH = ROOT / "data/processed/xhs_representative_video_candidate.json"
TMP_DIR = ROOT / "tmp/xhs_representative_video"
MANIFEST_PATH = ROOT / "data/processed/xhs_representative_video_manifest.json"
WHISPER_MODEL = ROOT / "tmp/whisper_models/small_local"


def pick_stream(media: dict) -> dict | None:
    """优先 h264 主流（与最小POC同一策略）。"""
    streams = media.get("streams") or []
    for codec in ("h264", "h265", "av1"):
        for s in streams:
            if s.get("codec") == codec and s.get("master_url"):
                return s
    return None


def make_contact_sheets(frame_paths: list[Path], timestamps: list[float],
                        out_dir: Path, cols: int = 5, thumb_w: int = 320,
                        per_sheet: int = 20) -> list[Path]:
    """低分辨率联系表（带时间戳标注），供多模态批量读帧。仅本地 tmp/。"""
    from PIL import Image, ImageDraw

    sheets: list[Path] = []
    for sheet_idx in range(0, len(frame_paths), per_sheet):
        chunk = frame_paths[sheet_idx:sheet_idx + per_sheet]
        chunk_ts = timestamps[sheet_idx:sheet_idx + per_sheet]
        thumbs = []
        for fp in chunk:
            img = Image.open(fp).convert("RGB")
            ratio = thumb_w / img.width
            img = img.resize((thumb_w, max(1, int(img.height * ratio))))
            thumbs.append(img)
        if not thumbs:
            break
        cell_h = max(t.height for t in thumbs) + 22
        rows = (len(thumbs) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * thumb_w, rows * cell_h), (24, 24, 24))
        draw = ImageDraw.Draw(sheet)
        for i, (t, ts) in enumerate(zip(thumbs, chunk_ts, strict=True)):
            x, y = (i % cols) * thumb_w, (i // cols) * cell_h
            sheet.paste(t, (x, y))
            draw.rectangle([x, y + t.height, x + thumb_w, y + cell_h], fill=(0, 0, 0))
            draw.text((x + 6, y + t.height + 4), f"{ts:.1f}s", fill=(255, 255, 0))
        out = out_dir / f"contact_sheet_{sheet_idx // per_sheet + 1}.jpg"
        sheet.save(out, quality=80)
        sheets.append(out)
    return sheets


def main() -> int:
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    note_id = candidate["note_id"]
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    policy = XhsCdpReadonlyPolicy.load(POLICY_PATH, ROOT)
    adapter = XhsCdpBrowserAdapter(policy, ROOT)
    print("[CDP] 连接 127.0.0.1:9222 ...")
    if not adapter.chrome_reachable():
        print("[FAIL] CDP 端点不可达")
        return 2
    adapter.connect()
    try:
        pages = adapter.all_pages()
        page = next((p for p in pages if note_id in (p.url or "")), None)
        if page is None:
            print(f"[FAIL] 未找到 note_id={note_id} 的标签页；"
                  "请在专用 Chrome 打开候选笔记后重跑")
            return 2
        gate = adapter.login_gate_state(page)
        if is_login_gate(gate):
            print("[FAIL] 未登录")
            return 3
        print(f"[PAGE] {page.url[:80]}")

        media = adapter.extract_note_media(page)
        if not media or media.get("type") != "video":
            print("[FAIL] 页面不是视频笔记或状态缺失")
            return 4
        stream = pick_stream(media)
        if not stream:
            print("[FAIL] 无可用视频流")
            return 4
        page_dur = (stream.get("duration") or media.get("video_duration") or 0) / 1000.0

        # 1. 下载（页面直链 + context 请求栈；原始 URL 只进 tmp/）
        video_path = TMP_DIR / "source_video.mp4"
        (TMP_DIR / "page_media_raw.json").write_text(json.dumps(
            {"master_url": stream["master_url"],
             "backup_urls": stream.get("backup_urls", []),
             "observed_at": datetime.now(timezone.utc).isoformat()},
            ensure_ascii=False, indent=2), "utf-8")
        urls = [stream["master_url"], *stream.get("backup_urls", [])]
        last_err: Exception | None = None
        for u in urls:
            try:
                adapter.download_via_context(page, u, video_path)
                if video_path.stat().st_size > 0:
                    break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(1)
        if not video_path.is_file() or video_path.stat().st_size == 0:
            print(f"[FAIL] 视频下载失败: {last_err}")
            return 5
        print(f"[DOWNLOAD] {video_path.stat().st_size} bytes")

        # 2. FFprobe 校验
        meta = probe_video_metadata(video_path)
        width, height = 0, 0
        if meta.get("resolution") and "x" in str(meta["resolution"]):
            w_s, h_s = str(meta["resolution"]).split("x", 1)
            width, height = int(w_s), int(h_s)
        drift = abs((meta["duration_seconds"] or 0) - page_dur)
        dur_file = meta["duration_seconds"] or 0.0
        print(f"[PROBE] {dur_file:.1f}s {width}x{height} "
              f"{meta.get('video_codec')}/{meta.get('audio_codec')} drift={drift:.3f}s")
        if not meta["duration_seconds"] or meta["duration_seconds"] <= 0 or width <= 0:
            print("[FAIL] FFprobe 校验不通过")
            return 6
        if drift > 3.0:
            print(f"[FAIL] 页面时长与文件时长漂移 {drift:.2f}s 超阈值")
            return 6
        sha = sha256_file(video_path)

        # 3. 音频 + 4. 转写（faster-whisper small 本地模型）
        audio_path = extract_audio(video_path, TMP_DIR / "audio.wav")
        print(f"[AUDIO] {audio_path.name}")
        model_ref = str(WHISPER_MODEL) if WHISPER_MODEL.is_dir() else "small"
        txt_path, srt_path = transcribe_with_faster_whisper(
            audio_path, TMP_DIR, model_size=model_ref)
        print(f"[ASR] model={model_ref} -> {txt_path.name}, {srt_path.name}")

        # 5. 抽帧（每2s + 场景切换）+ 6. 去重
        frames = extract_keyframes(video_path, TMP_DIR / "keyframes", interval_seconds=2)
        interval_frames = sorted(
            [f for f in frames if f.kind == "interval"], key=lambda f: f.timestamp)
        scene_frames = [f for f in frames if f.kind == "scene_change"]
        all_paths = [Path(f.path) for f in interval_frames + scene_frames]
        kept = dedupe_keyframes(all_paths, max_distance=5)
        kept_set = {str(p) for p in kept}
        kept_interval = [f for f in interval_frames if f.path in kept_set]
        print(f"[FRAMES] interval={len(interval_frames)} scene={len(scene_frames)} "
              f"deduped={len(kept)} (有效 interval={len(kept_interval)})")

        # 7. 联系表（多模态读帧输入）
        sheets = make_contact_sheets(
            [Path(f.path) for f in kept_interval],
            [f.timestamp for f in kept_interval], TMP_DIR)
        print(f"[SHEETS] {[s.name for s in sheets]}")

        # 8. 关键帧 manifest（tmp/ 本地）
        (TMP_DIR / "keyframe_manifest.json").write_text(json.dumps({
            "interval_total": len(interval_frames),
            "scene_total": len(scene_frames),
            "deduped_total": len(kept),
            "valid_interval_frames": [
                {"timestamp": f.timestamp, "file": Path(f.path).name}
                for f in kept_interval],
        }, ensure_ascii=False, indent=2), "utf-8")

        # 9. Git 文件清单（不含签名 URL / 原始媒体）
        manifest = {
            "note_id": note_id,
            "canonical_url": candidate["canonical_url"],
            "creator_name": candidate["creator_name"],
            "title": candidate["title"],
            "file_size_bytes": video_path.stat().st_size,
            "sha256": sha,
            "duration_seconds_file": round(dur_file, 3),
            "duration_seconds_page": round(page_dur, 3),
            "duration_drift_seconds": round(drift, 3),
            "width": width,
            "height": height,
            "video_codec": meta.get("video_codec"),
            "audio_codec": meta.get("audio_codec"),
            "asr_model": "faster-whisper small (local)",
            "keyframe_stats": {
                "interval_total": len(interval_frames),
                "scene_change_total": len(scene_frames),
                "deduped_total": len(kept),
                "valid_interval": len(kept_interval),
            },
            "source": "cdp_page_observed",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "raw_artifacts": "tmp/xhs_representative_video/ (gitignored)",
        }
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
        print(f"[OK] manifest -> {MANIFEST_PATH}")
        print("NEXT: 多模态读取 contact sheet → 生成时间线与分析报告")
        return 0
    finally:
        adapter.close()


if __name__ == "__main__":
    raise SystemExit(main())
