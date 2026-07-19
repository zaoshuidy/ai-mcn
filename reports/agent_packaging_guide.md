# Agent 打包说明：轻醒商单脚本 Agent（agent/）

> 版本：v0.1.0 ｜ 日期：2026-07-19 ｜ 范围：`agent/` 目录、`tests/test_agent_graph.py`
>
> 本文是 agent/ 包的交付说明：编排图、节点契约、回退矩阵、人工接入点、
> 与 5 个 Skill 的对应关系、langgraph 迁移路径与安装/验证方法。
> 所有结论均有文件或命令输出支撑（见第 9 节验证证据）。

## 1. 概述与边界

`agent/` 把"Brief → 风格 → 脚本 → 人味化 → 事实回检 → 合规审查 → 分镜 →
人工审批 → 飞书写入"这条商单脚本链路打包为一个**最小可运行的纯 Python 编排图**：

- **不依赖 langgraph**：langgraph 在组件 registry 中登记为 CAND-017
  （`reference_only`，2026-07-19 审查），"是否作为运行时依赖引入需另行执行
  组件评审"。在评审通过前，本包以纯 Python 实现等价语义（节点注册 / 状态合并 /
  条件路由 / 失败回退 / 人工暂停），并保留逐条迁移注释（`agent/graph.py` 模块
  docstring 与本文第 7 节）。
- **不含任何 LLM 调用**：LLM 节点（script_generator / humanizer /
  storyboard_generator）为契约完备的 stub（`NotImplementedError`），正式实现
  经 `build_agent_graph(node_overrides=...)` 统一注入。
- **不含任何真实凭据**：feishu_publisher 为 stub；正式实现凭据只读环境变量
  （`.env.example` 中 FEISHU_* 变量名），严禁硬编码、严禁提交。
- **可运行演示**：brief_analyzer / creator_style_distiller 基于 Stage 1/3 已验收的
  真实数据文件做确定性统计；fact_regression / compliance_reviewer 基于
  `agent/policies/` 策略文件做确定性规则检查（无证据即拦截的下限，不声称全量召回）。

## 2. 文件清单

```text
agent/
├── __init__.py                     # 包说明与版本
├── state.py                        # AgentState TypedDict、节点名/状态常量、make_initial_state
├── schemas.py                      # 9 个节点 IO 契约（Pydantic v2，纯契约无 IO）
├── graph.py                        # AgentGraph 引擎、4 个路由函数、build_agent_graph、run_demo
├── nodes/
│   ├── __init__.py                 # 节点分类说明（演示 / stub）
│   ├── brief_analyzer.py           # 演示：读 state.brief 或 data/processed/qingxing_brief.json
│   ├── creator_style_distiller.py  # 演示：读 Top3 真实视频时间线做统计画像
│   ├── script_generator.py         # stub（LLM + 脚本 Skill）
│   ├── humanizer.py                # stub（LLM + 人味化 Skill）
│   ├── fact_regression.py          # 演示：规则回检（qingxing_claims.yaml）
│   ├── compliance_reviewer.py      # 演示：违禁表达扫描（banned_claims.yaml）
│   ├── storyboard_generator.py     # stub（LLM + 分镜 Skill）
│   ├── human_approval.py           # 演示：无决定→waiting_human；有决定→路由分流
│   └── feishu_publisher.py         # stub（Stage 12，凭据只读环境变量）
└── policies/
    ├── qingxing_claims.yaml        # 轻醒允许卖点、证据要求与禁止解释方向
    ├── banned_claims.yaml          # 违禁表达类目（减肥/降糖/医疗/绝对化等 7 类）
    └── approval_rules.yaml         # 人工审批规则（AR-001~005）
tests/test_agent_graph.py           # 26 项测试（路由语义 + 规则演示 + 本地数据演示）
reports/agent_packaging_guide.md    # 本文
```

## 3. 编排图说明

