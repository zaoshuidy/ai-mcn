# 组件准入审查报告：CAND-014 Humanizer-zh（参考组件）

- 核实日期：**2026-07-19**（证据为当日经 GitHub REST API 实时抓取，见 `evidence/` 内 `fetched_at` 时间戳）
- 评审结论：**reference_only（中文规则参考，非 approved 执行组件）**
- 证据目录：`reports/component_reviews/evidence/`

---

## 1. 基本信息（来源核验）

| 项目 | 值 | 证据 |
| --- | --- | --- |
| 仓库 | https://github.com/op7418/Humanizer-zh | evidence/op7418__Humanizer-zh__meta.json |
| Owner | op7418（GitHub User 账号） | 同上 |
| 默认分支 | `main` | 同上 |
| 固定 commit | `91f3d394db8419c20d67ebe22a96cf8fee0a404b`（main 最新提交） | 同上（latest_commit_sha，经 /commits?per_page=1 核验） |
| Star | 13445 | 同上 |
| 最近推送 | 2026-01-19 | 同上（pushed_at）——近半年未更新 |
| 描述 | "Humanizer 的汉化版本，Claude Code Skills，旨在消除文本中 AI 生成的痕迹" | 同上 |

## 2. 用途定位

- 申请用途：中文自然化规则参考（chinese_rule_reference）
- 本项目参考其中文 AI 痕迹消除规则的设计思路（中文特有的 AI 腔调、连接词滥用、三段式结构等），用于商单脚本中文表达质量门。
- **不引入其任何代码、SKILL.md 原文或规则清单。**

## 3. License 结论

- **MIT（已核实）**：GitHub API `license.spdx_id = "MIT"`（meta.json）
- 任务中标注"许可证需核验"——核验通过，确认为 MIT。

## 4. 安全结论

- 作为纯参考组件不执行、不安装，无直接攻击面。
- 风险点：最近推送 2026-01-19，近半年未更新，维护活跃度一般；为 CAND-013（blader/humanizer）的汉化衍生版本，存在双层来源关系，规则可能滞后于上游。
- 缓解：仅规则思路参考，中文自然化规则由本项目基于小红书语料自研。

## 5. 使用限制

1. 禁止复制规则原文进本仓库；
2. 仅中文自然化规则设计思路参考；
3. 与 CAND-013 的关系仅为"参考链"记录，不构成对任一组件的代码引入。

## 6. 替代方案

- 本项目 skills/humanizer-zh 已有基于维基百科"AI 写作特征"指南的中文规则路线；
- 基于真实小红书达人语料的自研规则迭代。

## 7. 准入定位

**reference_only。** 登记于 registry/component_candidates.csv 与 registry/THIRD_PARTY_NOTICES.md；不进入 approved_components.yaml。

## 8. 证据链接

- GitHub 仓库：https://github.com/op7418/Humanizer-zh
- 上游关联：https://github.com/blader/humanizer（CAND-013）
- 本地证据：evidence/op7418__Humanizer-zh__meta.json；evidence/op7418__Humanizer-zh__reverify.json（2026-07-19 复核：MIT、/license 200、commit SHA 一致、star 13445）
