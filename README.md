# mcn-script-assistant

面向 MCN 商单策划的小红书达人调研、风格分析、脚本生成、合规质检与飞书交付 Agent。

## 1. 项目名称

`mcn-script-assistant`

## 2. 项目简介

本项目是面向 MCN AI 咨询服务与 Agent 原型交付岗位的面试实操项目。目标是把"品牌 Brief → 达人调研 → 脚本策划 → 合规质检 → 飞书交付"这条 MCN 商单策划链路，建设为一个可验证、可复用、可交付的 Agent 工作流仓库。

## 3. 业务问题

MCN 在承接食品等品牌商单时，达人筛选依赖人工经验、脚本风格难以稳定复刻、食品广告合规风险高、交付过程分散在聊天记录和文档中，导致：

- 达人选择缺乏证据链，无法向品牌方解释"为什么选这位达人"；
- 脚本质量依赖个别策划，无法规模化；
- 合规检查靠人肉，容易遗漏《广告法》及食品类目违禁词；
- 交付物难以沉淀为可复用的 Skill 与流程资产。

## 4. 最终能力范围

1. 小红书达人调研；
2. 达人筛选与评分；
3. 达人内容风格拆解；
4. 商单视频脚本生成；
5. 文案 Humanizer 处理；
6. 视频分镜生成；
7. 食品广告合规检查；
8. Agent 工作流搭建；
9. 飞书文档自动写入；
10. Skill 沉淀；
11. GitHub 仓库完整交付。

## 5. 当前阶段

```text
当前阶段：Stage 2 - 达人搜索策略、组件正式准入与受控候选采集POC（进行中）
```

阶段进度：

| 阶段 | 状态 |
| -- | -- |
| Stage 0 - 项目控制台与组件准入机制 | 已通过（97/100） |
| Stage 1 - 品牌Brief结构化 | 已通过项目总控复评（96/100；首次 86/100，经数据契约返工后通过） |
| Stage 2 - 达人搜索策略与候选采集 | 进行中：组件准入审查＋受控POC；候选调研已放行，**最终达人定案尚未放行** |

> Stage 1已通过项目总控复评，96/100。Stage 2正在执行组件准入与受控候选采集POC。最终达人定案尚未放行。
> 达人风格Skill、脚本生成、飞书接入等功能**尚未实现**，将在后续阶段按门禁逐步推进。

## 6. 总体工作流

```text
品牌Brief结构化
  → 达人搜索策略与候选采集
  → 达人筛选与评分（10位）
  → 达人证据与字幕语料
  → 风格画像与 Style Skill
  → 脚本Skill与工具选型
  → 三方向脚本生成与竞争
  → Humanizer 中文人味处理
  → 分镜与拍摄可行性设计
  → 食品广告合规与事实质检
  → Agent 工作流编排
  → 飞书自动写入
  → 通用 MCN Skill 沉淀
  → GitHub 仓库与最终报告
```

## 7. 目录结构

```text
mcn-script-assistant/
├── README.md                  # 项目说明（本文件）
├── .gitignore                 # Git 忽略规则（含密钥/环境文件）
├── .env.example               # 环境变量模板（仅变量名，无真实值）
├── requirements.txt           # 运行依赖
├── pyproject.toml             # 项目元数据与工具配置（pytest/ruff）
│
├── project/                   # 项目控制台：章程、验收、角色、日志、决策
│   ├── project_charter.md
│   ├── acceptance_criteria.md
│   ├── role_matrix.md
│   ├── execution_log.md
│   └── decision_log.md
│
├── registry/                  # 第三方组件准入机制
│   ├── component_requirements.yaml
│   ├── component_candidates.csv
│   ├── approved_components.yaml
│   ├── rejected_components.yaml
│   ├── component_scorecard.md
│   └── THIRD_PARTY_NOTICES.md
│
├── config/                    # 项目配置与质量门禁
│   ├── project.yaml
│   └── quality_gates.yaml
│
├── data/                      # 数据（raw / processed / samples）
├── reports/                   # 阶段报告与分析报告
├── outputs/                   # 生成的脚本、分镜等产出物
├── prompts/                   # Prompt 资产
├── skills/                    # 沉淀的 Skill
├── adapters/                  # 第三方组件统一适配器
├── src/                       # 源代码
├── tests/                     # 自动化测试
├── docs/                      # 补充文档
├── scripts/                   # 自动化脚本（含阶段验证）
└── screenshots/               # 证据截图
```

## 8. 环境准备

- Python >= 3.10
- Git
- 建议使用虚拟环境：`python -m venv .venv`

## 9. 安装方式

