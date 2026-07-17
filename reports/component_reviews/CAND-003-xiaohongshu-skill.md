# 组件准入审查报告：CAND-003 xiaohongshu-skill

- 核实日期：**2026-07-17**（所有证据均为当日实时抓取，见 `evidence/` 各文件内 `fetched_at` 时间戳）
- 评审结论：**rejected**（审定）
- 证据目录：`reports/component_reviews/evidence/`（下文引用均为相对 `reports/component_reviews/` 的相对路径）

---

## 1. 基本信息

| 项目 | 值 | 证据 |
| --- | --- | --- |
| 仓库 | https://github.com/ibreez3/xiaohongshu-skill | evidence/ibreez3__xiaohongshu-skill__meta.json |
| Owner | ibreez3（GitHub **User** 账号） | 同上（owner_login / owner_type） |
| 默认分支 | `main` | 同上 |
| 最新提交 | 2026-02-01T14:30:47Z，短 sha `5928cc4`（"fix: 修复 Skill 加载卡住问题"） | 同上（latest_commit） |
| Star / Fork / Watch | 20 / 8 / 0 | 同上 |
| 是否归档 / 禁用 | 否 / 否 | 同上 |
| 语言 | JavaScript | 同上 |
| 创建 / 最近推送 | 2026-02-01 / 2026-02-01 | 同上（created_at / pushed_at）——**创建当天即最后一次推送** |
| Open issues（GitHub 计数） | 2 | 同上（open_issues_count） |

## 2. 功能能力

Xiaohongshu Auto-Publish Skill：面向 Cursor / Claude Code / Cline / OpenClaw 的插件，通过 xiaohongshu-mcp（CAND-001）服务端实现小红书自动化（evidence/ibreez3__xiaohongshu-skill__readme_excerpt.md 第 1–8 行）。功能列表（第 10–20 行）：

- **发布图文、发布视频**（发布为主）
- 检查登录状态并获取二维码
- 搜索内容、获取 feed 详情、首页 feed 列表、用户资料
- **发表评论、点赞与收藏**

**结论：能力偏向内容发布而非采集；且自身不含实现，全部操作依赖上游 CAND-001。**

## 3. 安装方式

- OpenClaw：`./install.sh`（快速安装）或手动拷贝 `index.js`、`openclaw.plugin.json`、`commands/`、`skills/` 到 `~/.openclaw/skills/xiaohongshu-auto-publish/` 并 `chmod +x`（readme_excerpt.md 第 143–195 行）
- OpenClaw 适配器模式：`./install-adapter.sh`（第 63–66 行）
- 标准 MCP 客户端：配置 `.cursor/mcp.json` 指向 `http://localhost:18060/mcp`（第 82–94 行）
- 前置条件：必须先部署并运行 xiaohongshu-mcp（CAND-001），**README 称其用 `npm install && npm start` 启动（第 127–139 行）——但 CAND-001 实为 Go 项目（含 go.mod，无 package.json），文档与上游实际技术栈不符，文档质量存疑**
- 运行环境：**Node.js 18+**（第 26 行）
- 顶层文件：`SKILL.md`、`package.json`、`index.js`、`adapter-mcp.js`、`adapter-server.js`、多个 install/uninstall shell 脚本及 15+ 个排障 md（evidence/ibreez3__xiaohongshu-skill__files.txt）

## 4. 权限范围

| 权限 | 是/否 | 证据 |
| --- | --- | --- |
| **执行 Shell** | **是（安装期）**——install.sh / install-adapter.sh / uninstall*.sh / cleanup-old-mcp.sh 等 shell 脚本，含拷贝文件与 `chmod +x` | readme_excerpt.md 第 147–195 行；files.txt |
| 启动浏览器 | 本身不启动；依赖的上游 CAND-001 启动无头浏览器 | readme_excerpt.md 第 24–25、123–141 行（全部操作依赖上游服务） |
| 读取 Cookie | 本身不直接读取；登录态由上游管理 | 同上 |
| 监听本地端口 | 含 `adapter-server.js`（OpenClaw HTTP API 适配器）；主链路为连接上游 `http://localhost:18060/mcp` | files.txt；readme_excerpt.md 第 6、54–74 行 |
| **访问/修改项目外文件** | **是**——向 `~/.openclaw/skills/` 写入文件；发布时读取本地图片绝对路径 | readme_excerpt.md 第 181–195 行 |

## 5. 网络行为

- 本身主要发起到本机 `http://127.0.0.1:18060/mcp` 的 HTTP/SSE 请求（readme_excerpt.md 第 89、108、139 行）
- 所有对小红书的外网访问均由上游 CAND-001 发起（第 123–141 行）
- 无证据表明向第三方服务器回传数据

## 6. 文件行为

- 安装时向 `~/.openclaw/skills/xiaohongshu-auto-publish/` 拷贝文件并赋可执行权限（readme_excerpt.md 第 181–195 行）
- 发布图文时读取本地图片路径（`/publish "标题" "内容" ["/path/img.jpg"]`，第 71 行）
- 含大量诊断/清理脚本（diagnose-mcp.js、cleanup-old-mcp.sh 等，files.txt）

## 7. 登录态行为

- 登录态完全继承上游 CAND-001：二维码扫码登录，登录状态由上游 cookies 文件保存（readme_excerpt.md 第 14 行"Check login status and get QR code"、第 58–72 行 `/check-login` 命令）
- 本身不保存登录态

## 8. 许可证

