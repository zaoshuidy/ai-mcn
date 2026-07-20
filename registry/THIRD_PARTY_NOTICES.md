# 第三方组件许可证与风险记录（Third-Party Notices）

> 任何第三方 Skill、GitHub 工具、库或代码片段在进入本项目前，必须先在
> `registry/` 完成准入评审，并在本文件追加一条记录。
>
> 当前状态：**无任何已批准的第三方组件，本文件暂无组件记录。**

## 记录要求

每个第三方组件必须记录以下信息：

1. **组件名称**：官方名称；
2. **仓库地址**：GitHub 或官方源地址；
3. **作者或组织**：作者/维护组织；
4. **许可证**：许可证类型（以仓库 LICENSE 文件原文为准）；
5. **使用方式**：直接依赖 / 代码借鉴 / 仅方法参考；
6. **修改情况**：是否修改、修改了哪些部分；
7. **版本或 Commit**：锁定的版本号或 commit hash；
8. **项目内使用位置**：引入到本项目的哪个目录/模块；
9. **许可证文本或链接**：LICENSE 全文链接或归档路径；
10. **风险说明**：安全风险、维护风险、许可证兼容性风险及缓解措施。

## 记录模板

```markdown
### [组件名称]

- 仓库地址：
- 作者或组织：
- 许可证：
- 使用方式：
- 修改情况：
- 版本或 Commit：
- 项目内使用位置：
- 许可证文本或链接：
- 风险说明：
- 准入评审记录：registry/component_scorecard.md 对应评分卡 / 决策日志编号
```

## 当前组件清单

（无）

## 准入审查记录（2026-07-17）

2026-07-17 对首批 4 个候选第三方组件完成准入审查（证据：reports/component_reviews/evidence/，当日实时抓取；评分卡：registry/component_scorecard.md；完整报告：reports/component_reviews/CAND-00X-*.md）。**4 个组件结论均为 rejected**，其代码、二进制、脚本均未进入本仓库，因此本文件无需添加任何许可证声明。

| 组件 ID | 仓库 | 结论 | 主要原因 |
| --- | --- | --- | --- |
| CAND-001 | xpzouying/xiaohongshu-mcp | rejected（总分 74） | **无任何开源许可证**（license API 404、无 LICENSE 文件）；issue 区集中封号/风控反馈；具备发布/评论/点赞写权限 |
| CAND-002 | jackwener/xhs-cli | rejected（总分 69） | 总分不足（< 85）；维护停滞（2026-03-14 后无提交）；登录失效类 issue；默认提取 Chrome cookie。Apache-2.0 已核实（优点） |
| CAND-003 | ibreez3/xiaohongshu-skill | rejected（总分 44） | 总分不足；偏向内容发布而非采集；完全依赖 CAND-001（已 rejected）；创建次日即停更；star 仅 20。MIT 已核实（优点） |
| CAND-004 | BrowserMCP/mcp | rejected（总分 43） | README 明示 "avoids basic bot detection and CAPTCHAs"，命中"绕过验证码或平台风控逻辑：直接 rejected"规则；源码 14 个多月未提交且无法独立构建。Apache-2.0 已核实（优点） |

说明：

1. 上述组件**未被使用、未被批准**，本项目不包含其任何代码或衍生内容；
2. 若未来重新引入其中任一组件（或其分叉），**必须重新完成准入评审**并在本文件追加记录后方可使用；
3. CAND-002 如在后续恢复活跃维护，可按评审结论备注重新发起评估。

## 参考组件登记（2026-07-19）

2026-07-19 对 6 个**参考类组件**完成静态准入审查（核验证据：reports/component_reviews/evidence/，当日经 GitHub REST API 实时抓取；完整报告：reports/component_reviews/CAND-012 至 CAND-017）。**6 个组件全部定位为 reference_only（方法论/结构参考），不是已批准执行组件**：其代码、SKILL.md 原文、规则文本均未进入、也不得整体复制进本仓库；仅允许吸收方法论与结构思路后自研实现。CAND-012~017 已登记于 registry/component_candidates.csv，**未进入 approved_components.yaml**。

### CAND-012 nuwa-skill（方法论参考）

