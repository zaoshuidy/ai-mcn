# 组件准入审查报告：CAND-001 xiaohongshu-mcp

- 核实日期：**2026-07-17**（所有证据均为当日实时抓取，见 `evidence/` 各文件内 `fetched_at` 时间戳）
- 评审结论：**rejected**（审定）
- 证据目录：`reports/component_reviews/evidence/`（下文引用均为相对 `reports/component_reviews/` 的相对路径）

---

## 1. 基本信息

| 项目 | 值 | 证据 |
| --- | --- | --- |
| 仓库 | https://github.com/xpzouying/xiaohongshu-mcp | evidence/xpzouying__xiaohongshu-mcp__meta.json |
| Owner | xpzouying（GitHub **User** 账号，非组织） | 同上（owner_login / owner_type） |
| 默认分支 | `main` | 同上（default_branch） |
| 最新提交 | 2026-06-29T02:07:48Z，短 sha `5c5197d`（"docs: Update WeChat QR code image in README"） | 同上（latest_commit） |
| Star / Fork / Watch | 14,714 / 2,176 / 34 | 同上 |
| 是否归档 / 禁用 | 否 / 否 | 同上（archived=false, disabled=false） |
| 语言 | Go | 同上（language） |
| 创建 / 最近推送 | 2025-08-03 / 2026-07-13 | 同上（created_at / pushed_at） |
| Open issues（GitHub 计数，含 PR） | 288 | 同上（open_issues_count） |

## 2. 功能能力

MCP for 小红书（xiaohongshu.com），让 AI 助手直接访问小红书数据（evidence/xpzouying__xiaohongshu-mcp__readme_excerpt.md 第 11 行）。README 列出的功能：

- 登录和检查登录状态（第 63–76 行）
- 发布图文内容（支持 HTTP 图片链接与本地绝对路径图片，第 78–109 行）
- 发布视频内容（本地视频文件，第 111–137 行）
- 搜索内容（第 139–148 行）
- 获取推荐列表（第 150–159 行）
- 获取帖子详情（互动数据：点赞、收藏、分享、评论数；评论列表及子评论，第 161–181 行）
- 发表评论到帖子（第 183–201 行）
- 回复评论、点赞/取消点赞（智能检测当前状态）（evidence/xpzouying__xiaohongshu-mcp__readme_full.md 第 233–265 行）
- 用户主页信息：关注数、粉丝数、获赞量统计（readme_full.md 第 214、227 行）

**结论：具备完整的读 + 写能力（发布图文/视频、评论、回复评论、点赞/取消点赞），无私信功能。**

## 3. 安装方式

三种方式（readme_full.md）：

1. **GitHub Releases 预编译二进制**直接下载运行（第 324–326 行）；首次运行**自动下载约 150MB 无头浏览器**（第 354 行）
2. **Go 源码编译**：依赖 Golang 环境，需配置 GOPROXY（第 359–380 行）
3. **Docker**：`docker pull xpzouying/xiaohongshu-mcp` 或 docker compose（第 380–435 行）；仓库顶层含 `Dockerfile`、`Dockerfile.arm64`、`docker/` 目录、`go.mod`/`go.sum`（evidence/xpzouying__xiaohongshu-mcp__files.txt）

## 4. 权限范围

| 权限 | 是/否 | 证据 |
| --- | --- | --- |
| 执行任意 Shell | 未发现 | README 全文无相关描述 |
| **启动浏览器** | **是**——默认无头模式（`-headless=false` 可切有界面），基于 rod 系无头浏览器，首次运行自动下载约 150MB | readme_full.md 第 354、465–479 行 |
| **读取/保存 Cookie** | **是**——登录态保存为 cookies 文件；Docker 版挂载 `./data` 存储 cookies 和运行数据；提供 `delete_cookies` 工具 | readme_full.md 第 431、851–852 行；files.txt 顶层含 `cookies/` 目录 |
| **监听本地端口** | **是**——默认监听 18060，MCP 端点 `http://localhost:18060/mcp` | readme_full.md 第 433、504、546 行 |
| **访问本地文件** | **是**——发布图文/视频需读取本地绝对路径图片/视频 | readme_excerpt.md 第 85–96、118–122 行 |
| 读取环境变量 | 是——支持 `XHS_PROXY` 代理环境变量 | readme_full.md 第 484–491 行 |

