# 第三方组件评分卡（Component Scorecard）

> 每个候选组件一份评分卡。评分必须给出依据，空打分无效。
> 加权总分 >= 90 且许可证、安全审查通过 → `approved`；
> 85–89 → `reference_only`（仅借鉴方法）；< 85 或存在关键风险 → `rejected`。

## 评分维度与权重

| 维度 | 权重 |
| --- | --: |
| 业务匹配度 | 25 |
| 输入输出兼容性 | 15 |
| 可复现性和文档质量 | 10 |
| 维护活跃度 | 10 |
| 社区使用情况 | 10 |
| 许可证可用性 | 10 |
| 安全性 | 10 |
| 改造成本 | 5 |
| 可替换性 | 5 |
| 总分 | 100 |

---

## 评分卡模板（复制以下区块逐组件填写）

### 组件：（名称）

- 组件 ID：
- 仓库地址：
- 版本 / Commit：
- 评估人：
- 评估日期：

#### 1. 分项评分

| 维度 | 权重 | 得分(0-100) | 加权分 | 评分依据 | 扣分原因 |
| --- | --: | --: | --: | --- | --- |
| 业务匹配度 | 25 | | | | |
| 输入输出兼容性 | 15 | | | | |
| 可复现性和文档质量 | 10 | | | | |
| 维护活跃度 | 10 | | | | |
| 社区使用情况 | 10 | | | | |
| 许可证可用性 | 10 | | | | |
| 安全性 | 10 | | | | |
| 改造成本 | 5 | | | | |
| 可替换性 | 5 | | | | |
| **总分** | 100 | — | | — | — |

#### 2. 风险项

| 风险 | 等级(高/中/低) | 说明 | 缓解措施 |
| --- | --- | --- | --- |
| | | | |

#### 3. 权限与供应链审查

| 审查项 | 是/否 | 说明 |
| --- | --- | --- |
| 是否允许执行 Shell | | |
| 是否读取环境变量 | | |
| 是否访问外部网络 | | |
| 是否会修改项目外文件 | | |
| 是否存在供应链风险（依赖不明二进制、远程脚本注入等） | | |

#### 4. 最终准入结论

- 加权总分：
- 许可证审查结论：
- 安全审查结论：
- 结论：approved / reference_only / rejected / pending
- 替代方案（fallback）：
- 审查证据（路径/命令输出/截图）：

---

## 当前已评估组件

> 2026-07-17 完成首批 4 个候选组件评估，证据见 `reports/component_reviews/evidence/`（当日实时抓取），
> 完整报告见 `reports/component_reviews/CAND-00X-*.md`。4 个组件结论均为 **rejected**，未引入任何代码。

### 组件：xiaohongshu-mcp

- 组件 ID：CAND-001
- 仓库地址：https://github.com/xpzouying/xiaohongshu-mcp
- 版本 / Commit：main @ `5c5197d`（2026-06-29）
- 评估人：项目评审（Kimi 辅助取证）
- 评估日期：2026-07-17

#### 1. 分项评分

| 维度 | 权重 | 得分(0-100) | 加权分 | 评分依据 | 扣分原因 |
| --- | --: | --: | --: | --- | --- |
| 业务匹配度 | 25 | 92 | 23 | 登录/搜索/feed/详情/发布/评论/点赞全覆盖，契合 MCN 采集+互动场景（evidence/xpzouying__xiaohongshu-mcp__readme_excerpt.md） | 无私信等少量能力 |
| 输入输出兼容性 | 15 | 87 | 13 | 标准 MCP over HTTP（localhost:18060/mcp），JSON 输入输出 | 需 xsec_token 等平台内部参数，接入有门槛 |
| 可复现性和文档质量 | 10 | 80 | 8 | 二进制/Go 源码/Docker 三种安装 + 视频演示（readme_full.md） | 文档夹杂推广内容 |
| 维护活跃度 | 10 | 90 | 9 | 2026-06-29 最新提交，2026-07-13 仍有推送（meta.json） | — |
| 社区使用情况 | 10 | 100 | 10 | 14,714 star / 2,176 fork（meta.json） | — |
| 许可证可用性 | 10 | 0 | 0 | spdx_id=null，license API 404，无 LICENSE 文件（license.json、files.txt） | **无许可证，使用/修改/分发无授权** |
| 安全性 | 10 | 30 | 3 | — | 发布/评论/点赞写权限；首启下载约150MB无头浏览器；cookies 文件落盘；监听 18060；issue 区集中封号/风控实证（issues.md） |
| 改造成本 | 5 | 80 | 4 | Go 代码结构清晰（go.mod、分层目录，files.txt） | 无许可证致改造无合法基础 |
| 可替换性 | 5 | 80 | 4 | 官方开放平台/自研可替代 | — |
| **总分** | 100 | — | **74** | — | — |

