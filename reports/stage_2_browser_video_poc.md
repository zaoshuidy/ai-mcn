# Stage 2 只读浏览器控制＋视频理解 POC 报告

日期：2026-07-18
路线：D-0008（撤销"只能人工采集"结论，采用 kimi-webbridge 只读适配器＋策略层＋视频理解管线）
策略：`config/xhs_readonly_policy.yaml`（唯一权威来源）

---

## 1. 执行结论

- 浏览器只读 POC：**真实执行成功**（受控范围内全部达成）
- 视频理解 POC：**获取链真实执行，按策略如实停止**（范围内无视频可下载）
- 登录/验证码：未出现；若出现将由人工处理，适配器检测即停
- 写操作：**零**（审计动作序列仅 evaluate / list_tabs / screenshot）
- Cookie/凭据：未导出、未读取、未提交（登录态留在用户浏览器内）

## 2. 技术架构

```text
config/xhs_readonly_policy.yaml（白名单/上限/人工门禁）
        ↓ 强制校验
adapters/xhs_browser_adapter.py
        ↓ HTTP
kimi-webbridge 守护进程（127.0.0.1:10086）
        ↓
用户真实 Chrome（已登录小红书，Cookie 不出浏览器）
```

- 白名单动作：find_tab / list_tabs / snapshot / evaluate / screenshot（navigate 已彻底移除）；
  click / fill / upload / cdp 等在适配器层直接 PolicyViolation；
- evaluate 仅允许内置只读脚本（搜索卡片/笔记/主页提取、门禁检测、页面状态、软导航）；
- 每次页面请求 ≥3 秒（RateLimiter），自动重试 ≤1 次；
- 守护进程 navigate 对重页面有 30s load 超时 → 三个高层方法统一为软导航
  （search_notes_soft / open_profile_soft / open_note_soft）：location.href 赋值＋轮询就绪，
  复用已登录会话标签页，不创建新标签页。

## 3. 浏览器 POC 真实结果

执行：`python scripts/run_xhs_readonly_poc.py`（范围：1 词 / ≤5 结果 / ≤2 主页 / ≤1 笔记）

| 项 | 结果 | 证据 |
| -- | -- | -- |
| 搜索关键词 | 健身女孩饮食（搜索计划 POC 首词） | screenshots/stage_2_browser_poc/01_search.png |
| 搜索结果 | 5 条真实笔记卡片（标题/URL/作者/主页URL） | data/processed/xhs_browser_poc.json |
| 达人主页 1 | 包包的减脂盒子，粉丝 4617 | 02_profile_1.png |
| 达人主页 2 | 泡泡王菲，粉丝 972 | 02_profile_2.png |
| 笔记详情 | 《已瘦20斤🙏生活化减脂✅》 赞 4.3万 / 藏 3.5万 / 评 279 | 03_note.png |
| 审计 | actions_log 仅 evaluate/list_tabs/screenshot | xhs_browser_poc.json.actions_log |

主页提取经 Vue ref（`_value`）解包修复后获得真实粉丝数；笔记 type=normal（图文），
5 条结果均为图文笔记，无视频卡片。

## 4. 视频理解 POC 真实结果

执行：`python scripts/analyze_xhs_video.py --url <笔记URL>`（yt-dlp 2026.07.04 已真实安装）

| 步骤 | 结果 | 说明 |
| -- | -- | -- |
| yt-dlp 获取 | 失败（预期内） | 目标为图文笔记，无视频流；yt-dlp 真实执行 |
| XHS-Downloader 兜底 | 不可用 | 本机未安装；按策略停止（退出码 5），未绕过 |
| VideoCaptioner 转写 | 未执行 | 工具未安装且无视频输入 |
| FFmpeg 抽帧 | 未执行 | 本机无 ffmpeg |
| video_timeline.json / content_analysis.md | 未生成 | 不伪造产物；管线代码与 22 项离线测试就绪 |

## 5. 安全与合规核验