```bash
git clone <repo-url>
cd mcn-script-assistant
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## 10. 配置方式

```bash
cp .env.example .env
# 然后在 .env 中填写 LLM / 飞书 / GitHub 等凭据
```

`.env` 已被 `.gitignore` 忽略，**严禁**将真实密钥提交到仓库。

## 11. 阶段验收机制

项目分为 Stage 0 ~ Stage 14 共 15 个阶段，每个阶段有明确的目标、输入、交付物、验收证据和评分门槛，详见 `project/acceptance_criteria.md`。

统一门禁：

```text
90—100分：允许进入下一阶段
85—89分：局部返工后重新评分
低于85分：重新设计或重新执行
存在真实性、密钥泄露、合规或核心功能问题：直接退回
```

## 12. 第三方组件准入机制

所有第三方 Skill 和 GitHub 工具必须先在 `registry/` 登记并评分：

1. 在 `registry/component_candidates.csv` 登记候选组件；
2. 按 `registry/component_requirements.yaml` 的字段完成审查；
3. 按 `registry/component_scorecard.md` 的评分卡打分；
4. 90 分以上且许可证、安全审查通过 → 进入 `approved_components.yaml`；
5. 低于 85 分或存在关键风险 → 进入 `rejected_components.yaml`；
6. 在 `THIRD_PARTY_NOTICES.md` 记录许可证与风险。

未经准入的第三方组件不得引入代码库。

## 13. 数据真实性原则

- 真实数据优先：达人、笔记、互动数据必须来自真实渠道并保留证据（链接、截图）；
- 不将模型输出直接视为事实：所有模型生成的事实性内容必须经人工或规则核验；
- 不得虚构运行结果、接口返回或测试结论；
- 所有验收结论必须有文件、日志或命令输出作为证据。

## 14. 安全原则

- 密钥只存在于本地 `.env`，通过环境变量读取，禁止硬编码；
- 第三方组件最小权限：逐项声明所需的网络、Shell、环境变量、文件访问范围；
- 禁止提交 Cookie、Token、Session 文件（已在 `.gitignore` 中屏蔽）；
- 每个第三方组件必须记录许可证、安全风险和替代方案。

## 15. 当前已完成内容

- 标准 GitHub 仓库目录结构；
- 项目章程、角色矩阵、15 阶段验收标准与评分模型；
- 第三方组件准入机制（需求字段、候选登记表、评分卡、许可证记录模板）；
- 环境变量模板与 `.gitignore` 安全规则；
- Stage 0 自动验证脚本（`scripts/validate_stage_0.py`）与结构测试——**Stage 0 已通过（97/100）**；
- 执行日志与决策日志框架；
- Stage 1 品牌 Brief 结构化管线——**Stage 1 已通过项目总控复评（96/100）**：Pydantic 模型、JSON Schema、业务规则校验、合规边界、18 项缺失信息、ValidationReport 评分与 Stage 2 双层门禁；
- Stage 2 组件正式准入审查（2026-07-17）：4 个候选组件经真实取证审查**全部 rejected**（CAND-001 无许可证 74 分；CAND-002 维护停滞 69 分；CAND-003 依赖已拒绝上游 44 分；CAND-004 明示规避验证码 43 分触发硬性排除），未安装任何组件，审查报告与证据见 `reports/component_reviews/`；
- Stage 2 达人采集数据契约：Creator Schema（`src/creator_models.py` + `config/creator_schema.json`）、真实性五层来源标记、POC 候选状态约束；
- Stage 2 搜索策略：4 组 16 词搜索计划（`data/processed/creator_search_plan.json`）、POC 边界规则（`config/creator_search_rules.yaml`）、人工验证表；
- Stage 2 自动验证脚本（`scripts/validate_stage_2.py`），全部测试 290 项通过；
- Stage 2 只读浏览器控制 POC（D-0008，2026-07-18）：kimi-webbridge 只读适配器＋策略层（白名单动作、3s 限速、重试≤1、人工门禁），真实采集 1 词 5 条结果、2 位达人主页（真实粉丝数）、1 篇笔记（真实互动数据）与 4 张截图，审计零写操作、零 Cookie 导出；
- Stage 2 第二轮（2026-07-18）：旧 navigate 入口彻底移除（策略白名单＋适配器＋测试三重锁定），三个高层方法统一为软导航并复用已登录会话标签页；从已采集达人主页真实定位视频笔记（小娇日记747 / 6a4903ad000000002003b221，type=video，page_observed）；FFmpeg v7.1（CAND-009）与 faster-whisper tiny 本地模型（CAND-010）真实安装验证；12 字段视频时间线契约与全链路编排脚本就绪，全量 315 项测试通过；
- 视频理解管线（获取→转写→抽帧→时间线→分析）代码就绪；yt-dlp 两轮真实执行均失败（图文笔记无视频；未登录页面不含视频流），XHS-Downloader 需 Cookie 属策略禁止；6 个 CLI/包工具登记 poc_required（CAND-005~010）。

## 16. 当前未完成内容

- **真实视频下载/转写/抽帧/时间线（阻塞于人工门禁）**：视频流地址仅在登录态页面可得，WebBridge 只能借用前台标签页，需用户将小红书标签页切到前台后重跑 `scripts/analyze_xhs_video.py`（`stage_2_video_poc_ready=false`，不伪造成功）；
- 视觉类字段标注（屏幕字幕/动作/场景/镜头/产品露出，保持 None 待人工或视觉模型）；
- 最终 10 位达人定案（未放行，`stage_2_final_selection_ready=false`）；
- 达人筛选评分、风格拆解（Stage 3 ~ 4）；
- 脚本生成、Humanizer、分镜（Stage 5 ~ 9）；
- 合规质检、Agent 编排、飞书写入（Stage 10 ~ 12）；
- Skill 沉淀与最终交付（Stage 13 ~ 14）。

## 17. 后续阶段

当前执行 **Stage 2：达人搜索策略、组件正式准入与受控候选采集 POC**。组件准入审查已完成（4 个候选全部 rejected），候选采集转人工路径执行；Stage 2 验收通过后进入 Stage 3（10 位达人深度调研，届时如启用新采集组件须重新走完整准入流程）。

## 18. 项目限制

- 本阶段不包含小红书自动爬虫、视频下载、飞书 API 调用、完整前端与自动发布；
- 平台数据采集以"人工真实搜索 + 证据留存"为主，自动化采集须经组件准入与合规评估；
- 所有对外内容发布动作均由人工执行，Agent 只负责生成与整理。
