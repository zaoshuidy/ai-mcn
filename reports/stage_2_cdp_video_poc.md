# Stage 2 专用 Chrome CDP 视频 POC 报告（D-0009）

日期：2026-07-18 ｜ 状态：**真实视频端到端理解完成**（technical_poc_only）

## 1. 路线变更背景

WebBridge 前台借用方案（D-0008）在 60+ 次借用尝试后确认不可用：借用要求 Chrome 窗口
处于操作系统焦点，用户回复对话即失焦，协议性失败。D-0009 决策：改用专用 Chrome
配置目录＋CDP 连接（96 分），WebBridge 成果保留为搜索/截图备用能力。

## 2. 专用 Chrome 与 CDP 会话

| 项 | 结果 | 证据 |
| -- | -- | -- |
| 专用 Profile | tmp/xhs_cdp_profile/（已 gitignore，未读默认 Profile） | scripts/start_xhs_cdp_chrome.ps1 |
| 调试端口 | 127.0.0.1:9222（环回，非 0.0.0.0） | config/xhs_cdp_readonly_policy.yaml |
| 可见窗口 | 是（非 headless） | 策略 headless: false |
| CDP 连接 | Playwright connect_over_cdp 成功（contexts=1 pages=1） | data/processed/xhs_cdp_session_evidence.json |
| 登录 | 人工在专用窗口扫码完成（loggedIn=true），脚本自动检测继续 | 同上 |
| 标签页选择 | 按 URL note_id 匹配，不依赖 OS 焦点 | adapters/xhs_cdp_browser_adapter.py |

## 3. 真实笔记核验

- 未登录时笔记直连返回 300031（需公开分享令牌）；从达人主页 noteCard 提取真实
  xsecToken 后软导航成功（复用同一标签页，未创建新标签页）；
- 页面核对：note_id=6a4903ad000000002003b221 ✓、type=video ✓、
  作者=小娇日记747 ✓、标题=《爬坡后吃根香蕉 下颌线真的越来越清晰！！》✓；
- 媒体结构：h264/h265 两个流，720x960，时长 2996ms，页面报 size=463,505 bytes
  （data/processed/xhs_video_page_evidence.json，签名 URL 仅存哈希与域名）。

## 4. 视频下载与校验

| 项 | 值 |
| -- | -- |
| 下载方式 | CDP 页面 context 请求栈（yt-dlp/浏览器原生下载未触发即成功） |
| 文件 | tmp/xhs_video_poc/source_video.mp4（不入 Git） |
| 大小 | 463,505 bytes（与页面报文完全一致） |
| 时长 | 3.0s（与页面 2996ms 漂移 0.004s） |
| 分辨率/编码 | 720x960 / h264 + aac（HE-AAC） |
| SHA-256 | 见 data/processed/xhs_video_file_manifest.json |

## 5. 转写

- FFmpeg 提取 16kHz 单声道 audio.wav（96,674 bytes）；
- faster-whisper **small** 本地模型（ModelScope 真实下载 483MB，加载验证）；
- 语言识别 zh（prob=1.00），1 个转写片段：0–2s「字幕by索兰娅」（第三方字幕水印）；
- 结论：**该视频无实质口播**，仅有背景音乐与字幕水印（如实记录）；
- 完整转写仅存 tmp/，不入 Git。

## 6. 关键帧与多模态视觉读取

- 每 2 秒精确帧（0.0s、2.0s）＋结尾帧（2.9s）＋场景切换检测（0 命中，单镜头）；
- 近似去重后 3 帧；联系表 tmp/xhs_video_poc/contact_sheet.jpg；
- **实际读取关键帧**（多模态）：健身房跑步机第一人称视角、手持剥开的香蕉行走咬食、
  五行标题字幕（爬坡公式）、无包装商品品牌可辨、无商业合作标识；
- keyframe_manifest.json（tmp/）记录每帧时间戳。

## 7. 产出物（Git）

- data/processed/xhs_cdp_session_evidence.json（CDP 会话证据）
- data/processed/xhs_video_page_evidence.json（页面媒体证据，签名 URL 仅哈希）
- data/processed/xhs_video_file_manifest.json（文件清单＋SHA-256）
- data/processed/video_timeline.json（14 字段音视频联合时间线，2 个片段）
- data/processed/video_evidence_manifest.json（证据清单）
- reports/stage_2_real_video_analysis.md（10 点分析，全部结论可追溯）

## 8. 安全核验

- 只读：无点赞/收藏/评论/关注/私信/发布；无自动登录；无验证码绕过；
- 未导出 Cookie/localStorage；未访问默认 Chrome Profile；CDP 仅环回；
- 原始视频/音频/完整转写/关键帧均在 tmp/（gitignore 强制）；
- 媒体签名 URL 只写 tmp/，Git 仅存 SHA-256＋域名；
- actions_log：connect_over_cdp / evaluate_readonly / soft_navigate /
  context_request_get，无写操作。

## 9. 目标笔记用途声明

标题与画面字幕以「瘦脸/下颌线/燃脂」外貌结果承诺为核心，违反轻醒合规边界；
内容赛道与产品场景错位。标记：usage_scope=technical_poc_only，
selection_status=excluded_from_creator_selection。**不进入轻醒达人名单。**

## 10. 测试

新增 28 项 CDP 适配器测试（11 个覆盖点：环回地址、禁默认 Profile、gitignore、
按 URL 选页、登录等待成功/超时、零凭据读取、媒体筛选、签名 URL 脱敏、
不碰用户日常 Chrome、tmp 产物忽略、无写方法），全量 343 项通过。