#### 2. 风险项

| 风险 | 等级(高/中/低) | 说明 | 缓解措施 |
| --- | --- | --- | --- |
| 无开源许可证 | 高 | 默认保留所有权利，合规上不可引入 | 不引入代码，仅方法参考；无法技术缓解 |
| 平台风控/封号连带 | 高 | issue 实证：「被小红书识别出来封号了」「今天被小红书弹了警告，建议大家不要使用这个 MCP 了」「最近使用mcp容易被封号」 | 不用于生产账号；官方 API 替代 |
| 写操作滥用 | 高 | 发布图文/视频、评论、回复、点赞 | 不引入；如需则自研只读采集 |
| 无头浏览器下载 | 中 | 首启下载约 150MB 二进制 | 沙箱验证哈希 |
| cookies 落盘 + 端口监听 | 中 | 登录态文件 + 18060 HTTP 服务 | 隔离环境、绑定回环地址 |

#### 3. 权限与供应链审查

| 审查项 | 是/否 | 说明 |
| --- | --- | --- |
| 是否允许执行 Shell | 否 | 未见相关能力描述 |
| 是否读取环境变量 | 是 | `XHS_PROXY` 代理变量（readme_full.md 第 484 行） |
| 是否访问外部网络 | 是 | xiaohongshu.com；首启下载无头浏览器；Docker Hub 镜像 |
| 是否会修改项目外文件 | 是 | cookies/数据目录（./data 挂载）；读取本地图片/视频发布 |
| 是否存在供应链风险（依赖不明二进制、远程脚本注入等） | 是 | 约 150MB 无头浏览器运行时下载；Docker Hub 镜像；Releases 预编译二进制，均无许可证约束 |

#### 4. 最终准入结论

- 加权总分：**74**
- 许可证审查结论：**不通过**——无许可证（license API 404，无 LICENSE 文件）
- 安全审查结论：**不通过**——写权限 + 封号/风控实证 + 无头浏览器下载 + cookies 落盘
- 结论：**rejected**
- 替代方案（fallback）：小红书官方开放平台 API；自研受限只读采集器；CAND-002（亦 rejected，仅方法参考）
- 审查证据（路径/命令输出/截图）：reports/component_reviews/evidence/xpzouying__xiaohongshu-mcp__{meta.json,license.json,readme_excerpt.md,readme_full.md,issues.md,files.txt}；报告 reports/component_reviews/CAND-001-xiaohongshu-mcp.md

---

### 组件：xhs-cli

- 组件 ID：CAND-002
- 仓库地址：https://github.com/jackwener/xhs-cli
- 版本 / Commit：main @ `3ce7141`（2026-03-14）
- 评估人：项目评审（Kimi 辅助取证）
- 评估日期：2026-07-17

#### 1. 分项评分

| 维度 | 权重 | 得分(0-100) | 加权分 | 评分依据 | 扣分原因 |
| --- | --: | --: | --: | --- | --- |
| 业务匹配度 | 25 | 80 | 20 | 搜索/阅读/用户/feed/互动/发布，CLI 契合脚本化（readme_excerpt.md） | 发布等写能力非主要诉求 |
| 输入输出兼容性 | 15 | 80 | 12 | 全命令 `--json` 输出 + xsec_token 自动缓存 | CLI 需包装才成服务 |
| 可复现性和文档质量 | 10 | 60 | 6 | PyPI 发布（uv/pipx），含命令表与冒烟测试 | 文档篇幅有限，架构说明单薄 |
| 维护活跃度 | 10 | 40 | 4 | 创建后活跃约 10 天 | **2026-03-14 后停滞约 4 个月** |
| 社区使用情况 | 10 | 50 | 5 | 611 star / 62 fork | 体量有限，watch 0 |
| 许可证可用性 | 10 | 100 | 10 | Apache-2.0，LICENSE 文件存在（license.json、files.txt） | — |
| 安全性 | 10 | 50 | 5 | — | 默认自动提取 Chrome cookie（敏感本地读取）；cookies.json 落盘；含写操作（显式命令可禁用） |
| 改造成本 | 5 | 60 | 3 | Python 包结构清晰（pyproject.toml、xhs_cli/） | 停滞项目改造需自担维护 |
| 可替换性 | 5 | 80 | 4 | 官方 API / 自研可替代 | — |
| **总分** | 100 | — | **69** | — | — |

#### 2. 风险项