- 仓库地址：https://github.com/alchaincyf/nuwa-skill
- 作者或组织：alchaincyf（GitHub User 账号）
- 许可证：**MIT（已核实，GitHub API license.spdx_id = "MIT"）**
- 使用方式：仅方法参考（达人表达DNA与风格蒸馏方法论，methodology_reference）
- 修改情况：不引入代码，无修改
- 版本或 Commit：`72857dc720f4d1dd3e68a40a544341dfc65ea33e`（main 分支最新，pushed_at 2026-07-02）
- 项目内使用位置：无（不进入项目目录）
- 许可证文本或链接：https://github.com/alchaincyf/nuwa-skill/blob/main/LICENSE
- 风险说明：社区热度极高（28282 star）但为 User 账号个人项目，方法论主观性强，蒸馏"任何人思维方式"的定位存在伦理/合规争议；缓解：仅由策划人员阅读参考，输出物须经人工审校
- 使用限制：禁止整体复制源码、SKILL.md 及蒸馏产物模板进项目；仅方法论参考
- 准入评审记录：reports/component_reviews/CAND-012-nuwa-skill.md；registry/component_candidates.csv CAND-012

### CAND-013 humanizer（改写规则参考）

- 仓库地址：https://github.com/blader/humanizer
- 作者或组织：blader（GitHub User 账号）
- 许可证：**MIT（已核实，GitHub API license.spdx_id = "MIT"）**
- 使用方式：仅方法参考（AI 写作模式识别、自然化、语气校准，adapted_skill_reference）
- 修改情况：不引入代码，无修改
- 版本或 Commit：`1b48564898e999219882660237fde01bf4843a0f`（main 分支最新，pushed_at 2026-06-29）
- 项目内使用位置：无（不进入项目目录）
- 许可证文本或链接：https://github.com/blader/humanizer/blob/main/LICENSE
- 风险说明：面向英文写作场景，中文语境适配度有限；个人账号维护，无 SLA；缓解：仅吸收模式识别思路，中文规则以自研为准（另见 CAND-014）
- 使用限制：禁止复制其 SKILL.md/规则清单原文进项目；仅模式识别思路参考
- 准入评审记录：reports/component_reviews/CAND-013-humanizer.md；registry/component_candidates.csv CAND-013

### CAND-014 Humanizer-zh（中文规则参考）

- 仓库地址：https://github.com/op7418/Humanizer-zh
- 作者或组织：op7418（GitHub User 账号）
- 许可证：**MIT（已核实，GitHub API license.spdx_id = "MIT"）**
- 使用方式：仅方法参考（中文自然化规则，chinese_rule_reference）
- 修改情况：不引入代码，无修改
- 版本或 Commit：`91f3d394db8419c20d67ebe22a96cf8fee0a404b`（main 分支最新，pushed_at 2026-01-19）
- 项目内使用位置：无（不进入项目目录）
- 许可证文本或链接：https://github.com/op7418/Humanizer-zh/blob/main/LICENSE
- 风险说明：最近推送 2026-01-19，近半年未更新，维护活跃度一般；为 CAND-013 的汉化衍生版本，需注意双层来源关系；缓解：仅规则思路参考，中文自然化规则由本项目自研
- 使用限制：禁止复制规则原文进项目；仅中文自然化规则设计思路参考
- 准入评审记录：reports/component_reviews/CAND-014-Humanizer-zh.md；registry/component_candidates.csv CAND-014

### CAND-015 ai-video-storyboard-skill（分镜结构参考）

- 仓库地址：https://github.com/aicontentskills/ai-video-storyboard-skill
- 作者或组织：aicontentskills（GitHub Organization 账号，2026-07-19 复核 owner.type = "Organization"）
- 许可证：**声称 MIT，未通过核验——GitHub API license 字段为 null，/license 端点返回 404，仓库无 LICENSE 文件，按无许可证处理**
- 使用方式：仅方法参考（镜头表、叙事弧、视听与后期字段设计，adapted_skill_reference）
- 修改情况：不引入代码，无修改
- 版本或 Commit：`93f8a6d6935858bc4acd7ff3bbea2411edf88caa`（main 分支最新，pushed_at 2026-04-09）
- 项目内使用位置：无（不进入项目目录）
- 许可证文本或链接：无（仓库未提供 LICENSE 文件）
- 风险说明：无许可证即默认保留所有权利，法律上连"阅读后模仿"的边界都需谨慎；star 仅 26，社区验证极弱；缓解：仅由策划人员浏览字段结构后自行设计本项目分镜字段，不留存其原文
- 使用限制：无许可证前提下更需严格限定——禁止任何形式的原文/结构原样复制；仅字段维度（如镜头号、景别、时长、后期项）的思路参考
- 准入评审记录：reports/component_reviews/CAND-015-ai-video-storyboard-skill.md；registry/component_candidates.csv CAND-015

