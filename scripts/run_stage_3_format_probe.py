"""Stage 3 内容形式真实探测：判定每位深核候选的口播/字幕类型。

对 15 位深核候选各取 1 条代表视频笔记：
1. CDP 复用已登录标签页软导航打开笔记（只读，禁止写交互）；
2. 提取页面视频流地址，通过浏览器上下文下载到 tmp（不提交 Git）；
3. FFmpeg 抽取前 30 秒音频 → faster-whisper tiny 转写 → 判定 has_voiceover；
4. FFmpeg 在 15%/50%/85% 时长处抽 3 帧并拼接触表 → 供人工/多模态判定
   has_on_screen_text（视觉判定结果单独写入 stage_3_visual_verdicts.json）。

安全约束：
- 页面操作间隔 >= 8 秒；每 5 位暂停 120 秒；单账号失败记录后继续；
- 检测到验证码/登录门立即保存断点并以退出码 5 停止（人工处理后可断点续跑）；
- 原始视频/音频/帧仅存 tmp/stage_3_format_probe/（已被 .gitignore 忽略）；
- 不导出 Cookie，不记录完整签名媒体 URL（只存哈希与域名）。

用法：python scripts/run_stage_3_format_probe.py [--max-per-run N]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from adapters.xhs_cdp_browser_adapter import (  # noqa: E402
    XhsCdpBrowserAdapter,
    XhsCdpReadonlyPolicy,
    hash_signed_url,
    url_domain,
)
from src.video_analyzer import find_ffmpeg, transcribe_with_faster_whisper  # noqa: E402

DEEP_REVIEW = PROJECT_ROOT / "data/processed/stage_3_deep_review_15.json"
PROBE_OUT = PROJECT_ROOT / "data/processed/stage_3_format_probe.json"
TMP_DIR = PROJECT_ROOT / "tmp/stage_3_format_probe"
POLICY_PATH = PROJECT_ROOT / "config/xhs_cdp_readonly_policy.yaml"

PAGE_INTERVAL_S = 8
BATCH_PAUSE_S = 120
BATCH_SIZE = 5
VOICEOVER_MIN_CHARS = 15  # 前30秒口播字数阈值
PROBE_AUDIO_S = 30

EXIT_OK = 0
EXIT_CAPTCHA = 5


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def pick_stream(media: dict) -> dict | None:
    """优先 h264 流（兼容性最好）；与 run_xhs_cdp_video_poc.pick_stream 同规则。"""
    streams = [s for s in media.get("streams", []) if s.get("master_url")]
    if not streams:
        return None
    h264 = [s for s in streams if s.get("codec") == "h264"]
    pool = h264 or streams
    pool.sort(key=lambda s: s.get("size") or 1 << 60)
    return pool[0]


def probe_audio_voiceover(video_path: Path, work_dir: Path) -> dict:
    """前30秒音频转写，返回 {has_voiceover, spoken_chars_30s, model}。"""
    ffmpeg = find_ffmpeg()
    audio_path = work_dir / "probe_audio.wav"
    cmd = [
        ffmpeg, "-y", "-i", str(video_path), "-t", str(PROBE_AUDIO_S),
        "-vn", "-ac", "1", "-ar", "16000", str(audio_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0 or not audio_path.exists():
        return {"has_voiceover": None, "spoken_chars_30s": None,
                "model": None, "error": "ffmpeg audio extract failed"}
    try:
        txt_path, _srt = transcribe_with_faster_whisper(audio_path, work_dir, model_size="tiny")
        text = txt_path.read_text(encoding="utf-8")
    except Exception as exc:  # 转写失败诚实记录，不臆断
        if "为空" in str(exc):
            # 前30秒无任何可识别语音：沉浸式BGM视频的典型特征
            return {"has_voiceover": False, "spoken_chars_30s": 0,
                    "model": "faster-whisper tiny"}
        return {"has_voiceover": None, "spoken_chars_30s": None,
                "model": "faster-whisper tiny", "error": str(exc)[:200]}
    chars = len("".join(text.split()))
    return {
        "has_voiceover": chars >= VOICEOVER_MIN_CHARS,
        "spoken_chars_30s": chars,
        "model": "faster-whisper tiny",
    }


def extract_frames(video_path: Path, duration_s: float | None, work_dir: Path) -> list[dict]:
    """在 15%/50%/85% 时长处抽帧并拼接 3 联触表，返回帧清单。"""
    ffmpeg = find_ffmpeg()
    if not duration_s or duration_s <= 0:
        duration_s = 30.0
    frames: list[dict] = []
    frame_paths: list[Path] = []
    for idx, ratio in enumerate((0.15, 0.50, 0.85)):
        ts = round(duration_s * ratio, 1)
        fp = work_dir / f"frame_{idx}.jpg"
        cmd = [ffmpeg, "-y", "-ss", str(ts), "-i", str(video_path),
               "-frames:v", "1", "-q:v", "5", "-vf", "scale=480:-1", str(fp)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode == 0 and fp.exists() and fp.stat().st_size > 0:
            frames.append({"timestamp_s": ts, "path": str(fp.relative_to(PROJECT_ROOT))})
            frame_paths.append(fp)
    if len(frame_paths) == 3:
        sheet = work_dir / "contact_sheet.jpg"
        cmd = [ffmpeg, "-y", "-i", str(frame_paths[0]), "-i", str(frame_paths[1]),
               "-i", str(frame_paths[2]), "-filter_complex", "hstack=inputs=3",
               "-q:v", "6", str(sheet)]
        subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return frames


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-per-run", type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    review = json.loads(DEEP_REVIEW.read_text(encoding="utf-8"))
    creators = review["creators"]
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_path = TMP_DIR / "checkpoint.json"
    done: list[str] = []
    if checkpoint_path.exists():
        done = json.loads(checkpoint_path.read_text(encoding="utf-8")).get("done", [])

    results: dict = {"generated_at": utc_now(), "probes": []}
    if PROBE_OUT.exists():
        results = json.loads(PROBE_OUT.read_text(encoding="utf-8"))
    # 只有无 error 且拿到语音判定（含"无语音"结论）的条目才算完成；
    # 失败条目允许断点续跑时自动重试。
    ok_ids = {p["creator_id"] for p in results["probes"]
              if not p.get("error") and p.get("has_voiceover") is not None}
    done = [cid for cid in done if cid in ok_ids]
    probed_ids = {p["creator_id"] for p in results["probes"]
                  if not p.get("error") and p.get("has_voiceover") is not None}

    policy = XhsCdpReadonlyPolicy.load(POLICY_PATH, PROJECT_ROOT)
    adapter = XhsCdpBrowserAdapter(policy, PROJECT_ROOT)
    if not adapter.chrome_reachable():
        print("[ERR] CDP 端点不可达，请先启动专用 Chrome")
        return 2
    adapter.connect()

    processed = 0
    try:
        for creator in creators:
            cid = creator["creator_id"]
            if cid in done or cid in probed_ids:
                continue
            if processed >= args.max_per_run:
                print(f"[BATCH] 本轮已达 {args.max_per_run} 位上限，断点已保存，可再次运行续跑")
                break
            video_notes = [n for n in creator.get("representative_notes", [])
                           if n.get("note_type") == "video" and n.get("canonical_url")]
            if not video_notes:
                print(f"[SKIP] {creator['nickname']} 无视频代表笔记")
                done.append(cid)
                continue
            note = video_notes[0]
            print(f"[PROBE] {creator['nickname']} -> {note['canonical_url']}")
            work_dir = TMP_DIR / cid
            work_dir.mkdir(parents=True, exist_ok=True)
            entry = {
                "creator_id": cid,
                "nickname": creator["nickname"],
                "note_id": note["note_id"],
                "canonical_url": note["canonical_url"],
                "observed_at": utc_now(),
                "source": "ai_inferred",
                "confidence": 0.9,
            }
            try:
                # canonical URL 无 xsec_token 会被重定向到 404 安全页；
                # 与深核流程一致：先开主页取笔记 xsec 令牌，再带令牌开笔记。
                # 不用 find_or_soft_navigate：其等待片段固定为策略中的 Stage 2 note_id。
                pages = adapter.all_pages()
                if not pages:
                    raise RuntimeError("专用 Chrome 中没有任何标签页")
                page = pages[0]
                adapter.soft_navigate_to(page, creator["profile_url"], "/user/profile/")
                time.sleep(4)
                gate = adapter.login_gate_state(page)
                if gate.get("gated"):
                    print("[STOP] 检测到登录门/验证码，保存断点并停止（退出码 5）")
                    checkpoint_path.write_text(json.dumps({"done": done}, ensure_ascii=False),
                                               encoding="utf-8")
                    return EXIT_CAPTCHA
                notes_meta = adapter.extract_profile_notes_xsec(page)
                tokened = {n.get("note_id"): n for n in notes_meta if n.get("note_id")}
                meta = tokened.get(note["note_id"], {})
                note_url = note["canonical_url"]
                if meta.get("xsec_token"):
                    note_url += f"?xsec_token={meta['xsec_token']}&xsec_source=pc_user"
                time.sleep(PAGE_INTERVAL_S)
                adapter.soft_navigate_to(page, note_url, note["note_id"])
                time.sleep(4)
                gate = adapter.login_gate_state(page)
                if gate.get("gated"):
                    print("[STOP] 检测到登录门/验证码，保存断点并停止（退出码 5）")
                    checkpoint_path.write_text(json.dumps({"done": done}, ensure_ascii=False),
                                               encoding="utf-8")
                    return EXIT_CAPTCHA
                media = adapter.extract_note_media(page) or {}
                stream = pick_stream(media)
                if not stream:
                    raise RuntimeError("页面无可用视频流")
                entry["media_url_sha256"] = hash_signed_url(stream["master_url"])
                entry["media_domain"] = url_domain(stream["master_url"])
                entry["media_codec"] = stream.get("codec")
                video_path = work_dir / "probe_video.mp4"
                adapter.download_via_context(page, stream["master_url"], video_path)
                size = video_path.stat().st_size
                if size <= 0:
                    raise RuntimeError("下载视频为空")
                entry["video_bytes"] = size
                entry["video_duration_page_s"] = media.get("video_duration")
                audio = probe_audio_voiceover(video_path, work_dir)
                entry.update(audio)
                entry["frames"] = extract_frames(
                    video_path, note.get("duration_seconds"), work_dir)
                entry["contact_sheet"] = str(
                    (work_dir / "contact_sheet.jpg").relative_to(PROJECT_ROOT)
                )
                video_path.unlink(missing_ok=True)
                for wav in work_dir.glob("*.wav"):
                    wav.unlink(missing_ok=True)
                print(f"       voiceover={entry.get('has_voiceover')} "
                      f"chars={entry.get('spoken_chars_30s')} frames={len(entry['frames'])}")
            except Exception as exc:  # 单账号失败记录后继续
                entry["error"] = str(exc)[:300]
                print(f"       [FAIL] {entry['error']}")
            results["probes"] = [p for p in results["probes"] if p["creator_id"] != cid]
            results["probes"].append(entry)
            results["generated_at"] = utc_now()
            PROBE_OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
            done.append(cid)
            checkpoint_path.write_text(json.dumps({"done": done}, ensure_ascii=False),
                                       encoding="utf-8")
            processed += 1
            if processed % BATCH_SIZE == 0:
                print(f"[PAUSE] 已完成 {processed} 位，暂停 {BATCH_PAUSE_S} 秒")
                time.sleep(BATCH_PAUSE_S)
            else:
                time.sleep(PAGE_INTERVAL_S)
    finally:
        adapter.close()
    remaining = [c["creator_id"] for c in creators
                 if c["creator_id"] not in done and c["creator_id"] not in probed_ids]
    print(f"[DONE] 本轮处理 {processed} 位，剩余 {len(remaining)} 位")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