## 5. 网络行为

- 主动访问 xiaohongshu.com：登录、搜索、推荐、详情、发布、评论、点赞（readme_excerpt.md 功能列表）
- 首次运行联网下载约 150MB 无头浏览器（readme_full.md 第 354 行）
- 支持 `XHS_PROXY` 代理出站（readme_full.md 第 484 行）
- Docker 镜像从 Docker Hub 拉取（readme_full.md 第 387–396 行）
- 对外暴露 HTTP MCP 服务端点（18060 端口，局域网可访问时需注意绑定地址；README FAQ 提示非 Docker 环境用本机 IPv4 访问，readme_full.md 第 971–976 行）

## 6. 文件行为

- 读写本地数据目录（cookies、运行数据），Docker 版挂载 `./data`（readme_full.md 第 431 行）；顶层有 `cookies/` 目录（files.txt）
- 读取用户指定的本地图片/视频文件用于发布（readme_excerpt.md 第 93–96、118–122 行）
- 无证据表明会扫描或修改项目外文件

## 7. 登录态行为

- **必须登录才能使用核心功能**（readme_excerpt.md 第 66、175、196 行）
- **登录方式：二维码扫码**——`get_login_qrcode` 工具返回 Base64 二维码图片（readme_full.md 第 851 行）
- **登录态持久化**：保存为 cookies 文件，`delete_cookies` 可重置（readme_full.md 第 852 行）；作者自述"只有出现过 Cookies 过期需要重新登录"（readme_full.md 第 301 行）

## 8. 许可证

- **无任何开源许可证**：`license.spdx_id = null`（evidence/xpzouying__xiaohongshu-mcp__meta.json）
- **LICENSE 文件不存在**：GitHub license API 返回 **404「未找到 LICENSE 文件」**（evidence/xpzouying__xiaohongshu-mcp__license.json）
- 顶层文件列表中无 LICENSE / COPYING（evidence/xpzouying__xiaohongshu-mcp__files.txt）

**法律含义：无许可证即默认保留所有权利，使用、修改、再分发均未获授权，企业/商业场景不可合法引入。**

## 9. 维护状态

- 维护活跃：最新提交 2026-06-29，pushed_at 2026-07-13（meta.json）
- open issue 总数（search API，type:issue state:open）：**205**（evidence/xpzouying__xiaohongshu-mcp__issues.md）
- **issue 区高频出现封号/风控/失效类反馈**，代表性标题（同上文件）：
  - 「被小红书识别出来封号了」
  - 「今天被小红书弹了警告，建议大家不要使用这个 MCP 了」
  - 「最近使用mcp容易被封号」
  - 「使用了一天低强度抓数据，没有发帖被小红书警告了，应该是小红书程序员摸透了这个mcp的特征」
  - 「搜索文章做总结 被检测到使用脚本」
  - 「二维码过期」类多条（微信群二维码）

## 10. 风险

| 风险 | 等级 | 说明 |
| --- | --- | --- |
| 无开源许可证 | **高（致命）** | 使用/修改/分发无授权，合规上不可引入；命中"许可证不明确不能 approved"规则 |
| 平台风控与账号封禁连带 | **高** | issue 区集中出现封号、警告、被识别反馈；使用方账号（含 MCN 矩阵账号）有直接封禁风险 |
| 写操作能力 | **高** | 发布图文/视频、评论、回复、点赞，若被自动化滥用将违反平台规则并放大封号面 |
| 无头浏览器自动下载 | 中 | 首次运行下载约 150MB 二进制，供应链来源需审计 |
| cookies 本地保存 | 中 | 登录态以文件形式落盘，存在凭据泄露面 |
| 监听本地端口 | 低-中 | 18060 端口 HTTP 服务，未见鉴权描述，绑定非回环地址时风险上升 |

## 11. 缓解措施