- `.gitignore` 已覆盖 cookies.json / storage_state.json / .env / tmp/（测试锁定）；
- 视频仅存 tmp/（StoragePolicyViolation 强制，测试锁定）；
- GPL 工具（XHS-Downloader、VideoCaptioner）仅 CLI 调用，未复制任何源码；
- 适配器无 like/collect/comment/follow/dm/publish 方法（测试锁定）；
- 门禁词（扫码登录/安全验证等）命中即 HumanGateRequired（测试锁定）。

## 6. 测试与验证

- 新增离线测试 47 项（只读策略 25 + 视频管线 22），全部通过；
- 全量回归：Stage 0/1/2 验证脚本、pytest、ruff 结果见交付报告。

## 7. 第二轮（2026-07-18）：navigate 清理与真实视频端到端尝试

### 7.1 navigate 彻底清理（已验证）

- 策略白名单删除 navigate（现仅 find_tab/list_tabs/snapshot/evaluate/screenshot）；
- 适配器无 public navigate 方法，源码不再向守护进程发送 navigate 动作（测试锁定）；
- 三个高层方法统一软导航并复用已登录会话标签页（测试锁定）；
- 主页笔记提取修正为真实 noteCard 结构（id/displayTitle/type/interactInfo.likedCount）。

### 7.2 真实视频笔记定位（page_observed）

| 字段 | 值 |
| -- | -- |
| 达人 | 小娇日记747（主页 SSR 笔记列表提取） |
| 标题 | 爬坡后吃根香蕉 下颌线真的越来越清晰！！ |
| note_id | 6a4903ad000000002003b221 |
| type | video（noteCard.type，page_observed） |
| canonical_url | https://www.xiaohongshu.com/explore/6a4903ad000000002003b221（无 xsec_token） |

范围：检查 4 位达人主页（第 4 位因守护进程超时中断）；候选存
`data/processed/xhs_video_candidate.json`（human_verified=false）。

### 7.3 视频获取链真实结果（第二轮）

| 步骤 | 结果 | 说明 |
| -- | -- | -- |
| yt-dlp 2026.07.04 | 失败 | 未登录 explore 页面返回 No video formats found（页面不含视频流） |
| XHS-Downloader | 未安装 | 需 Cookie 配置，属策略禁止（不导出 Cookie） |
| 已登录页面提取 video_url | 阻塞（人工门禁） | WebBridge 只能借用**前台**标签页；用户当前未查看小红书页面，4 次借用均失败；守护进程 502 后按规则仅重启一次并恢复 |

### 7.4 工具链就绪（真实安装与验证）

- FFmpeg v7.1（imageio-ffmpeg 0.6.0，BSD-2-Clause，CAND-009，58 分 poc_required）：
  `ffmpeg -i` 元数据探测、音频抽取、每 2 秒＋场景切换抽帧均可用；
- faster-whisper 1.2.1（MIT，CAND-010，82 分 poc_required）＋ tiny 本地模型
  （75.5MB，经 ModelScope 真实下载并加载验证）；
- 12 字段 VideoSegment / VideoTimelineV2 / VideoEvidenceManifest 模型与全链路编排脚本
  `scripts/analyze_xhs_video.py` 就绪；新增 27 项测试，全量 315 项通过。

### 7.5 当前状态

`stage_2_video_poc_ready = false`——视频未真实下载/转写/抽帧，不伪造成功。
门禁解除（用户将小红书标签页切到前台）后，一条命令完成全链路：

```bash
python scripts/analyze_xhs_video.py   # 自动：提取video_url→下载→转写→抽帧→时间线→报告
```

## 8. 未完成与后续

- 真实视频下载/转写/抽帧/时间线：待人工门禁（前台标签页）解除后执行；
- 视觉类字段（屏幕字幕/动作/场景/镜头/产品露出）保持 None，待人工或视觉模型标注；
- 本 POC 不构成达人名单，全部候选仍需人工验证表审核。