```text
┌────────────────┐   ┌─────────────────────────┐   ┌──────────────────┐
│ brief_analyzer │ → │ creator_style_distiller │ → │ script_generator │ ←──────────────┐
└────────────────┘   └─────────────────────────┘   └──────────────────┘                │
                                                          │                            │
                                                          ▼                            │
┌────────────────┐   ┌─────────────────────┐   ┌──────────────────┐                    │
│ human_approval │ ← │ storyboard_generator│ ← │compliance_reviewer│                   │
└────────────────┘   └─────────────────────┘   └──────────────────┘                    │
       │  ▲                    │  ▲                    │ fact/compliance 未通过          │
       │  │                    │  └─ 时长不一致回退    ├────────────────────────────────┘
       │  └─ 人工拒绝回退      │    （回本节点重排）   │
       │    （回 retry_node    ▼                       │
       │      指定修改节点） ┌──────────────────┐      │
       ▼                    │   fact_regression │ ←── humanizer ←──┘
┌────────────────┐          └──────────────────┘
│feishu_publisher│ → END（status=completed）
└────────────────┘

暂停/中止出口：
- human_approval 无 human_decision → END（status=waiting_human，等待人工补决定后重跑）
- 累计回退 > max_retries（默认 3）→ END（status=aborted_max_retries）
- 人工决定 retry_node 非法 → END（status=aborted_invalid_human_route）
```

设计要点：

- **节点不做路由决策**：全部流向判断集中在 `agent/graph.py` 的 4 个路由函数
  （route_after_fact / route_after_compliance / route_after_storyboard /
  route_after_human），回退矩阵是唯一事实来源；
- **状态合并语义与 langgraph 对齐**：节点函数 `run(state) -> patch`，引擎合并
  patch 并记录 `history`；流程控制字段（retry_count/status/errors/last_failure）
  仅引擎与路由函数写入；
- **单一重试预算**：所有闸口共享 `retry_count`（含质检回退、时长回退、人工拒绝），
  超限即中止转人工线下处理（approval_rules.yaml AR-003），防止无限返修；
- **质检在人味化之后**：防止"改写引入违禁表达"，humanized.text 是两个质检节点的
  优先扫描对象（无 humanized 时回退 script.text）。

## 4. 节点契约表

契约模型见 `agent/schemas.py`；各节点模块 docstring 为同内容的可执行约束。

| 节点 | 读取 state 键 | 写入 state 键 | 输出契约 | 实现状态 |
| -- | -- | -- | -- | -- |
| brief_analyzer | brief（可选，缺省读默认文件） | brief_analysis | BriefAnalysis | 演示（本地文件） |
| creator_style_distiller | style_timelines（可选）、brief_analysis | style_profile | StyleProfile | 演示（本地文件统计） |
| script_generator | brief_analysis、style_profile、last_failure | script | ScriptDraft | stub（LLM） |
| humanizer | script、style_profile、last_failure | humanized | HumanizedScript | stub（LLM） |
| fact_regression | humanized/script、brief_analysis | fact_result | FactCheckResult | 演示（规则） |
| compliance_reviewer | humanized/script | compliance_result | ComplianceResult | 演示（规则） |
| storyboard_generator | humanized、script、style_profile、last_failure | storyboard | Storyboard | stub（LLM） |
| human_approval | 全部交付物、human_decision | （仅 waiting_human 标记） | HumanDecision（输入） | 演示（状态判断） |
| feishu_publisher | 全部交付物 + human_decision | publish_result | PublishResult | stub（Stage 12） |

关键字段约定：

- `script.text`：完整口播/字幕文本，两个质检节点的扫描对象；
- `script.claims_used`：草稿声明用到的卖点，fact_regression 据此做白名单核对；
- `script.target_duration_s`：分镜时长一致性基准（容差 5 秒，
  `graph.DURATION_TOLERANCE_S`）；
- `storyboard.total_duration_s`：缺省时按各镜头 `end_s - start_s` 求和；
- `last_failure`：回退时携带 `{gate, fallback_to, retry_count, detail}`，
  修订类节点（script_generator 等）必须逐条响应。

## 5. 回退矩阵

