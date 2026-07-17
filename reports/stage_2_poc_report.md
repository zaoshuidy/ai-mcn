# Stage 2 受控 POC 报告

日期：2026-07-17
结论：**自动化采集 POC 未执行**。原因：4 个候选组件在正式准入审查中全部 rejected，
无任何组件进入 POC 环节。本报告如实记录审查结论与替代路径，不伪造 POC 结果。

---

## 1. POC 前提检查

按任务书规定，组件进入 POC 需先完成准入审查并达到 `poc_required` 状态。
2026-07-17 对 4 个候选组件完成逐项真实核实（证据存于
`reports/component_reviews/evidence/`，审查报告存于 `reports/component_reviews/`）：

| 组件 | 最终分 | 状态 | 关键原因 |
| -- | --: | -- | -- |
| CAND-001 xiaohongshu-mcp | 74 | rejected | 无许可证；issue 高频封号/风控反馈；写权限 |
| CAND-002 xhs-cli | 69 | rejected | 维护停滞；登录失效 issue 集中；默认提取 Chrome cookie |
| CAND-003 xiaohongshu-skill | 44 | rejected | 偏发布；依赖已 rejected 的 CAND-001；创建次日停更 |
| CAND-004 browser-mcp | 43 | rejected | README 明示规避 bot 检测与验证码（硬性排除） |

4 个组件均未达到 85 分准入线，无人进入 `poc_required`，
因此**不存在可执行 POC 的组件**，自动化 POC 依法不执行。

## 2. 未执行项与原因

| 项目 | 是否执行 | 原因 |
| -- | -- | -- |
| 组件安装 | 否 | 无组件通过准入审查 |
| 登录态测试 | 否 | 无组件可安装 |
| 关键词自动搜索 | 否 | 无组件可安装 |
| 达人主页深读 | 否 | 无组件可安装 |
| Adapter 创建 | 否 | 任务书规定：无组件通过准入不得创建伪 Adapter |

## 3. 本阶段实际产出

虽未执行自动化 POC，以下 POC 前置资产已完成并可用：

1. **统一数据 Schema**：`src/creator_models.py` + `config/creator_schema.json`
   + `data/samples/creator_candidate_example.json`（虚构演示样例，已通过模型校验）；
2. **搜索策略**：`data/processed/creator_search_plan.json`
   （4 组 16 词，POC 子集 4 词 × 10 条 = 40 条，符合上限）；
3. **POC 边界规则**：`config/creator_search_rules.yaml`
   （上限、禁止行为、登录人工门禁、合规约束）；
4. **人工验证表**：`reports/creator_human_review_template.md`；
5. **空候选池**：`data/processed/creator_candidates_poc.json`
   （candidates 为空，注明未执行原因）。

## 4. 真实性与安全检查

| 检查项 | 结果 |
| -- | -- |
| 是否伪造 POC 成功 | 否，本报告明确记录未执行 |
| 是否产生虚构达人数据 | 否，候选池为空，样例文件明确标注虚构演示 |
| Cookie/Token/Session 是否进入 Git | 否，未安装任何组件，无登录态产生 |
| 是否执行点赞/评论/收藏/关注/私信 | 否 |
| 是否绕过验证码/风控 | 否（含绕过逻辑的 CAND-004 已直接 rejected） |
| 是否下载视频 | 否 |

## 5. 替代路径

1. **候选采集转人工执行**：人工执行者按 `creator_search_plan.json` 的
   POC 子集（4 词 × 10 条）在小红书网页端人工搜索，按
   `creator_human_review_template.md` 逐位核验后录入候选池；
2. **后续重新物色组件**：按 `rejected_components.yaml` 中
   `re_evaluation_condition` 跟踪上游变化，或评估新的只读采集组件，
   准入通过并完成真实 POC 后方可启用自动化采集。

## 6. 对最终达人定案的影响

`stage_2_final_selection_ready` 保持 `false` 不变。
本阶段不输出任何最终达人名单；候选池内所有未来条目默认
`human_verified=false`、`selection_status=poc_candidate`。
