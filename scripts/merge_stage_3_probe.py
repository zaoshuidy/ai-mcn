"""Stage 3 探测结果合并：把口播探测与视觉判定写回深核数据。

合并内容（全部标记 source/confidence，区分 page_observed 与 ai_inferred）：
1. 被探测代表笔记：has_voiceover（faster-whisper 实测）、has_on_screen_text（抽帧多模态判定）；
2. 被探测代表笔记：commercial_signal（视觉帧确认的商业植入，仅覆盖确认的 4 条）；
3. 达人级 primary_format：voiceover（真人口播/旁白型）或 subtitle_immersive（沉浸式字幕型）。

幂等：重复运行覆盖同名字段，不产生重复数据。
用法：python scripts/merge_stage_3_probe.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEEP_REVIEW = PROJECT_ROOT / "data/processed/stage_3_deep_review_15.json"
PROBE = PROJECT_ROOT / "data/processed/stage_3_format_probe.json"
VERDICTS = PROJECT_ROOT / "data/processed/stage_3_visual_verdicts.json"


def main() -> int:
    review = json.loads(DEEP_REVIEW.read_text(encoding="utf-8"))
    probes = {p["creator_id"]: p for p in json.loads(PROBE.read_text(encoding="utf-8"))["probes"]}
    verdicts = {v["creator_id"]: v
                for v in json.loads(VERDICTS.read_text(encoding="utf-8"))["verdicts"]}
    now = datetime.now(timezone.utc).isoformat()
    merged = 0
    for creator in review["creators"]:
        cid = creator["creator_id"]
        probe = probes.get(cid)
        verdict = verdicts.get(cid)
        if not probe or probe.get("error") or probe.get("has_voiceover") is None or not verdict:
            print(f"[SKIP] {creator['nickname']} 探测或判定不完整")
            continue
        has_voiceover = bool(probe["has_voiceover"])
        has_text = bool(verdict["has_on_screen_text"])
        for note in creator.get("representative_notes", []):
            if note["note_id"] == probe["note_id"]:
                note["has_voiceover"] = has_voiceover
                note["has_on_screen_text"] = has_text
                note["format_probe"] = {
                    "audio_model": probe.get("model"),
                    "spoken_chars_30s": probe.get("spoken_chars_30s"),
                    "visual_contact_sheet": verdict["evidence_contact_sheet"],
                    "source": "ai_inferred",
                    "confidence": 0.9,
                    "observed_at": now,
                }
                if verdict.get("probed_note_commercial_signal"):
                    note["commercial_signal"] = True
                    note["commercial_evidence"] = verdict.get("commercial_evidence")
                break
        creator["primary_format"] = "voiceover" if has_voiceover else "subtitle_immersive"
        creator["primary_format_source"] = "ai_inferred"
        creator["primary_format_confidence"] = 0.9
        creator["primary_format_evidence"] = (
            f"代表视频 {probe['note_id']} 前30秒口播字数="
            f"{probe.get('spoken_chars_30s')}（faster-whisper tiny实测）；"
            f"屏幕字幕={'有' if has_text else '无'}（抽帧视觉判定）"
        )
        merged += 1
    review["format_probe_merged_at"] = now
    DEEP_REVIEW.write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[DONE] 合并 {merged}/{len(review['creators'])} 位")
    vo = sum(1 for c in review["creators"] if c.get("primary_format") == "voiceover")
    sub = sum(1 for c in review["creators"] if c.get("primary_format") == "subtitle_immersive")
    print(f"       口播型 {vo} 位 / 沉浸字幕型 {sub} 位")
    return 0 if merged == len(review["creators"]) else 1


if __name__ == "__main__":
    sys.exit(main())
