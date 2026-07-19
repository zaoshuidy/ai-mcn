"""Stage 3 最终候选截图证据采集。

对 stage_3_final_10.json 中每位最终候选采集：
- 1 张主页截图 -> screenshots/stage_3_creators/{creator_id}_profile.jpg
- 每位 2 张代表笔记截图 -> screenshots/stage_3_notes/{creator_id}_{note_id}.jpg

规则：
- CDP 视口截图（天然不含浏览器框架区域），JPEG quality=60，单张<=300KB；
- 笔记 URL 使用主页笔记列表返回的 xsec_token 构造（canonical 直接访问会被 404）；
- 页面间隔 >=8 秒；验证码/登录门即停（退出码 5）；断点续跑幂等；
- 截图路径回写 stage_3_final_10.json 的 evidence_screenshot / profile_screenshot。

用法：python scripts/run_stage_3_screenshots.py [--max-per-run N]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from adapters.xhs_cdp_browser_adapter import (  # noqa: E402
    XhsCdpBrowserAdapter,
    XhsCdpReadonlyPolicy,
)

FINAL_JSON = PROJECT_ROOT / "data/processed/stage_3_final_10.json"
POLICY_PATH = PROJECT_ROOT / "config/xhs_cdp_readonly_policy.yaml"
CREATOR_DIR = PROJECT_ROOT / "screenshots/stage_3_creators"
NOTE_DIR = PROJECT_ROOT / "screenshots/stage_3_notes"
CHECKPOINT = PROJECT_ROOT / "tmp/stage_3_screenshots/checkpoint.json"

PAGE_INTERVAL_S = 8
JPEG_QUALITY = 60
MAX_BYTES = 300 * 1024
EXIT_CAPTCHA = 5


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def shoot(page, out_path: Path) -> int:
    """视口 JPEG 截图，返回字节数；超限时逐步降质量。"""
    for quality in (JPEG_QUALITY, 45, 30):
        page.screenshot(path=str(out_path), type="jpeg", quality=quality,
                        full_page=False)
        size = out_path.stat().st_size
        if size <= MAX_BYTES:
            return size
    return out_path.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-per-run", type=int, default=2)
    args = parser.parse_args()

    doc = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    finalists = doc["finalists"]
    CREATOR_DIR.mkdir(parents=True, exist_ok=True)
    NOTE_DIR.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    done: list[str] = []
    if CHECKPOINT.exists():
        done = json.loads(CHECKPOINT.read_text(encoding="utf-8")).get("done", [])

    policy = XhsCdpReadonlyPolicy.load(POLICY_PATH, PROJECT_ROOT)
    adapter = XhsCdpBrowserAdapter(policy, PROJECT_ROOT)
    if not adapter.chrome_reachable():
        print("[ERR] CDP 端点不可达，请先启动专用 Chrome")
        return 2
    adapter.connect()

    processed = 0
    try:
        for creator in finalists:
            cid = creator["creator_id"]
            if cid in done:
                continue
            if processed >= args.max_per_run:
                print(f"[BATCH] 本轮已达 {args.max_per_run} 位上限，断点已保存")
                break
            print(f"[SHOT] {creator['nickname']}")
            try:
                pages = adapter.all_pages()
                if not pages:
                    raise RuntimeError("专用 Chrome 中没有任何标签页")
                page = pages[0]
                adapter.soft_navigate_to(page, creator["profile_url"], "/user/profile/")
                time.sleep(4)
                gate = adapter.login_gate_state(page)
                if gate.get("gated"):
                    print("[STOP] 检测到登录门/验证码，保存断点并停止（退出码 5）")
                    CHECKPOINT.write_text(json.dumps({"done": done}, ensure_ascii=False),
                                          encoding="utf-8")
                    return EXIT_CAPTCHA
                profile_shot = CREATOR_DIR / f"{cid}_profile.jpg"
                size = shoot(page, profile_shot)
                creator["profile_screenshot"] = str(profile_shot.relative_to(PROJECT_ROOT))
                print(f"       profile -> {size // 1024}KB")
                notes_meta = {n.get("note_id"): n
                              for n in adapter.extract_profile_notes_xsec(page)
                              if n.get("note_id")}
                time.sleep(PAGE_INTERVAL_S)
                for note in creator.get("representative_notes", [])[:2]:
                    meta = notes_meta.get(note["note_id"], {})
                    url = note["canonical_url"]
                    if meta.get("xsec_token"):
                        url += f"?xsec_token={meta['xsec_token']}&xsec_source=pc_user"
                    adapter.soft_navigate_to(page, url, note["note_id"])
                    time.sleep(4)
                    gate = adapter.login_gate_state(page)
                    if gate.get("gated"):
                        print("[STOP] 笔记页触发登录门/验证码，断点停止（退出码 5）")
                        CHECKPOINT.write_text(
                            json.dumps({"done": done}, ensure_ascii=False), encoding="utf-8")
                        return EXIT_CAPTCHA
                    shot = NOTE_DIR / f"{cid}_{note['note_id']}.jpg"
                    size = shoot(page, shot)
                    note["evidence_screenshot"] = str(shot.relative_to(PROJECT_ROOT))
                    print(f"       note {note['note_id'][:12]} -> {size // 1024}KB")
                    time.sleep(PAGE_INTERVAL_S)
                creator["screenshots_captured_at"] = utc_now()
            except Exception as exc:  # 单账号失败记录后继续
                creator["screenshot_error"] = str(exc)[:300]
                print(f"       [FAIL] {creator['screenshot_error']}")
            done.append(cid)
            CHECKPOINT.write_text(json.dumps({"done": done}, ensure_ascii=False),
                                  encoding="utf-8")
            doc["generated_at"] = utc_now()
            FINAL_JSON.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
            processed += 1
    finally:
        adapter.close()
    remaining = [c["creator_id"] for c in finalists if c["creator_id"] not in done]
    print(f"[DONE] 本轮 {processed} 位，剩余 {len(remaining)} 位")
    return 0


if __name__ == "__main__":
    sys.exit(main())
