# 组件准入审查报告：CAND-015 ai-video-storyboard-skill（参考组件）

- 核实日期：**2026-07-19**（证据为当日经 GitHub REST API 实时抓取，见 `evidence/` 内 `fetched_at` / `reverify_at` 时间戳）
- 评审结论：**reference_only（分镜结构参考，非 approved 执行组件）**
- 证据目录：`reports/component_reviews/evidence/`

---

## 1. 基本信息（来源核验）

| 项目 | 值 | 证据 |
| --- | --- | --- |
| 仓库 | https://github.com/aicontentskills/ai-video-storyboard-skill | evidence/aicontentskills__ai-video-storyboard-skill__meta.json |
| Owner | aicontentskills（GitHub Organization 账号，2026-07-19 复核 owner.type = "Organization"） | 同上；evidence/aicontentskills__ai-video-storyboard-skill__reverify.json |
| 默认分支 | `main` | 同上 |
| 固定 commit | `93f8a6d6935858bc4acd7ff3bbea2411edf88caa`（main 最新提交，commit date 2026-04-09T13:51:37Z） | 同上（latest_commit_sha，经 /commits?per_page=1 核验；2026-07-19 复核一致） |
| Star | 26 | 同上（2026-07-19 复核仍为 26） |
| 最近推送 | 2026-04-09 | 同上（pushed_at） |

## 2. 用途定位

- 申请用途：镜头表 / 叙事弧 / 视听与后期字段设计参考（adapted_skill_reference）
- 本项目仅参考其分镜字段维度（如镜头号、景别、时长、画面、台词、后期项等），用于设计 MCN 商单脚本 Agent 的分镜脚本输出结构。
- **不引入其任何代码、SKILL.md 原文或模板文件。**

## 3. License 结论

- **声称 MIT，未通过核验，按无许可证处理**：
  - GitHub API 仓库元数据 `license = null`（meta.json；2026-07-19 复核仍为 null）；
  - `/license` 端点返回 **404 Not Found**（2026-07-19 复核 reverify.json：`license_endpoint_http = 404`），即仓库无 LICENSE 文件。
- 无许可证即默认保留所有权利，"声称 MIT"无任何法律凭据。

## 4. 安全结论

- 作为纯参考组件不执行、不安装，无直接攻击面。
- 风险点：无许可证下连"阅读后模仿"的边界都需谨慎；star 仅 26，社区验证极弱；内容质量与专业性无第三方背书。
- 缓解：仅由策划人员浏览字段结构后**自行设计**本项目分镜字段，不留存、不转贴其原文。

## 5. 使用限制

1. 无许可证前提下严格限定：禁止任何形式的原文、结构原样复制进本仓库；
2. 仅允许参考"字段维度"层面的思路（镜头号 / 景别 / 时长 / 后期项等通用概念），字段命名与模板由本项目自研；
3. 如未来其补充了可核验的开源许可证，可重新评估参考深度。

## 6. 替代方案

- 影视/广告行业通用的分镜表（storyboard）字段范式，属公共领域方法论；
- 自研分镜字段：结合本项目 `data/processed/stage_3_top3_video_timelines.json` 中 3 条真实视频时间线的结构归纳。

## 7. 准入定位

**reference_only。** 登记于 registry/component_candidates.csv 与 registry/THIRD_PARTY_NOTICES.md；不进入 approved_components.yaml。

## 8. 证据链接

- GitHub 仓库：https://github.com/aicontentskills/ai-video-storyboard-skill
- 本地证据：evidence/aicontentskills__ai-video-storyboard-skill__meta.json（2026-07-19 首次抓取）、evidence/aicontentskills__ai-video-storyboard-skill__reverify.json（2026-07-19 复核：license=null、/license 404、commit SHA 一致）


## 2026-07-20 demotion

This historical review is retained for traceability. `CAND-015` is **demoted** and must not be used as a primary reference: Demoted: only 26 stars and no verifiable LICENSE; historical review is retained for traceability.
