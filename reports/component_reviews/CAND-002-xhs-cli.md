# 组件准入审查报告：CAND-002 xhs-cli

- 核实日期：**2026-07-17**（所有证据均为当日实时抓取，见 `evidence/` 各文件内 `fetched_at` 时间戳）
- 评审结论：**rejected**（审定）
- 证据目录：`reports/component_reviews/evidence/`（下文引用均为相对 `reports/component_reviews/` 的相对路径）

---

## 1. 基本信息

| 项目 | 值 | 证据 |
| --- | --- | --- |
| 仓库 | https://github.com/jackwener/xhs-cli | evidence/jackwener__xhs-cli__meta.json |
| Owner | jackwener（GitHub **User** 账号） | 同上（owner_login / owner_type） |
| 默认分支 | `main` | 同上 |
| 最新提交 | 2026-03-14T12:23:52Z，短 sha `3ce7141`（"ci: remove deprecated ClawHub publish workflow"） | 同上（latest_commit） |
| Star / Fork / Watch | 611 / 62 / 0 | 同上 |
| 是否归档 / 禁用 | 否 / 否 | 同上 |
| 语言 | Python | 同上 |
| 创建 / 最近推送 | 2026-03-04 / 2026-03-14 | 同上（created_at / pushed_at） |
| Open issues（GitHub 计数，含 PR） | 8 | 同上（open_issues_count） |

## 2. 功能能力

小红书命令行工具——在终端中搜索笔记、查看主页、点赞、收藏、评论（evidence/jackwener__xhs-cli__readme_excerpt.md 第 11 行）：

- 读：关键词搜索、笔记详情与评论、用户资料/笔记/粉丝/关注、推荐 Feed、话题搜索（第 20–24 行）
- **写：点赞/取消、收藏/取消、评论、删除笔记、发布图文笔记**（第 25–26、38–40 行）
- 认证：自动提取 Chrome cookie 或 browser-assisted 扫码登录（终端二维码渲染）（第 27 行）
- 所有数据命令支持 `--json` 输出；`xsec_token` 搜索后自动缓存（第 28–29 行）

README 同时指出：作者另有逆向 API 版（xiaohongshu-cli），"速度更加快更加稳定。但是风控上应该不如当前这个直接用浏览器操作真实"（第 3–4 行）——即作者自认存在平台风控对抗背景。

## 3. 安装方式

- `uv tool install xhs-cli` 或 `pipx install xhs-cli`（PyPI 已发布），需要 **Python 3.8+**（readme_excerpt.md 第 44–54 行）
- 源码安装：`git clone` + `uv sync`（第 56–65 行）
- 顶层文件：`pyproject.toml`、`uv.lock`、`xhs_cli/` 包目录、`scripts/`、`tests/`、`SKILL.md`（evidence/jackwener__xhs-cli__files.txt）

## 4. 权限范围

| 权限 | 是/否 | 证据 |
| --- | --- | --- |
| 执行任意 Shell | 未发现（CLI 工具本身不执行外部命令） | README 全文无相关描述 |
| **读取浏览器 Cookie** | **是——默认登录方式即"自动从 Chrome 提取 cookie（推荐）"**，属敏感本地读取 | readme_excerpt.md 第 101–103 行 |
| **启动浏览器** | **是**——browser-assisted 扫码登录会启动浏览器；底层为 Playwright 浏览器自动化（issue 标题"xhs comment fails with Playwright click timeout"） | readme_excerpt.md 第 27 行；evidence/jackwener__xhs-cli__issues.md |
| 监听本地端口 | 未发现（CLI 形态，无服务端） | README 全文无端口监听描述 |
| **访问本地文件** | **是**——读写 `~/.xhs-cli/cookies.json`；发布时读取本地图片（`--image photo1.jpg`） | readme_excerpt.md 第 69、188 行 |

## 5. 网络行为

- 直接请求小红书 Web/API：搜索、阅读、互动、发布（readme_excerpt.md 命令一览，第 33–42 行）
- 扫码登录通过 Playwright 驱动真实浏览器访问小红书（第 27、101–109 行）
- 无证据表明向第三方服务器回传数据（未发现遥测描述）

## 6. 文件行为

- 登录态与 token 落盘：`~/.xhs-cli/cookies.json`，`xsec_token` 自动缓存（readme_excerpt.md 第 29、69 行）
- 发布时读取用户指定本地图片文件（第 188 行）
- 冒烟测试脚本 `scripts/smoke_local.sh`（第 67–95 行）
- 无证据表明修改项目外其他文件

## 7. 登录态行为

三种登录方式（readme_excerpt.md 第 99–120 行）：

1. **自动从 Chrome 提取 cookie（默认推荐）**：`xhs login`
2. **二维码扫码**：`xhs login --qrcode`（终端渲染二维码）
3. **手动 cookie 字符串**（至少包含 `a1` 和 `web_session`）：`xhs login --cookie "..."`

登录态持久化保存（`cookies.json`）；`xhs status` 可在不启动浏览器、不读取浏览器 cookie 的情况下检查已保存登录态；`xhs logout` 退出。

## 8. 许可证

- **Apache-2.0**：`license.spdx_id = "Apache-2.0"`（evidence/jackwener__xhs-cli__meta.json）
- **LICENSE 文件真实存在**：license API 返回 200，顶层含 `LICENSE` 文件（evidence/jackwener__xhs-cli__license.json；evidence/jackwener__xhs-cli__files.txt）
- README 徽章同步标注 Apache-2.0（readme_excerpt.md 第 9 行）