- **不引入任何代码或二进制**；仅允许作为方法参考（reference），且需团队知悉其无许可证状态
- 如业务确需类似能力：优先评估小红书官方开放平台；或自研受限只读采集器（不登录或专用低权限账号 + 严格限速）
- 若仅做技术验证：隔离容器 + 专用测试小号 + 出站流量审计 + 不挂载真实数据目录
- 许可证缺失无法通过技术措施缓解 → 维持 rejected

## 12. 输入输出

- 输入：MCP 工具调用（JSON-RPC over HTTP，`http://localhost:18060/mcp`）；参数含关键词、`feed_id` + `xsec_token`、本地图片/视频绝对路径或 HTTP 图片链接、评论内容（readme_excerpt.md 第 85–96、171–198 行）
- 输出：MCP 工具 JSON 响应——登录二维码 Base64、搜索/推荐列表、帖子详情与评论、发布/评论/点赞操作结果（readme_full.md 第 851 行起工具列表）

## 13. 测试计划（若未来状态变化需重评时的预案）

1. 许可证复查：确认仓库是否补充 OSI 许可证
2. 隔离 Docker 部署，仅挂空数据目录；专用测试账号，严禁生产/矩阵账号
3. 先验只读路径（搜索、feed、详情），写操作默认禁用
4. 限速与行为频率监控；出现风控告警立即停止
5. 审计首次运行下载的无头浏览器二进制来源与哈希
6. 复核 issue 区封号反馈是否随版本收敛

## 14. 替代方案

- 小红书官方开放平台 API（合规首选）
- jackwener/xhs-cli（Apache-2.0；但本次评审亦为 rejected，见 CAND-002）
- 人工采集 + 表格整理（低量场景）
- 自研受限只读采集器（不登录/低权限账号 + 限速）

## 15. 评分（审定分数）

| 维度 | 权重 | 加权得分 | 依据要点 |
| --- | --: | --: | --- |
| 业务匹配度 | 25 | 23 | 读+写能力覆盖采集与互动，与 MCN 业务高度匹配 |
| 输入输出兼容性 | 15 | 13 | 标准 MCP/HTTP JSON，易接入 |
| 可复现性和文档质量 | 10 | 8 | 三种安装方式 + 视频演示，文档完整 |
| 维护活跃度 | 10 | 9 | 2026-06/07 仍在提交 |
| 社区使用情况 | 10 | 10 | 14.7k star、2.2k fork，采用面广 |
| 许可证可用性 | 10 | **0** | 无许可证、无 LICENSE 文件（license API 404） |
| 安全性 | 10 | 3 | 写权限 + 无头浏览器下载 + cookies 落盘 + 端口监听 + 封号实证 |
| 改造成本 | 5 | 4 | Go 代码结构清晰，易裁剪 |
| 可替换性 | 5 | 4 | 存在官方 API 与同类工具可替换 |
| **总分** | 100 | **74** | — |

## 16. 准入建议

**rejected。** 理由（审定）：

1. 无任何开源许可证（license 端点 404、无 LICENSE 文件）→ 命中"许可证不明确不能 approved"规则，且总分 74 < 85；
2. issue 区集中出现封号/风控反馈（见第 9 节具体标题），账号连带风险高；
3. 具备发布/评论/点赞写权限，自动化滥用风险大；
4. 首次运行下载约 150MB 无头浏览器、监听 18060 端口、二维码登录 + cookies 文件落盘，安全审计面大。

## 17. 证据链接

- GitHub 仓库：https://github.com/xpzouying/xiaohongshu-mcp
- license API（404）：https://api.github.com/repos/xpzouying/xiaohongshu-mcp/license
- 本地证据：
  - evidence/xpzouying__xiaohongshu-mcp__meta.json
  - evidence/xpzouying__xiaohongshu-mcp__license.json
  - evidence/xpzouying__xiaohongshu-mcp__readme_excerpt.md
  - evidence/xpzouying__xiaohongshu-mcp__readme_full.md
  - evidence/xpzouying__xiaohongshu-mcp__issues.md
  - evidence/xpzouying__xiaohongshu-mcp__files.txt
