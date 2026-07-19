# 组件准入审查报告：CAND-013 humanizer（参考组件）

- 核实日期：**2026-07-19**（证据为当日经 GitHub REST API 实时抓取，见 `evidence/` 内 `fetched_at` 时间戳）
- 评审结论：**reference_only（改写规则参考，非 approved 执行组件）**
- 证据目录：`reports/component_reviews/evidence/`

---

## 1. 基本信息（来源核验）

| 项目 | 值 | 证据 |
| --- | --- | --- |
| 仓库 | https://github.com/blader/humanizer | evidence/blader__humanizer__meta.json |
| Owner | blader（GitHub User 账号） | 同上 |
| 默认分支 | `main` | 同上 |
| 固定 commit | `1b48564898e999219882660237fde01bf4843a0f`（main 最新提交） | 同上（latest_commit_sha，经 /commits?per_page=1 核验） |
| Star | 29868 | 同上 |
| 最近推送 | 2026-06-29 | 同上（pushed_at） |
| 描述 | "Claude Code skill that removes signs of AI-generated writing from text" | 同上 |

## 2. 用途定位

- 申请用途：AI 写作模式识别、自然化、语气校准（adapted_skill_reference）
- 本项目参考其 AI 痕迹识别模式（如夸大象征、宣传性语言、AI 高频词汇、否定式排比等），用于商单脚本的"去 AI 味"质量门设计。
- **不引入其任何代码、SKILL.md 原文或规则清单。**

## 3. License 结论

- **MIT（已核实）**：GitHub API `license.spdx_id = "MIT"`（meta.json）
- 声称 MIT 与核验结果一致。

## 4. 安全结论

- 作为纯参考组件不执行、不安装，无直接攻击面。
- 风险点：面向英文写作场景，中文语境适配度有限；个人账号维护。
- 缓解：中文自然化规则以自研为准，另参考 CAND-014（Humanizer-zh）的中文适配思路。

## 5. 使用限制

1. 禁止复制其 SKILL.md/规则清单原文进本仓库；
2. 仅吸收模式识别思路，规则表述须自研重写；
3. 本项目 skills/ 下已有中文 humanizer 能力时，以本项目自研规则为准。

## 6. 替代方案

- 本项目自研中文自然化规则（基于小红书真实达人语料）；
- 维基百科"AI 写作特征"类公开指南（本项目 skills/humanizer-zh 已采用此路线）。

## 7. 准入定位

**reference_only。** 登记于 registry/component_candidates.csv 与 registry/THIRD_PARTY_NOTICES.md；不进入 approved_components.yaml。

## 8. 证据链接

- GitHub 仓库：https://github.com/blader/humanizer
- 本地证据：evidence/blader__humanizer__meta.json；evidence/blader__humanizer__reverify.json（2026-07-19 复核：MIT、/license 200、commit SHA 一致；star 由登记时 29868 增至 29870，属正常漂移，固定 commit 不变）
