"""Stage 3 自动验证脚本：真实达人采集与评分产出合规性。

检查候选池、深度核验、最终候选、Top3、风格研究对象、截图证据、
评分可复现性与安全边界。任何关键检查失败以非 0 退出码结束。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.stage_3_scoring import MIN_FORMAL_SCORE, score_creator  # noqa: E402

PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"

REQUIRED_FILES = [
    "data/raw/stage_3_search_log.json",
    "data/processed/stage_3_creator_pool.json",
    "data/processed/stage_3_prefiltered_30.json",
    "data/processed/stage_3_deep_review_15.json",
    "data/processed/stage_3_eliminated.json",
    "data/processed/stage_3_scores.json",
    "data/processed/stage_3_final_10.json",
    "data/processed/stage_3_top3.json",
    "data/processed/stage_3_style_reference.json",
    "data/processed/stage_3_evidence_manifest.json",
    "data/processed/stage_3_verification_events.json",
    "data/processed/stage_3_top3_video_timelines.json",
    "reports/stage_3_creator_research.md",
    "reports/stage_3_top3_video_summary.md",
]

CANONICAL_RE = re.compile(r"^https://www\.xiaohongshu\.com/explore/[0-9a-f]{24}$")
PROFILE_RE = re.compile(r"^https://www\.xiaohongshu\.com/user/profile/[0-9a-f]{24}$")
FORBIDDEN_SELECTION_STATUS = {
    "commercially_selected",
    "confirmed_collaboration",
    "brand_approved",
}
PLACEHOLDER_PATTERNS = re.compile(
    r"^(unknown|unnamed|匿名|未知|占位|placeholder|user[_\s]?\d*|达人\d*)$", re.IGNORECASE
)
SENSITIVE_PATTERNS = [
    re.compile(r"xsec_token\s*[=:]"),
    re.compile(r'"xsec_token"\s*:\s*"A'),
    re.compile(r"web_session"),
    re.compile(r"Set-Cookie", re.IGNORECASE),
]

errors: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    line = f"[{status}] {label}" + (f" — {detail}" if detail else "")
    print(line)
    if not ok:
        errors.append(line)


def load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def main() -> int:
    # 1. 必需文件存在
    for rel in REQUIRED_FILES:
        check(f"文件存在 {rel}", (ROOT / rel).is_file())
    if errors:
        print("\n缺少必需文件，终止后续检查。")
        return 1

    pool = load_json("data/processed/stage_3_creator_pool.json")
    deep = load_json("data/processed/stage_3_deep_review_15.json")
    scores = load_json("data/processed/stage_3_scores.json")
    final = load_json("data/processed/stage_3_final_10.json")
    top3 = load_json("data/processed/stage_3_top3.json")
    style_ref = load_json("data/processed/stage_3_style_reference.json")
    manifest = load_json("data/processed/stage_3_evidence_manifest.json")

    if isinstance(pool, dict):
        pool_creators = pool.get("creators") or pool.get("candidates") or []
    else:
        pool_creators = pool
    deep_creators = deep["creators"]
    finalists = final["finalists"]

    # 2. 数量约束
    check("原始候选 >= 20", len(pool_creators) >= 20, f"实际 {len(pool_creators)}")
    check("深度主页核验 >= 15", len(deep_creators) >= 15, f"实际 {len(deep_creators)}")
    check("最终候选 <= 10", len(finalists) <= 10, f"实际 {len(finalists)}")

    # 3. creator_id 唯一性
    pool_ids = [c["creator_id"] for c in pool_creators]
    check("候选池 creator_id 唯一", len(pool_ids) == len(set(pool_ids)))
    final_ids = [c["creator_id"] for c in finalists]
    check("最终候选 creator_id 唯一", len(final_ids) == len(set(final_ids)))

    # 4. 主页 URL 真实且含 /user/profile/，且与 creator_id 一致（非昵称拼接）
    for c in finalists:
        url = c.get("profile_url", "")
        check(f"{c['nickname']} profile_url 合法", bool(PROFILE_RE.match(url)), url)
        check(
            f"{c['nickname']} profile_url 含 creator_id（非昵称拼接）",
            c["creator_id"] in url,
        )

    # 5. 代表笔记：每位 >=2 篇、note_id 唯一、canonical 合法
    all_note_ids: list[str] = []
    for c in finalists:
        notes = c.get("representative_notes", [])
        check(f"{c['nickname']} 代表笔记 >= 2 篇", len(notes) >= 2, f"实际 {len(notes)}")
        for n in notes:
            nid = n.get("note_id", "")
            all_note_ids.append(nid)
            expected = f"https://www.xiaohongshu.com/explore/{nid}"
            check(
                f"笔记 {nid[:8]}… canonical 可构造且已清洗",
                CANONICAL_RE.match(n.get("canonical_url", "")) is not None
                and n["canonical_url"] == expected,
            )
    check(
        "全部代表笔记 note_id 唯一",
        len(all_note_ids) == len(set(all_note_ids)),
        f"{len(all_note_ids)} 条",
    )

    # 6. 无占位昵称
    for c in finalists:
        nick = (c.get("nickname") or "").strip()
        check(f"{nick or '<空>'} 昵称非占位", bool(nick) and not PLACEHOLDER_PATTERNS.match(nick))

    # 7. Top3 / 风格研究对象包含关系
    top3_ids = {c["creator_id"] for c in top3["top3"] if isinstance(c, dict)}
    if not top3_ids:  # 兼容其他结构
        top3_ids = {c["creator_id"] for c in top3.get("candidates", [])}
    check("Top3 属于最终候选", top3_ids <= set(final_ids), f"top3={len(top3_ids)}")
    style_id = style_ref.get("creator_id") or style_ref.get("style_reference", {}).get(
        "creator_id", ""
    )
    check("风格研究对象属于 Top3", style_id in top3_ids, style_id)

    # 8. selection_status 禁词（全部产出文件）
    def scan_status(obj, path=""):
        found = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "selection_status" and v in FORBIDDEN_SELECTION_STATUS:
                    found.append(f"{path}.{k}={v}")
                else:
                    found.extend(scan_status(v, f"{path}.{k}"))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                found.extend(scan_status(v, f"{path}[{i}]"))
        return found

    bad_status = []
    for name, data in (("final_10", final), ("top3", top3), ("style_reference", style_ref)):
        bad_status.extend(scan_status(data, name))
    check("无 commercial_selected 类禁词状态", not bad_status, "; ".join(bad_status[:3]))

    # 9. human_verified 全 false
    def all_human_verified_false(obj):
        flags = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "human_verified":
                    flags.append(v is False)
                else:
                    flags.extend(all_human_verified_false(v) if isinstance(v, (dict, list)) else [])
        elif isinstance(obj, list):
            for v in obj:
                flags.extend(all_human_verified_false(v))
        return flags

    hv = all_human_verified_false(finalists)
    check("最终候选 human_verified 全为 false", bool(hv) and all(hv), f"{sum(hv)}/{len(hv)}")

    # 10. page_observed 与 ai_inferred 分离
    deep_sources = {c.get("source") for c in deep_creators}
    check("深核页面事实 source=page_observed", deep_sources == {"page_observed"}, str(deep_sources))
    inf_sources = {c.get("audience_inference_source") for c in deep_creators}
    check(
        "受众推测 source=ai_inferred 且与页面事实分离",
        inf_sources == {"ai_inferred"},
        str(inf_sources),
    )

    # 11. 评分可复现：重跑 score_creator 与 stage_3_scores.json 一致
    saved = {x["creator_id"]: x["total"] for x in scores["scores"]}
    mismatches = []
    for c in deep_creators:
        r = score_creator(c)
        if saved.get(c["creator_id"]) != r["total"]:
            mismatches.append(c["nickname"])
    detail = f"不一致: {mismatches}" if mismatches else f"{len(saved)} 位一致"
    check("评分可复现（重算与存档一致）", not mismatches, detail)

    # 12. 低于 85 不得进入正式最终候选
    below = [
        c["nickname"]
        for c in finalists
        if (saved.get(c["creator_id"]) or 0) < MIN_FORMAL_SCORE
    ]
    check("最终候选全部 >= 85 分", not below, f"低于线: {below}" if below else "")

    # 13. 截图证据与 manifest 一致
    raw_shots = manifest.get("screenshots", {})
    if isinstance(raw_shots, dict):
        shot_entries = [e for group in raw_shots.values() for e in group]
    else:
        shot_entries = raw_shots
    missing_shots = [e["path"] for e in shot_entries if not (ROOT / e["path"]).is_file()]
    check("manifest 截图全部存在", not missing_shots, f"缺失 {len(missing_shots)} 张")
    final_shots = set()
    for c in finalists:
        if c.get("profile_screenshot"):
            final_shots.add(c["profile_screenshot"])
        for n in c.get("representative_notes", []):
            if n.get("evidence_screenshot"):
                final_shots.add(n["evidence_screenshot"])
    manifest_shots = {e["path"] for e in shot_entries}
    check(
        "final_10 截图路径与 manifest 一致",
        final_shots <= manifest_shots,
        f"final_10 引用 {len(final_shots)} 张 / manifest {len(manifest_shots)} 张",
    )

    # 14. 敏感信息扫描（Stage 3 全部入库 JSON 与截图清单）
    violations = []
    for rel in REQUIRED_FILES:
        if not rel.endswith(".json"):
            continue
        text = (ROOT / rel).read_text(encoding="utf-8")
        if rel.endswith("stage_3_evidence_manifest.json"):
            # manifest 的 sensitive_scan.patterns 是扫描器自身的模式声明，非数据内容
            m_obj = json.loads(text)
            scan_block = m_obj.get("sensitive_scan") or {}
            check(
                "manifest 敏感扫描结果为 0 违规",
                scan_block.get("violations", scan_block.get("violation_count", 0)) in (0, "0", []),
                json.dumps(scan_block, ensure_ascii=False)[:120],
            )
            m_obj.pop("sensitive_scan", None)
            text = json.dumps(m_obj, ensure_ascii=False)
        for pat in SENSITIVE_PATTERNS:
            for m in pat.finditer(text):
                ctx = text[max(0, m.start() - 30): m.end() + 10].replace("\n", " ")
                # 声明性文字（"不含xsec_token" / "xsec_token": null / false 标记）不算违规
                if re.search(r'(不含|未保存|无)\s*xsec_token', ctx) or re.search(
                    r'xsec_token"?\s*:\s*(null|false|"")', ctx
                ):
                    continue
                violations.append(f"{rel}: {ctx}")
    check("无 xsec_token/session/Cookie 入库", not violations, "; ".join(violations[:3]))

    # 15. 基础设施只读边界：适配器无写操作能力、无凭据导出
    adapter_src = (ROOT / "adapters" / "xhs_cdp_browser_adapter.py").read_text(encoding="utf-8")
    forbidden_caps = [
        r"\.click\(", r"\.fill\(", r"\.press\(", r"\.type\(",
        r"context\.cookies\(", r"storage_state\(",
    ]
    hits = [p for p in forbidden_caps if re.search(p, adapter_src)]
    check("CDP 适配器无写操作/凭据导出能力", not hits, f"命中: {hits}" if hits else "")
    check(
        "CDP 适配器不存在旧 navigate 公开入口",
        "def navigate(" not in adapter_src,
    )

    # 16. 风格研究对象视频证据：至少 1 条完整处理 + 共 3 条视频证据
    sr_body = style_ref.get("style_reference", style_ref)
    video_ev = sr_body.get("video_evidence", {})
    if isinstance(video_ev, dict):
        fully = video_ev.get("fully_processed_note_id")
        extra = video_ev.get("extra_video_page_evidence", [])
        ev_count = (1 if fully else 0) + len(extra)
        check("风格研究对象有 3 条视频证据", ev_count >= 3, f"实际 {ev_count}")
        check("风格研究对象至少 1 条完整管线处理", bool(fully), str(fully))
    else:
        check("风格研究对象有 3 条视频证据", len(video_ev) >= 3, f"实际 {len(video_ev)}")
        full_processed = [v for v in video_ev if v.get("processing") == "full_pipeline"]
        check("风格研究对象至少 1 条完整管线处理", len(full_processed) >= 1)

    # 17. Top3 视频时间线
    timelines = load_json("data/processed/stage_3_top3_video_timelines.json")
    tls = timelines.get("timelines", [])
    check("Top3 视频时间线 = 3 条", len(tls) == 3, f"实际 {len(tls)}")
    for tl in tls:
        check(
            f"时间线 {tl['note_id'][:8]}… 片段 >= 5",
            len(tl.get("segments", [])) >= 5,
            f"{tl.get('segments_count')} 段",
        )

    print()
    if errors:
        print(f"Stage 3 验证失败：{len(errors)} 项未通过。")
        return 1
    print("Stage 3 验证全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