| # | 触发条件 | 判定位置 | 回退目标 | retry_count | 超限行为 |
| -- | -- | -- | -- | -- | -- |
| F1 | fact_result.passed=False | route_after_fact | script_generator | +1 | 累计 > max_retries → aborted_max_retries |
| F2 | compliance_result.passed=False | route_after_compliance | script_generator | +1 | 同上 |
| F3 | 分镜总时长与脚本目标时长差 > 5s（或时长字段缺失） | route_after_storyboard | storyboard_generator | +1 | 同上 |
| F4 | human_decision.approved=False 且 retry_node 合法 | route_after_human | retry_node 指定节点（script_generator / humanizer / storyboard_generator） | +1 | 同上 |
| F5 | human_decision.approved=False 但 retry_node 缺失/非法 | route_after_human | 不回退 | — | aborted_invalid_human_route |
| F6 | 无 human_decision | human_approval 节点 + route_after_human | 不回退 | — | waiting_human（暂停，可补决定后重跑） |

每次回退都会向 `errors` 追加一条 `{gate, fallback_to, retry_count, detail}` 记录，
并将同一对象写入 `last_failure` 供修订节点消费；全程可追溯。

## 6. 人工接入点

**唯一人工闸口：human_approval**（规则见 `agent/policies/approval_rules.yaml`）。

- **提交什么**：人工看到的一定是"双检通过"的稿件——script / humanized /
  fact_result / compliance_result / storyboard 全部在 state 中可审（AR-001）；
- **如何注入决定**：两种方式，均不经过网络——
  1. 运行前注入：`make_initial_state(human_decision={...})` 或把决定放进初始 state；
  2. 暂停后补录：流程无决定时停在 `waiting_human`，人工审阅后把
     `human_decision` 补进 state 重跑（langgraph 迁移后对应
     `interrupt_before=["human_approval"]` + checkpointer 续跑）；
- **决定契约**（agent.schemas.HumanDecision）：
  `approved`（必填）、`retry_node`（拒绝时必填，仅允许
  script_generator / humanizer / storyboard_generator）、`feedback`（拒绝时必填，
  AR-002）、`reviewer`、`decided_at`；
- **铁律**：`auto_approve=false`——无人工决定绝不自动通过（F6）；审批通过前
  feishu_publisher 不可达（AR-004）；审批记录随交付物写入飞书（AR-005）。

演示/测试可用 `node_overrides` 注入假审批节点（见 `tests/test_agent_graph.py`
的 `make_overrides` 与 `agent/graph.py` 的 `run_demo`）。

## 7. 与 5 个 Skill 的对应关系

脚本链路的 5 个 Skill 已沉淀于 `skills/`（各有 SKILL.md，由并行任务交付）；
registry 参考组件均注明"仅参考、禁止复制原文"。节点与 Skill 一一对应：

| Agent 节点 | 对应 Skill（skills/ 实际目录） | registry 参考 | 关系说明 |
| -- | -- | -- | -- |
| creator_style_distiller | `skills/creator-style-distiller/` | CAND-012 nuwa-skill（方法论参考） | 节点是 Skill 的编排封装；本包演示实现提供统计底座 |
| script_generator | `skills/xhs-commercial-script/` | CAND-016 video-script-developer-gist（结构参考） | 节点 stub 的正式实现即调用该 Skill |
| humanizer | `skills/xhs-script-humanizer/` | CAND-013 humanizer / CAND-014 Humanizer-zh（规则思路参考） | 同上 |
| fact_regression + compliance_reviewer | `skills/xhs-food-ad-compliance/` | —（策略为本项目自研 YAML） | 两个节点共用该 Skill 的策略文件与检查器 |
| storyboard_generator | `skills/xhs-storyboard-generator/` | CAND-015 ai-video-storyboard-skill（字段结构参考） | 节点 stub 的正式实现即调用该 Skill |

brief_analyzer 复用 Stage 1 管线成果（src/brief_parser 等）、human_approval 与
feishu_publisher 为流程固有节点，均不属于 5 个 Skill。

## 8. 后续 langgraph 迁移路径

前置条件：langgraph（CAND-017）通过组件准入评审成为运行时依赖。迁移为逐条
机械替换，节点函数与契约零改动：