| 风险 | 等级(高/中/低) | 说明 | 缓解措施 |
| --- | --- | --- | --- |
| Chrome cookie 提取 | 中-高 | 默认登录方式即读取本机 Chrome 凭据 | 改用二维码登录（--qrcode） |
| 维护停滞 | 中-高 | 2026-03-14 后无提交；登录失效 issue 悬置 | 恢复活跃后重评 |
| 登录失效 | 中 | 「Unable to login via QR code」「Login failed」「session is still limited」 | 专用测试账号验证 |
| 写操作 | 中 | like/favorite/comment/post/delete | 显式命令，不调用即可禁用 |
| 平台风控 | 中 | 作者自述与逆向 API 版的风控取舍 | 限速、只读优先 |

#### 3. 权限与供应链审查

| 审查项 | 是/否 | 说明 |
| --- | --- | --- |
| 是否允许执行 Shell | 否 | CLI 本身不执行外部命令 |
| 是否读取环境变量 | 是 | 冒烟测试环境变量（XHS_SMOKE_*） |
| 是否访问外部网络 | 是 | xiaohongshu.com API/页面（Playwright） |
| 是否会修改项目外文件 | 是 | `~/.xhs-cli/cookies.json`、xsec_token 缓存 |
| 是否存在供应链风险（依赖不明二进制、远程脚本注入等） | 部分 | PyPI 包需核对与仓库一致性；Playwright 浏览器二进制依赖 |

#### 4. 最终准入结论

- 加权总分：**69**
- 许可证审查结论：**通过**——Apache-2.0 已核实
- 安全审查结论：**有条件**——Chrome cookie 提取与写操作可通过配置规避，但叠加维护停滞不予通过
- 结论：**rejected**（总分 < 85；如恢复活跃维护可重新评估）
- 替代方案（fallback）：官方开放平台 API；自研只读 CLI（参考其命令设计）
- 审查证据（路径/命令输出/截图）：reports/component_reviews/evidence/jackwener__xhs-cli__{meta.json,license.json,readme_excerpt.md,issues.md,files.txt}；报告 reports/component_reviews/CAND-002-xhs-cli.md

---

### 组件：xiaohongshu-skill

- 组件 ID：CAND-003
- 仓库地址：https://github.com/ibreez3/xiaohongshu-skill
- 版本 / Commit：main @ `5928cc4`（2026-02-01）
- 评估人：项目评审（Kimi 辅助取证）
- 评估日期：2026-07-17

#### 1. 分项评分

| 维度 | 权重 | 得分(0-100) | 加权分 | 评分依据 | 扣分原因 |
| --- | --: | --: | --: | --- | --- |
| 业务匹配度 | 25 | 40 | 10 | 有搜索/feed 读取能力 | **偏向内容发布而非采集，方向错位** |
| 输入输出兼容性 | 15 | 53 | 8 | OpenClaw 命令 + MCP 包装 | 无独立实现，离开上游不可用 |
| 可复现性和文档质量 | 10 | 50 | 5 | install 脚本 + 大量指南文档 | **README 启动命令（npm start）与上游 Go 技术栈不符** |
| 维护活跃度 | 10 | 10 | 1 | — | **创建次日（2026-02-01）即最后提交，5 个多月无维护** |
| 社区使用情况 | 10 | 10 | 1 | — | star 仅 20、watch 0 |
| 许可证可用性 | 10 | 100 | 10 | MIT，LICENSE 文件存在（license.json、files.txt） | — |
| 安全性 | 10 | 50 | 5 | 本身攻击面小 | 继承上游 CAND-001 全部风险；安装脚本写 `~/.openclaw/skills/` |
| 改造成本 | 5 | 40 | 2 | 仅包装层 | 无核心逻辑，改造价值低 |
| 可替换性 | 5 | 40 | 2 | 可绕过该层直接用上游 | 上游本身 rejected |
| **总分** | 100 | — | **44** | — | — |

#### 2. 风险项

| 风险 | 等级(高/中/低) | 说明 | 缓解措施 |
| --- | --- | --- | --- |
| 依赖 CAND-001（rejected） | 高 | 全部功能依赖无许可证且封号实证的上游 | 不引入；待合规上游出现再评估 |
| 停止维护 | 高 | 创建次日即停更 | 无需缓解（不引入） |
| 业务方向不匹配 | 高 | 发布为主、采集为辅 | 不作为采集方案 |
| 安装脚本写主目录 | 低-中 | install.sh 拷贝+chmod | 不执行脚本，仅阅读参考 |

#### 3. 权限与供应链审查

| 审查项 | 是/否 | 说明 |
| --- | --- | --- |
| 是否允许执行 Shell | 是 | install.sh / install-adapter.sh / uninstall*.sh 等安装期脚本 |
| 是否读取环境变量 | 未见 | README 未述 |
| 是否访问外部网络 | 间接 | 本身仅访问本机 18060；外网由上游发起 |
| 是否会修改项目外文件 | 是 | 写入 `~/.openclaw/skills/xiaohongshu-auto-publish/` |
| 是否存在供应链风险（依赖不明二进制、远程脚本注入等） | 是 | 依赖链整体受 CAND-001 供应链风险传导 |

