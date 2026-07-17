# 组件准入审查报告：CAND-004 browser-mcp

- 核实日期：**2026-07-17**（所有证据均为当日实时抓取，见 `evidence/` 各文件内 `fetched_at` 时间戳）
- 评审结论：**rejected**（审定）
- 证据目录：`reports/component_reviews/evidence/`（下文引用均为相对 `reports/component_reviews/` 的相对路径）

---

## 1. 基本信息

| 项目 | 值 | 证据 |
| --- | --- | --- |
| 仓库 | https://github.com/BrowserMCP/mcp | evidence/BrowserMCP__mcp__meta.json |
| Owner | BrowserMCP（GitHub **Organization**） | 同上（owner_login / owner_type） |
| 默认分支 | `main` | 同上 |
| 最新提交 | 2025-04-24T21:49:35Z，短 sha `9db12f2`（"chore: version 0.1.3"） | 同上（latest_commit） |
| Star / Fork / Watch | 6,840 / 535 / 19 | 同上 |
| 是否归档 / 禁用 | 否 / 否 | 同上 |
| 语言 | TypeScript | 同上 |
| 创建 / 最近推送 | 2025-03-28 / 2025-04-24 | 同上（created_at / pushed_at）——**源码 14 个多月未提交** |
| Open issues（GitHub 计数，含 PR） | 142 | 同上（open_issues_count） |

## 2. 功能能力

MCP server + Chrome 扩展，让 AI 应用（VS Code、Claude、Cursor、Windsurf）**自动化控制用户本机真实浏览器**（evidence/BrowserMCP__mcp__readme_excerpt.md 第 17 行）：

- 读写操作：点击、输入、hover 等浏览器自动化（issue 标题"Read operations work but write operations (click, type, hover) fail..."佐证能力面，evidence/BrowserMCP__mcp__issues.md）
- 特点（README 第 21–24 行）：本地执行低延迟；隐私（不发送远程服务器）；**复用已登录浏览器 profile**；**"Stealth: Avoids basic bot detection and CAPTCHAs by using your real browser fingerprint"（规避基础机器人检测与验证码）**
- 改编自微软 Playwright MCP，但驱动用户现有浏览器而非新开实例，"to use logged-in sessions and avoid bot detection mechanisms that commonly block automated browser use"（第 32 行）

## 3. 安装方式

- README 仅 32 行，**无安装与构建说明**（readme_excerpt.md 全文，完整文件标记在第 34 行）
- **README 明示："currently cannot yet be built on its own due to dependencies on utils and types from the monorepo where it's developed"（第 28 行）——开源代码无法独立构建，可复现性缺失**
- 正式分发依赖闭源链路：browsermcp.io 网站 + docs.browsermcp.io + Chrome 扩展（第 1–12 行）
- 顶层文件：`package.json`、`tsconfig.json`、`src/`；无 Dockerfile（evidence/BrowserMCP__mcp__files.txt）

## 4. 权限范围

| 权限 | 是/否 | 证据 |
| --- | --- | --- |
| 执行 Shell | 未发现直接证据 | README 无相关描述 |
| **启动/控制浏览器** | **是（最高权限级）**——驱动用户本机真实 Chrome（经扩展），可点击/输入/hover，读写任意已登录页面 | readme_excerpt.md 第 17、32 行；issues.md |
| **读取登录态/Cookie** | **间接是**——直接使用浏览器 profile 的已登录会话（"Uses your existing browser profile, keeping you logged into all your services"） | readme_excerpt.md 第 23 行 |
| **监听本地端口** | **是**——MCP server 与扩展经 WebSocket 通信，issue 出现 9009 端口进程管理失败（"Failed to kill process on port 9009..."） | issues.md |
| 访问本地文件 | 未知——源码不可独立构建，无法从 README 判定 | readme_excerpt.md 第 28 行 |

## 5. 网络行为

- MCP server 与 Chrome 扩展之间经本地 WebSocket 通信（issues.md 中"MV3 service worker killed... WebSocket never reconnects"）
- 浏览器内发起的网络请求继承用户全部已登录会话，可触达任意网站
- 无证据表明向远程服务器回传浏览器活动（README 第 22 行声称本地执行、不外发），但因无法独立构建，**该声称无法审计验证**

## 6. 文件行为

- README 未描述文件读写行为；开源部分不可构建，无法静态确认（readme_excerpt.md 第 28 行）
- 作为浏览器自动化工具，页面下载/截图等行为取决于 AI 客户端发出的工具调用

## 7. 登录态行为

- **不自行管理登录**：完全复用用户现有浏览器 profile 中的已登录会话（readme_excerpt.md 第 23、32 行）
- 这意味着任何经 MCP 连接进来的 AI 客户端都继承用户在所有站点上的登录态权限

## 8. 许可证

- **Apache-2.0**：`license.spdx_id = "Apache-2.0"`（evidence/BrowserMCP__mcp__meta.json）
- **LICENSE 文件真实存在**：license API 返回 200，顶层含 `LICENSE`（evidence/BrowserMCP__mcp__license.json；evidence/BrowserMCP__mcp__files.txt）

## 9. 维护状态

