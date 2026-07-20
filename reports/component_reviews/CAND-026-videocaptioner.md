# Component admission review: CAND-026 VideoCaptioner-high-star-reference

- Observed at: **2026-07-20T06:26:24Z**
- Decision: **primary** / **cli_runtime_reference**
- Evidence: `reports/component_reviews/evidence/github_api_snapshot.json`

## Verified facts

| Field | Value |
| --- | --- |
| Repository | https://github.com/WEIFENG2333/VideoCaptioner |
| Stars | 15368 |
| Fixed commit | `95842ecb5618c0b6a548a336bdfb0eb859bdb501` |
| Default branch | `master` |
| Pushed at | 2026-07-19T00:00:00Z |
| SPDX | GPL-3.0 |
| Archived / fork | false / false |

## LICENSE file verification\n\nLICENSE was present.\n\n## Project mapping and boundary

Local video transcription, subtitle generation, and correction reference. CLI only; no source copy or Python-source embedding. GPL is isolated through subprocess use. Separate from CAND-007 Stage 2 POC.

No source, SKILL.md text, assets, or scripts are copied into this project. The component is a reference only and is not an approved runtime dependency. Security-sensitive browser capabilities (including stealth, CAPTCHA bypass, risk-control evasion, and unauthorized account actions) are excluded.
