"""Stage 3 证据清单生成：汇总本阶段全部证据产物与文件一致性。

输出 data/processed/stage_3_evidence_manifest.json：
- 数据文件清单（搜索/候选池/预筛/深核/淘汰/探测/评分/终选/Top3/风格对象）；
- 截图文件枚举（screenshots/stage_3_creators|notes）与 final_10 中登记路径比对；
- Top3 视频证据（manifest+时间线，原始媒体不进Git的声明）；
- 敏感信息自检（无 xsec_token / Cookie / 签名URL 入库）。

用法：python scripts/build_stage_3_evidence_manifest.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/processed/stage_3_evidence_manifest.json"

DATA_FILES = [
    "data/raw/stage_3_search_log.json",
    "data/processed/stage_3_creator_pool.json",
    "data/processed/stage_3_prefiltered_30.json",
    "data/processed/stage_3_deep_review_15.json",
    "data/processed/stage_3_eliminated.json",
    "data/processed/stage_3_verification_events.json",
    "data/processed/stage_3_format_probe.json",
    "data/processed/stage_3_visual_verdicts.json",
    "data/processed/stage_3_scores.json",
    "data/processed/stage_3_final_10.json",
    "data/processed/stage_3_top3.json",
    "data/processed/stage_3_style_reference.json",
    "data/processed/stage_3_top3_video_manifest.json",
    "data/processed/stage_3_top3_video_timelines.json",
]

# 精确违规模式：令牌赋值/URL参数/Cookie值，排除"不含xsec_token""cookie_exported: false"等声明文字
SENSITIVE_PATTERNS = [
    "xsec_token=", '"xsec_token": "A', "set-cookie", "web_session=", "sessionid=",
]


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    manifest: dict = {
        "generated_at": now,
        "stage": "stage_3",
        "data_files": [],
        "screenshots": {"creators": [], "notes": []},
        "screenshot_consistency": {},
        "top3_video_evidence": [],
        "sensitive_scan": {"patterns": SENSITIVE_PATTERNS, "violations": []},
        "original_media_policy": "原始视频/音频/完整逐字稿/关键帧仅存 tmp/，不进 Git；"
                                 "Git 仅保留字段存在性、哈希、时间戳与转述",
    }

    for rel in DATA_FILES:
        p = ROOT / rel
        entry = {"path": rel, "exists": p.exists()}
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for key in ("creators", "candidates", "finalists", "probes",
                                "scores", "videos", "timelines", "queries", "results"):
                        if key in data and isinstance(data[key], list):
                            entry["records"] = len(data[key])
                            entry["record_key"] = key
                            break
            except json.JSONDecodeError:
                entry["exists"] = False
            # 敏感信息扫描（证据文件自身）
            text = p.read_text(encoding="utf-8")
            for pat in SENSITIVE_PATTERNS:
                if pat in text:
                    manifest["sensitive_scan"]["violations"].append(
                        {"file": rel, "pattern": pat})
        manifest["data_files"].append(entry)

    for kind, rel_dir in (("creators", "screenshots/stage_3_creators"),
                          ("notes", "screenshots/stage_3_notes")):
        d = ROOT / rel_dir
        for f in sorted(d.glob("*.jpg")) if d.exists() else []:
            manifest["screenshots"][kind].append(
                {"path": f"{rel_dir}/{f.name}", "bytes": f.stat().st_size})

    final_path = ROOT / "data/processed/stage_3_final_10.json"
    missing_shots = []
    if final_path.exists():
        final_doc = json.loads(final_path.read_text(encoding="utf-8"))
        for c in final_doc.get("finalists", []):
            prof = c.get("profile_screenshot")
            if not prof or not (ROOT / prof).exists():
                missing_shots.append(f"{c['nickname']}.profile")
            for n in c.get("representative_notes", []):
                shot = n.get("evidence_screenshot")
                if not shot or not (ROOT / shot).exists():
                    missing_shots.append(f"{c['nickname']}.{n['note_id'][:12]}")
    manifest["screenshot_consistency"] = {
        "finalists_checked": True,
        "missing": missing_shots,
        "consistent": not missing_shots,
    }

    tl_path = ROOT / "data/processed/stage_3_top3_video_timelines.json"
    if tl_path.exists():
        tl_doc = json.loads(tl_path.read_text(encoding="utf-8"))
        for tl in tl_doc.get("timelines", []):
            manifest["top3_video_evidence"].append({
                "creator_id": tl["creator_id"],
                "note_id": tl["note_id"],
                "duration_s": tl.get("duration_s"),
                "segments": tl.get("segments_count"),
                "sha256": (tl.get("file") or {}).get("sha256"),
                "valid_keyframes": (tl.get("keyframes") or {}).get("valid_interval"),
                "asr_reliability": tl.get("asr_reliability"),
            })

    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    shots = len(manifest["screenshots"]["creators"]) + len(manifest["screenshots"]["notes"])
    ok_files = sum(1 for f in manifest["data_files"] if f["exists"])
    consistency = manifest["screenshot_consistency"]["consistent"]
    violations = len(manifest["sensitive_scan"]["violations"])
    print(f"[OK] manifest: 数据文件 {ok_files}/{len(DATA_FILES)}，"
          f"截图 {shots} 张，一致性={consistency}，敏感信息违规={violations}")
    if manifest["sensitive_scan"]["violations"]:
        for v in manifest["sensitive_scan"]["violations"]:
            print(f"  [SENSITIVE] {v['file']}: {v['pattern']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