- **源码停滞**：最新提交 2025-04-24（v0.1.3），至核实日 14 个多月无提交（meta.json）；issue「Browsermcp.dev is working but this repo is not」印证开源仓库与实际产品脱节（issues.md）
- open issue 总数（search API）：**125**（issues.md）
- **高频连接/功能失效类反馈**，代表性标题（同上）：
  - 「fails to load every time」
  - 「No connection to browser extension」
  - 「click always bad」
  - 「Read operations work but write operations (click, type, hover) fail with "No tab with given id"」
  - 「MV3 service worker killed on idle — popup shows stale 'Disconnect' state, WebSocket never reconnects」
- 另有 2 条安全相关 issue（"Preferred private channel for security report?"、"Security scan results..."）
- 无封号/风控类反馈（该工具面向通用浏览器自动化，非特定平台）

## 10. 风险

| 风险 | 等级 | 说明 |
| --- | --- | --- |
| **明示规避验证码/平台风控** | **极高（致命）** | README 卖点即 "Avoids basic bot detection and CAPTCHAs"，命中"存在绕过验证码或平台风控逻辑：直接 rejected"规则；用于小红书等平台场景即构成对抗平台风控 |
| 全登录态浏览器控制 | **高** | AI 客户端继承用户所有站点登录态 + 写操作（click/type），一旦被恶意提示注入利用，可在用户已登录的任意站点执行操作 |
| 不可独立构建/供应链不透明 | **高** | 依赖私有 monorepo，开源代码无法复现其正式分发物，审计断裂 |
| 源码停更 | 中-高 | 14 个多月无提交；125 个 open issue 大量失效反馈无人处理 |
| 扩展-服务通信健壮性 | 中 | MV3 service worker 被回收后 WebSocket 不重连等缺陷（issue 实证） |

## 11. 缓解措施

- **对本项目无有效缓解**：其"规避 bot 检测/验证码"为目的性设计而非可关闭的副作用，维持 rejected
- 如业务确需浏览器自动化：改用官方 Playwright MCP（新开隔离浏览器实例、不冒充用户指纹、不宣称规避检测），且不用于登录态采集
- 不安装其 Chrome 扩展到工作浏览器；如需试验使用独立测试浏览器 profile + 非生产账号

## 12. 输入输出

- 输入：MCP 工具调用（浏览器导航、点击、输入、hover、快照等，能力面见 issues.md 中 click/type/hover 相关 issue）
- 输出：操作结果与页面状态/快照返回给 AI 客户端
- 实际工具 schema 无法从开源部分完整确认（不可独立构建，readme_excerpt.md 第 28 行）

## 13. 测试计划（不适用——已 rejected；若未来重评时的预案）

1. 前置：项目移除/改写"规避 bot 检测与 CAPTCHA"逻辑与宣传，且开源代码可独立构建
2. 独立测试浏览器 profile + 专用测试账号，禁止接入日常工作浏览器
3. 审计 WebSocket 通道与扩展权限声明
4. 用提示注入用例测试写操作防护（确认操作前是否要求人工确认）

## 14. 替代方案

- microsoft/playwright-mcp（其上游母项目；新建隔离实例，不宣称规避检测，readme_excerpt.md 第 32 行提及其渊源）
- 官方 Playwright/Puppeteer 脚本（自有测试场景）
- 对平台数据采集：小红书官方开放平台 API

## 15. 评分（审定分数）

| 维度 | 权重 | 加权得分 | 依据要点 |
| --- | --: | --: | --- |
| 业务匹配度 | 25 | 8 | 通用浏览器自动化，非采集专用；规避检测方向与合规诉求冲突 |
| 输入输出兼容性 | 15 | 8 | 标准 MCP 接口，易接入 AI 客户端 |
| 可复现性和文档质量 | 10 | 3 | README 仅 32 行、无安装说明、明示不可独立构建 |
| 维护活跃度 | 10 | 1 | 源码 14 个多月未提交，125 个 open issue |
| 社区使用情况 | 10 | 7 | 6.8k star 知名度高，但 issue 反映实际可用性差 |
| 许可证可用性 | 10 | 10 | Apache-2.0 已核实，LICENSE 文件存在 |
| 安全性 | 10 | 1 | 明示规避验证码/检测 + 全登录态浏览器控制，风险极高 |
| 改造成本 | 5 | 2 | 无法独立构建，改造无从谈起 |
| 可替换性 | 5 | 3 | 有 playwright-mcp 等替代，但本组件独有能力即其风险点 |
| **总分** | 100 | **43** | — |

## 16. 准入建议

**rejected。** 理由（审定）：

1. README 明示 "avoids basic bot detection and CAPTCHAs"（readme_excerpt.md 第 24 行）→ **命中"存在绕过验证码或平台风控逻辑：直接 rejected"规则**；
2. 源码 14 个多月未提交（2025-04-24）且 README 声明无法独立构建（依赖私有 monorepo）；
3. open issue 高频连接/功能失效（「fails to load every time」「No connection to browser extension」等）；
4. Apache-2.0 许可证已核实（优点，但不足以改变结论）。

## 17. 证据链接

- GitHub 仓库：https://github.com/BrowserMCP/mcp
- 官方站点（README 所示）：https://browsermcp.io 、 https://docs.browsermcp.io
- 本地证据：
  - evidence/BrowserMCP__mcp__meta.json
  - evidence/BrowserMCP__mcp__license.json
  - evidence/BrowserMCP__mcp__readme_excerpt.md
  - evidence/BrowserMCP__mcp__issues.md
  - evidence/BrowserMCP__mcp__files.txt
