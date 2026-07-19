# 组件准入审查报告：CAND-012 nuwa-skill（参考组件）

- 核实日期：**2026-07-19**（证据为当日经 GitHub REST API 实时抓取，见 `evidence/` 内 `fetched_at` 时间戳）
- 评审结论：**reference_only（方法论参考，非 approved 执行组件）**
- 证据目录：`reports/component_reviews/evidence/`

---

## 1. 基本信息（来源核验）

| 项目 | 值 | 证据 |
| --- | --- | --- |
| 仓库 | https://github.com/alchaincyf/nuwa-skill | evidence/alchaincyf__nuwa-skill__meta.json |
| Owner | alchaincyf（GitHub User 账号） | 同上 |
| 默认分支 | `main` | 同上 |
| 固定 commit | `72857dc720f4d1dd3e68a40a544341dfc65ea33e`（main 最新提交） | 同上（latest_commit_sha，经 /commits?per_page=1 核验） |
| Star | 28282 | 同上 |
| 最近推送 | 2026-07-02 | 同上（pushed_at） |
| 描述 | "蒸馏任何人的思维方式——心智模型、决策启发式、表达DNA" | 同上 |

## 2. 用途定位

- 申请用途：达人表达DNA和风格蒸馏方法论（methodology_reference）
- 本项目仅参考其"风格蒸馏"方法论框架（如何从达人历史内容中归纳表达特征），用于设计 MCN 商单脚本 Agent 的达人风格分析 Prompt 与字段。
- **不引入其任何代码、SKILL.md 原文或模板文件。**

## 3. License 结论

- **MIT（已核实）**：GitHub API `license.spdx_id = "MIT"`（meta.json）
- 声称 MIT 与核验结果一致。

## 4. 安全结论

- 作为纯参考组件不执行、不安装，无直接攻击面。
- 风险点：方法论本身的主观性与"蒸馏任何人思维"的伦理/合规争议；个人 User 账号维护，无 SLA。
- 缓解：仅策划人员阅读参考；蒸馏输出物须经人工审校，不直接对外发布。

## 5. 使用限制

1. 禁止整体复制源码、SKILL.md、蒸馏模板进本仓库；
2. 仅允许吸收方法论思路后自研实现；
3. 如需引用其概念，在自研文档中以文字注明来源即可，不附原文。

## 6. 替代方案

- 自研达人风格分析维度（语气词、句式、emoji 习惯、选题偏好），以本项目 `data/processed/` 达人样本为语料；
- 学术化的文风分析（stylometry）公开方法论。

## 7. 准入定位

**reference_only。** 登记于 registry/component_candidates.csv 与 registry/THIRD_PARTY_NOTICES.md；不进入 approved_components.yaml。

## 8. 证据链接

- GitHub 仓库：https://github.com/alchaincyf/nuwa-skill
- 本地证据：evidence/alchaincyf__nuwa-skill__meta.json；evidence/alchaincyf__nuwa-skill__reverify.json（2026-07-19 复核：license.spdx_id=MIT、/license 200、commit SHA 一致、star 28282）
