"""一次性修复：将 stage_3_final_10.json 中的 Windows 反斜杠路径规范为正斜杠。"""

import json
from pathlib import Path

p = Path("data/processed/stage_3_final_10.json")
d = json.loads(p.read_text(encoding="utf-8"))
n = 0
for c in d["finalists"]:
    if c.get("profile_screenshot") and "\\" in c["profile_screenshot"]:
        c["profile_screenshot"] = c["profile_screenshot"].replace("\\", "/")
        n += 1
    for note in c.get("representative_notes", []):
        if note.get("evidence_screenshot") and "\\" in note["evidence_screenshot"]:
            note["evidence_screenshot"] = note["evidence_screenshot"].replace("\\", "/")
            n += 1
p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"normalized {n} paths")
