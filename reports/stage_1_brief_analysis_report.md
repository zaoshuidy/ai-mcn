# Stage 1 品牌 Brief 结构化分析报告

- 日期：2026-07-17
- 执行者：技术执行 AI
- 测试 Brief：轻食酸奶「轻醒」（`data/raw/qingxing_brief.md`，项目总控下发的固定测试 Brief）
- 关联决策：project/decision_log.md D-0004
- 状态：开发完成，待项目总控验收（本报告不声明 Stage 1 通过）

## 项目状态修正

- Stage 0首次验收：76/100，未通过
- Stage 0远程返工后复评：97/100，通过
- 当前阶段：Stage 1进行中
- Stage 2工具预研：已登记候选，未准入、未安装、未开发

## 1. 方案选型（三方向比较）

| 方向 | 方案 | 加权总分 | 结论 |
| -- | -- | --: | -- |
| A | 大模型自由 JSON 输出 | 72 | 结构易漂移、无法机器校验，不采用 |
| B | JSON Schema 校验 | 84 | 有结构校验但无类型层与业务规则层，不采用 |
| C | Pydantic 模型＋JSON Schema＋业务规则校验 | 95 | 唯一达 90 分门禁，已实施 |

评分明细见 `project/decision_log.md` D-0004。方向 C 实施为：

```text
data/raw/qingxing_brief.md（自然语言 Brief）
  → src/brief_parser.py（规则版解析，离线确定性）
  → src/brief_models.py（Pydantic 模型）
  → config/brief_schema.json（模型生成的 JSON Schema）
  → src/brief_validator.py + config/brief_rules.yaml（业务规则校验）
  → src/brief_renderer.py（人工可读摘要）
```

## 2. 结构化结果摘要

完整产物见 `data/processed/qingxing_brief.json` 与 `data/processed/qingxing_brief_summary.md`。

### 2.1 品牌与产品

- 品牌：轻醒
- 产品：0蔗糖高蛋白希腊酸奶（食品/乳制品）
- 口味：原味、蓝莓、黄桃
- 平台：小红书短视频
- 内容目标：自然种草，不要硬广，符合原博主创作风格

### 2.2 卖点证据等级（合规边界核心）

| 卖点 | 证据等级 | 依据 | 禁止解释方向 |
| -- | -- | -- | -- |
| 0蔗糖 | brand_claim | 未提供（不得升级为 confirmed） | 无糖 |
| 高蛋白 | brand_claim | 未提供 | — |
| 饱腹感 | subjective_experience | 未提供 | 减重、抑制食欲 |
| 低负担 | unverified | 未提供 | 不长胖、零负担、减肥 |

### 2.3 合规边界落地

- "控糖"仅作为目标人群兴趣标签（`audience_interest_not_product_claim`），产品卖点中无任何降糖/控制血糖/治疗类表述——由校验器 `INTEREST_AS_PRODUCT_CLAIM` / `INTEREST_AS_SELLING_POINT` 规则强制；
- 禁止承诺：减肥、降糖；
- 未编造任何蛋白质克数、糖含量、热量或检测数据——由 `FABRICATED_NUTRITION_DATA` 规则强制（数值仅允许出现在有依据的 confirmed 声明中）；
- 营养数据缺失被识别为缺失信息而非编造填充。

## 3. 缺失信息识别（6 项，需品牌方补充）

| 缺失项 | 优先级 | 影响 |
| -- | -- | -- |
| 营养成分数据（蛋白质/糖/热量） | 高 | 脚本卖点表述与合规质检 |
| 卖点依据（包装/检测报告） | 高 | brand_claim 能否升级为 confirmed |
| 投放预算与达人量级 | 中 | Stage 2-3 达人筛选范围 |
| 投放时间与排期 | 中 | 内容排期与脚本时效性 |
| 是否提供产品样品 | 中 | 达人拍摄可行性（Stage 9） |
| 是否有限定口味主推 | 低 | 脚本口味露出优先级 |

## 4. 达人搜索画像（Stage 2 输入）

- 内容赛道：健身饮食、轻食、控糖饮食、上班族生活、早餐
- 建议搜索关键词（8 个）：上班族早餐、健身女孩饮食、运动后加餐、办公室下午茶、控糖饮食记录、轻食一日三餐、高蛋白早餐、打工人冰箱常备
- 排除达人类型：品牌官方号、纯店铺号、搬运号、长期停更账号、硬广占比极高账号、主要内容为医疗或疾病建议的账号
- 风格要求：自然种草、非硬广、适合真实达人日常拍摄

## 5. 验证结果（真实运行）

```text
python scripts/build_brief.py       → error=0 warning=0，构建成功
python scripts/validate_stage_1.py  → 见本节末次运行输出
python -m pytest                    → 107 passed（Stage 0 回归 33 项 + Stage 1 新增 74 项）
python -m ruff check src scripts tests → All checks passed!
```

最终验证输出以执行报告（本次会话汇报）与 `git log` 为准。

## 6. 测试覆盖

Stage 1 新增测试 74 项（不含 Stage 0 的 33 项，合计 107 项全部通过）：

- `tests/test_brief_models.py`（12 项）：模型字段、枚举、默认值、JSON 往返、Schema 一致性；
- `tests/test_brief_parser.py`（24 项）：固定 Brief 解析、卖点归类、禁止解释、缺失信息与达人画像生成；
- `tests/test_brief_validator.py`（23 项）：四条卖点证据等级边界、禁止解释、兴趣/功效隔离、臆造数据拦截、必需栏目；
- `tests/test_brief_renderer.py`（15 项）：摘要栏目完整性、证据等级标签、合规提示展示。

全部测试离线运行，不依赖真实 LLM。

## 7. 边界与限制

- 当前解析器为规则版，适配固定格式 Brief；LLM 接入契约已写入 `prompts/brief_analyzer.md`，接入后输出仍走同一模型与规则校验；
- `human_verified=false`，待人工执行者核对结构化结果与原始 Brief 一致后置为 true；
- 本阶段未安装、未调用任何 Stage 2 候选组件，未进行达人采集。