### CAND-016 video-script-developer-gist（脚本结构参考）

- 仓库地址：https://gist.github.com/alexknowshtml/6a1e4d336a6d51c6231bd6bd9a3f0d17
- 作者或组织：alexknowshtml（GitHub User 账号）
- 许可证：**无许可证——GitHub Gist 无许可证机制，该 Gist 未附带 LICENSE，按默认保留所有权利处理**
- 使用方式：仅方法参考（Hook—Story—Landing 短视频脚本结构，structure_reference_only）
- 修改情况：不引入代码，无修改
- 版本或 Commit：Gist id `6a1e4d336a6d51c6231bd6bd9a3f0d17`（updated_at 2026-02-17T00:40:03Z）
- 项目内使用位置：无（不进入项目目录）
- 许可证文本或链接：无（Gist 未提供许可证）
- 风险说明：Gist 为个人笔记性质，无许可证、无版本承诺、可随时修改或删除；Hook—Story—Landing 为行业通用结构范式，概念层面参考无版权问题，但逐字复用其表述存在风险；缓解：仅参考结构概念，脚本模板由本项目自研
- 使用限制：禁止复制 Gist 原文进项目；仅 Hook—Story—Landing 结构概念参考
- 准入评审记录：reports/component_reviews/CAND-016-video-script-developer-gist.md；registry/component_candidates.csv CAND-016

### CAND-017 langgraph（编排框架参考）

- 仓库地址：https://github.com/langchain-ai/langgraph
- 作者或组织：LangChain, Inc.（GitHub Organization：langchain-ai）
- 许可证：**MIT（已核实，GitHub API license.spdx_id = "MIT"）**
- 使用方式：仅方法参考（Agent 状态编排、失败回退、Human-in-the-loop 机制，orchestration_framework）
- 修改情况：不引入代码，无修改
- 版本或 Commit：`49ae27c2ae983cfb92091b0dea9f7bc37a716479`（main 分支最新，pushed_at 2026-07-19）
- 项目内使用位置：无（不进入项目目录；如未来作为运行时 pip 依赖引入，须另行发起执行组件评审）
- 许可证文本或链接：https://github.com/langchain-ai/langgraph/blob/main/LICENSE
- 风险说明：组织化维护、当日活跃（37596 star），风险低；主要风险在于若日后引入为依赖会带来较重的依赖树（langchain 生态）；缓解：当前仅登记为方法论参考，引入运行时依赖前必须重新评审
- 使用限制：当前仅方法论/API 思路参考，禁止复制源码进项目；任何 pip 依赖引入须另行评审
- 准入评审记录：reports/component_reviews/CAND-017-langgraph.md；registry/component_candidates.csv CAND-017

说明：

1. 上述 6 个组件均为 **reference_only 参考组件，不是已批准执行组件**，本项目不包含其任何代码或衍生内容；
2. 其中 CAND-015 声称的 MIT **未通过核验**（无 LICENSE 文件）、CAND-016 为无许可证 Gist，两者仅限概念/结构层面参考；
3. 若未来任一参考组件要转为代码引入或运行时依赖，**必须重新完成执行组件准入评审**并在本文件更新记录后方可使用。


## 高星参考登记（2026-07-20）

CAND-018～026 已完成 GitHub API 证据登记，均为 `reference_only`，未进入 approved/rejected 运行准入 YAML。CAND-018 因无 LICENSE 拒绝 primary；其余组件仅按 CSV 的 integration_type 作为方法、框架或 CLI 隔离参考，禁止复制源码或 SKILL.md 原文。
