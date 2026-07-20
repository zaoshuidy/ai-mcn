# Component admission review: CAND-023 FFmpeg-high-star-reference

- Observed at: **2026-07-20T06:26:24Z**
- Decision: **primary** / **cli_runtime_reference**
- Evidence: `reports/component_reviews/evidence/github_api_snapshot.json`

## Verified facts

| Field | Value |
| --- | --- |
| Repository | https://github.com/FFmpeg/FFmpeg |
| Stars | 62210 |
| Fixed commit | `c23123630e6a7e645c199599b8ade3fe7e9ab3db` |
| Default branch | `master` |
| Pushed at | 2026-07-20T00:00:00Z |
| SPDX | NOASSERTION |
| Archived / fork | false / false |

## LICENSE file verification\n\nCOPYING.GPLv2, COPYING.GPLv3, COPYING.LGPLv2.1, COPYING.LGPLv3, and LICENSE.md were present; API SPDX is NOASSERTION.\n\n## Project mapping and boundary

Video metadata, frame extraction, scene detection, audio extraction, and output validation reference. CLI/subprocess only; no FFmpeg source is copied. GPL/LGPL obligations depend on the actual build, whose configuration must be recorded before use. Separate from CAND-008 Stage 2 POC.

No source, SKILL.md text, assets, or scripts are copied into this project. The component is a reference only and is not an approved runtime dependency. Security-sensitive browser capabilities (including stealth, CAPTCHA bypass, risk-control evasion, and unauthorized account actions) are excluded.