- **MIT**：`license.spdx_id = "MIT"`（evidence/ibreez3__xiaohongshu-skill__meta.json）
- **LICENSE 文件真实存在**：license API 返回 200，顶层含 `LICENSE`（evidence/ibreez3__xiaohongshu-skill__license.json；evidence/ibreez3__xiaohongshu-skill__files.txt）
- README 徽章同步标注 MIT（readme_excerpt.md 第 3 行）

## 9. 维护状态

- **几乎无维护**：仓库 2026-02-01 创建，最后一次提交/推送同为 2026-02-01（创建次日即停止），至核实日 5 个多月无任何更新（meta.json）
- open issue 总数（search API）：**2**（evidence/ibreez3__xiaohongshu-skill__issues.md）
- 无失效/风控类反馈；2 条均为使用咨询：「是不是需要修改openclaw.json的skills模块才能使用」「这个具备xiaohongshu mcp的全部功能吗？」——也反映文档不清晰
- 社区验证极弱：star 仅 20，watch 0（meta.json）

## 10. 风险

| 风险 | 等级 | 说明 |
| --- | --- | --- |
| 完全依赖 CAND-001（已被 rejected） | **高（致命）** | 上游无许可证 + 封号风控实证，本组件无任何独立价值 |
| 停止维护 | **高** | 创建次日即最后提交；上游 API 一旦变更即失效 |
| 业务方向不匹配 | **高** | 偏向内容发布（写）而非采集（读），与 MCN 脚本助手的主要诉求错位；发布能力反而带来合规风险 |
| 安装脚本修改用户主目录 | 低-中 | install.sh 向 `~/.openclaw/skills/` 写入并赋执行权限 |
| 文档质量 | 中 | README 启动命令（npm start）与上游 Go 技术栈不符，照做必然失败 |
| 社区验证缺失 | 中 | star 20 / watch 0，几乎无第三方使用检验 |

## 11. 缓解措施

- **不引入代码、不安装其脚本**；如需 Skill 形态能力，在上游合规方案确定后自行封装受限只读工具
- 阻断依赖链：CAND-001 已 rejected，本组件无可用上游，维持 rejected
- 若仅作方法参考：阅读其 OpenClaw/MCP 适配思路即可，不执行任何 install 脚本

## 12. 输入输出

- 输入：OpenClaw 斜杠命令（`/check-login`、`/publish "标题" "内容" ["/path/img.jpg"] ["标签"]`，readme_excerpt.md 第 69–72 行）；标准 MCP 客户端则通过 MCP 工具调用经 SSE/HTTP 转发到上游
- 输出：上游 xiaohongshu-mcp 的 JSON 响应（登录状态、二维码、发布/评论结果等），本组件仅做包装转发

## 13. 测试计划（若未来重评时的预案）

1. 前置：上游（CAND-001 或替代服务）必须先通过准入
2. 沙箱用户目录审查 install.sh 全部写入行为
3. 以 mock 上游验证 OpenClaw 命令与 MCP 适配层行为
4. 核查仓库是否恢复维护、README 与上游技术栈是否修正一致

## 14. 替代方案

- 在合规上游（官方开放平台/自研服务）之上自研轻量 Skill/命令封装
- 直接评估并使用合规上游的原生 MCP/CLI 接口，无需此中间包装层
- 人工发布流程（发布场景低频时可接受）

## 15. 评分（审定分数）

| 维度 | 权重 | 加权得分 | 依据要点 |
| --- | --: | --: | --- |
| 业务匹配度 | 25 | 10 | 偏向内容发布而非采集，方向错位 |
| 输入输出兼容性 | 15 | 8 | OpenClaw 命令与 MCP 包装尚可，但依赖上游才有意义 |
| 可复现性和文档质量 | 10 | 5 | 文档量大但与上游技术栈不符（npm start 错误） |
| 维护活跃度 | 10 | 1 | 创建次日即停更，5 个多月无提交 |
| 社区使用情况 | 10 | 1 | star 20、watch 0，几乎无采用 |
| 许可证可用性 | 10 | 10 | MIT 已核实，LICENSE 文件存在 |
| 安全性 | 10 | 5 | 本身攻击面小，但继承上游全部风险 + 安装脚本写主目录 |
| 改造成本 | 5 | 2 | 无独立实现，改造价值低 |
| 可替换性 | 5 | 2 | 仅是包装层，可替代性强但替代品同样依赖上游 |
| **总分** | 100 | **44** | — |

## 16. 准入建议

**rejected。** 理由（审定）：

1. 总分 44 < 85；
2. MIT 许可证已核实（优点）；
3. 功能偏向内容发布而非采集，业务方向不匹配；
4. **完全依赖 CAND-001（xpzouying/xiaohongshu-mcp），而 CAND-001 已被 rejected**，依赖链断裂；
5. 仓库创建次日（2026-02-01）即停止维护；star 仅 20；
6. 文档质量一般（README 的 `npm start` 启动命令与上游 Go 技术栈实际不符）。

## 17. 证据链接

- GitHub 仓库：https://github.com/ibreez3/xiaohongshu-skill
- 依赖的上游：https://github.com/xpzouying/xiaohongshu-mcp（CAND-001，已 rejected）
- 本地证据：
  - evidence/ibreez3__xiaohongshu-skill__meta.json
  - evidence/ibreez3__xiaohongshu-skill__license.json
  - evidence/ibreez3__xiaohongshu-skill__readme_excerpt.md
  - evidence/ibreez3__xiaohongshu-skill__issues.md
  - evidence/ibreez3__xiaohongshu-skill__files.txt