| 本包（纯 Python） | langgraph 对应 |
| -- | -- |
| `AgentGraph` | `StateGraph(AgentState)` |
| `add_node(name, func)` | `builder.add_node(name, func)`（签名同为 state → patch） |
| `add_edge(src, dst)` | `builder.add_edge(src, dst)` |
| `add_conditional_edges(src, router)`，router 返回 `(next, patch)` | `builder.add_conditional_edges(src, router)`，router 只返回 `next`；patch 改由节点自身或 `Command(goto=..., update=...)` 表达 |
| `END = "__end__"` | `langgraph.graph.END` |
| `graph.run(state)` | `builder.compile().invoke(state)` |
| `waiting_human` 暂停 + 补决定重跑 | `interrupt_before=["human_approval"]` + checkpointer 续跑 |
| `max_steps` 死循环保护 | `recursion_limit` |

路由函数（route_after_*）与回退矩阵原样保留，仅需按上表调整返回值形态；
`tests/test_agent_graph.py` 的语义断言（轨迹顺序、回退目标、重试上限）迁移后
应原样通过。

## 9. 安装与验证

### 9.1 安装

本包仅依赖仓库既有运行依赖（`PyYAML>=6.0`、`pydantic>=2.0`，见
`requirements.txt` / `pyproject.toml`），无新增第三方包：

```bash
pip install -r requirements.txt
```

### 9.2 验证证据（本机真实执行，2026-07-19）

```text
$ python -m pytest tests/test_agent_graph.py -q
..........................                     [100%]
============================= 26 passed in 0.21s ==============================

$ python -m pytest tests/ -q        # 全量回归
======================= 544 passed, 5 warnings in 2.30s =======================

$ python -m ruff check agent/ tests/test_agent_graph.py
All checks passed!

$ python -m agent.graph             # 端到端演示（确定性假 LLM 节点 + 真实策略文件）
节点执行轨迹: brief_analyzer -> creator_style_distiller -> script_generator -> humanizer -> fact_regression -> compliance_reviewer -> storyboard_generator -> human_approval -> feishu_publisher
最终状态: completed
回退次数: 0
```

### 9.3 测试覆盖（tests/test_agent_graph.py，26 项）

- 装配：默认图节点注册顺序 = NODE_ORDER、每节点均有出边、人工回退白名单与
  策略文件一致；
- 主链路：全通过时严格按 9 节点顺序执行、status=completed；
- 回退：fact 失败→script_generator、compliance 失败→script_generator、
  分镜时长不一致→storyboard_generator（轨迹断言逐节点比对）；
- 人工：拒绝→指定修改节点、非法 retry_node→aborted_invalid_human_route、
  无决定→waiting_human 且发布节点未执行；
- 重试上限：共享预算 max_retries=3 下第 4 次失败中止、跨闸口共享预算中止；
- 时长校验：容差内通过、超差失败、缺 total 时按镜头求和、缺输入失败；
- 规则演示节点：违禁词阻断（减肥/瘦身/掉秤）、受限词仅告警（控糖）、
  营养数值拦截（10g/80千卡）、禁止解释方向拦截（0蔗糖→无糖）、
  白名单外卖点拦截、干净文本通过；
- 本地数据演示节点：brief_analyzer 读真实 qingxing_brief.json（轻醒/高蛋白/
  阻塞项透传）、creator_style_distiller 读真实 Top3 时间线（3 条、主导形式
  取自数据实际取值——真实数据中含 `subtitle_immersive` 等形式标签）。

## 10. 已知限制（如实说明）

1. script_generator / humanizer / storyboard_generator / feishu_publisher 为 stub，
   端到端真实产出须待对应 Skill 与凭据接入后经 node_overrides 注入；
2. fact_regression / compliance_reviewer 的演示实现是确定性下限（违禁词与
   数值拦截），不具备 LLM 语义召回能力，不构成完整质检；
3. creator_style_distiller 演示画像为统计摘要，非完整风格拆解（Stage 4 范围）；
4. 人工审批的"暂停—补录—重跑"在纯 Python 版为进程级语义，跨进程持久化待
   langgraph checkpointer 迁移后获得。
