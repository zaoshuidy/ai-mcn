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