#### 4. 最终准入结论

- 加权总分：**44**
- 许可证审查结论：**通过**——MIT 已核实
- 安全审查结论：**不通过**——依赖链断裂（上游 rejected）
- 结论：**rejected**
- 替代方案（fallback）：在合规上游之上自研轻量 Skill 封装；或直接使用合规上游接口
- 审查证据（路径/命令输出/截图）：reports/component_reviews/evidence/ibreez3__xiaohongshu-skill__{meta.json,license.json,readme_excerpt.md,issues.md,files.txt}；报告 reports/component_reviews/CAND-003-xiaohongshu-skill.md

---

### 组件：browser-mcp

- 组件 ID：CAND-004
- 仓库地址：https://github.com/BrowserMCP/mcp
- 版本 / Commit：main @ `9db12f2`（2025-04-24，v0.1.3）
- 评估人：项目评审（Kimi 辅助取证）
- 评估日期：2026-07-17

#### 1. 分项评分

| 维度 | 权重 | 得分(0-100) | 加权分 | 评分依据 | 扣分原因 |
| --- | --: | --: | --: | --- | --- |
| 业务匹配度 | 25 | 32 | 8 | 通用浏览器自动化可覆盖部分采集动作 | 非采集专用；规避检测方向与合规诉求冲突 |
| 输入输出兼容性 | 15 | 53 | 8 | 标准 MCP 接口 | 工具 schema 无法从开源部分完整确认 |
| 可复现性和文档质量 | 10 | 30 | 3 | — | **README 仅 32 行、无安装说明、明示依赖私有 monorepo 无法独立构建** |
| 维护活跃度 | 10 | 10 | 1 | — | **源码 14 个多月未提交（2025-04-24），125 个 open issue** |
| 社区使用情况 | 10 | 70 | 7 | 6,840 star / 535 fork | issue 区反映实际可用性差 |
| 许可证可用性 | 10 | 100 | 10 | Apache-2.0，LICENSE 文件存在（license.json、files.txt） | — |
| 安全性 | 10 | 10 | 1 | — | **README 明示 "avoids basic bot detection and CAPTCHAs"**；AI 客户端继承全站登录态 + 写操作 |
| 改造成本 | 5 | 40 | 2 | — | 无法独立构建，无改造基础 |
| 可替换性 | 5 | 60 | 3 | playwright-mcp 等可替代通用能力 | 其独有能力（规避检测）恰为风险点 |
| **总分** | 100 | — | **43** | — | — |

#### 2. 风险项

| 风险 | 等级(高/中/低) | 说明 | 缓解措施 |
| --- | --- | --- | --- |
| 绕过验证码/风控逻辑 | 高 | README 卖点 "Stealth: Avoids basic bot detection and CAPTCHAs by using your real browser fingerprint" | **无有效缓解，直接 rejected** |
| 全登录态浏览器控制 | 高 | 复用浏览器 profile，AI 客户端继承所有站点会话 + click/type 写操作 | 不安装到工作浏览器 |
| 供应链不透明 | 高 | 开源代码无法独立构建，正式分发在闭源链路 | 不采用 |
| 源码停更 | 中-高 | 14 个多月无提交，失效 issue 积压 | 无 |

#### 3. 权限与供应链审查

| 审查项 | 是/否 | 说明 |
| --- | --- | --- |
| 是否允许执行 Shell | 未见直接证据 | README 无描述；源码不可构建无法确认 |
| 是否读取环境变量 | 未知 | 同上 |
| 是否访问外部网络 | 是 | 浏览器内任意请求（继承用户会话）；本地 WebSocket（9009 端口，issues.md） |
| 是否会修改项目外文件 | 未知 | 不可构建，无法静态确认 |
| 是否存在供应链风险（依赖不明二进制、远程脚本注入等） | 是 | 依赖私有 monorepo；Chrome 扩展分发；开源与产品脱节（「Browsermcp.dev is working but this repo is not」） |

#### 4. 最终准入结论

- 加权总分：**43**
- 许可证审查结论：**通过**——Apache-2.0 已核实
- 安全审查结论：**不通过**——明示规避 bot 检测/CAPTCHA + 全登录态写操作 + 不可构建
- 结论：**rejected**（命中"绕过验证码或平台风控逻辑：直接 rejected"规则）
- 替代方案（fallback）：microsoft/playwright-mcp（隔离实例、不宣称规避检测）；官方 Playwright 脚本
- 审查证据（路径/命令输出/截图）：reports/component_reviews/evidence/BrowserMCP__mcp__{meta.json,license.json,readme_excerpt.md,issues.md,files.txt}；报告 reports/component_reviews/CAND-004-browser-mcp.md