## 9. 维护状态

- **维护停滞**：最新提交 2026-03-14，至核实日约 4 个月无提交；仓库 2026-03-04 创建，活跃期仅约 10 天（meta.json）
- open issue 总数（search API）：**7**（evidence/jackwener__xhs-cli__issues.md）
- **issue 以登录失效为主**，代表性标题（同上）：
  - 「Unable to login via QR code」
  - 「Login failed」
  - 「Login completed but session is still limited」
  - 另有「【bug】 xhs notifications 命令会失败」「xhs comment fails with Playwright click timeout」
- 无集中封号/风控反馈，但样本量小（仅 7 条）

## 10. 风险

| 风险 | 等级 | 说明 |
| --- | --- | --- |
| 默认提取 Chrome cookie | **中-高** | 读取本机浏览器凭据库，敏感本地读取；供应链投毒时危害大 |
| 维护停滞 | **中-高** | 2026-03-14 后无提交；登录类失效 issue 无人响应的风险随平台改版上升 |
| 写操作能力 | 中 | 点赞/收藏/评论/删除/发布；但为显式子命令，可通过不使用缓解 |
| 平台风控 | 中 | 作者自述与逆向 API 版的风控对比，表明工具处于平台对抗地带 |
| 登录失效面 | 中 | 现有 issue 已出现 QR 登录失败、session 受限 |
| cookies 落盘 | 低-中 | `~/.xhs-cli/cookies.json` 明文保存登录态 |

## 11. 缓解措施

- **不引入代码**；如需终端采集能力，优先自研或等其恢复活跃维护后重新评估
- 写操作命令（like/favorite/comment/post/delete）为显式子命令，可不调用以限制风险（缓解有效）
- 不使用默认的 Chrome cookie 提取登录，改用二维码登录（缓解 cookie 库读取风险）
- 若仅技术验证：隔离 Python 环境（uv/pipx 独立 venv）+ 专用测试账号 + 仅跑无副作用命令（其冒烟测试默认即 `integration and not live_mutation`，readme_excerpt.md 第 81–86 行）

## 12. 输入输出

- 输入：CLI 子命令 + 参数/选项（`xhs search "咖啡"`、`xhs read <note_id> [--xsec-token]`、`xhs comment <note_id> "..."` 等，readme_excerpt.md 第 122–198 行）
- 输出：终端 Rich 表格；所有数据命令支持 `--json` 结构化输出；`xsec_token` 自动缓存免手动传（第 28–29、42 行）

## 13. 测试计划（若未来重评时的预案）

1. 隔离 Python 环境安装 PyPI 包，核对 PyPI 发布与仓库代码一致性
2. 专用测试账号二维码登录，不启用 Chrome cookie 提取
3. 仅执行只读命令（search/read/feed/user）+ `--json` 校验输出结构
4. 运行其自带冒烟测试（默认不含 live_mutation）
5. 观察仓库是否恢复提交与 issue 响应，作为重评前提

## 14. 替代方案

- 小红书官方开放平台 API（合规首选）
- 手工采集 + 表格整理
- 自研受限只读 CLI/脚本（复用其命令设计思路即可，无需引入代码）
- 同作者逆向 API 版 xiaohongshu-cli（README 第 3 行提及；未在本次评审范围，引入前需另行审查）

## 15. 评分（审定分数）

| 维度 | 权重 | 加权得分 | 依据要点 |
| --- | --: | --: | --- |
| 业务匹配度 | 25 | 20 | 采集/阅读/互动覆盖面好，CLI 形态契合脚本化场景 |
| 输入输出兼容性 | 15 | 12 | `--json` 输出 + token 缓存，易于管道集成 |
| 可复现性和文档质量 | 10 | 6 | PyPI 可复现安装；文档含命令表与冒烟测试，但篇幅有限 |
| 维护活跃度 | 10 | 4 | 2026-03-14 后停滞约 4 个月 |
| 社区使用情况 | 10 | 5 | 611 star，有一定采用但体量有限 |
| 许可证可用性 | 10 | 10 | Apache-2.0 已核实，LICENSE 文件存在 |
| 安全性 | 10 | 5 | 默认读取 Chrome cookie + cookies 落盘 + 写操作，可用显式禁用部分缓解 |
| 改造成本 | 5 | 3 | Python 包结构清晰，但停滞项目改造需自担维护 |
| 可替换性 | 5 | 4 | 官方 API / 自研可替代 |
| **总分** | 100 | **69** | — |

## 16. 准入建议

**rejected。** 理由（审定）：

1. 总分 69 < 85；
2. Apache-2.0 许可证已核实（优点）；
3. 维护停滞（2026-03-14 后无提交），open issue 以登录失效为主（「Unable to login via QR code」「Login failed」等）；
4. 默认自动提取 Chrome cookie，属敏感本地读取；
5. 写操作为显式命令，可限制不用（缓解成立）；
6. **如恢复活跃维护可重新评估。**

## 17. 证据链接

- GitHub 仓库：https://github.com/jackwener/xhs-cli
- PyPI：https://pypi.org/project/xhs-cli/（README 第 8 行徽章所示）
- 本地证据：
  - evidence/jackwener__xhs-cli__meta.json
  - evidence/jackwener__xhs-cli__license.json
  - evidence/jackwener__xhs-cli__readme_excerpt.md
  - evidence/jackwener__xhs-cli__issues.md
  - evidence/jackwener__xhs-cli__files.txt
