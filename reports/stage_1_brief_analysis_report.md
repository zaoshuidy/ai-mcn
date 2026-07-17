# Stage 1 品牌 Brief 结构化分析报告（数据契约补齐版）

- 日期：2026-07-17（局部返工更新）
- 执行者：技术执行 AI
- 测试 Brief：轻食酸奶「轻醒」（`data/raw/qingxing_brief.md`，项目总控下发的固定测试 Brief）
- 关联决策：project/decision_log.md D-0004（方案选型）、D-0005（局部返工方式）
- 验收背景：Stage 1 验收 86/100 → 局部返工，补齐数据契约与 Stage 2 门禁
- 状态：返工完成，待项目总控复评（本报告不声明 Stage 1 通过）

## 1. 返工方式（D-0005）

| 方向 | 方案 | 评分 | 结论 |
| -- | -- | --: | -- |
| A | 接受当前简化模型，直接进入 Stage 2 | 84 | 不采用 |
| B | 删除现有实现并完全重写 | 88 | 不采用 |
| C | 向后兼容扩展模型与门禁 | 96 | 已实施 |

保留首版 107 项测试全部通过，新增 49 项契约测试，合计 156 项。

## 2. 标准数据契约

顶层模型 `BrandBrief`（version 2.0）同时包含标准结构与兼容字段，
`upgrade_legacy_brief` 可将仅有旧字段的数据迁移为完整结构。

| 模型 | 核心字段 | 下游用途 |
| -- | -- | -- |
| BrandInfo | brand/product/category/platform/content_format/campaign_goal | 平台与内容形式拆分，供 Agent 编排 |
| ProductVariant | name/confirmed/source | 口味清单及来源追溯 |
| UsageScenario | name/priority/natural_integration_reason/shooting_feasibility | 分镜与拍摄可行性（Stage 9） |
| ComplianceRule | category/prohibited/restricted/reason/guidance/severity | 合规质检（Stage 10），共 7 类 |
| MissingInformation | field/importance/reason/recommended_action/blocks_next_stage | 缺失信息门控下游阶段 |

年龄升级为 `age_min/age_max/age_range` 三字段：模型强制 age_max > age_min、
age_min ≥ 0；业务校验强制上下限与原文一致，不得擅自扩展。
平台拆分为 `platform=小红书`、`content_format=短视频`（兼容字段保留原文）。

## 3. 缺失信息（18 项）

- 阻塞 Stage 2 最终定案（blocks_next_stage=true，5 项）：营养成分表、0蔗糖依据、高蛋白依据、产品价格、购买渠道；
- 生成 warning（5 项，各扣 2 分）：品牌禁用词、竞品排他要求、达人预算和达人量级、投放时间与发布时间要求、视频时长要求；
- 其他待补（8 项）：产品包装图、产品规格、是否提供拍摄样品、主推口味、物流与寄样周期、内容修改轮次、品牌审核时限、素材使用授权范围。

## 4. ValidationReport（轻醒 Brief 当前状态）

- status：ready_with_warnings
- score：90/100（100 − 5 项 low warning × 2）
- errors：0；blockers：0；warnings：5（均为待补信息提醒）
- passed_rules：必需栏目完整性、卖点证据等级、禁止解释方向、人群兴趣与产品功效隔离、臆造数据拦截、年龄一致性、合规规则清单扫描、禁止承诺功效隔离
- **Stage 2 候选调研是否可开始：是**
- **Stage 2 最终达人定案是否可开始：否**（待补齐：营养成分表、0蔗糖依据、高蛋白依据、产品价格、购买渠道）

真实性/合规硬伤封顶机制：虚构营养数值、无证据 confirmed、0蔗糖→无糖、
低负担→不长胖、功效承诺、疾病治疗声明，命中任意一项总分封顶 79 且
Stage 2 候选调研自动拦截（验证脚本以构造样例实测：封顶后 score=70）。

## 5. 合规边界（与首版一致并保留）

| 卖点 | 证据等级 | 禁止解释方向 |
| -- | -- | -- |
| 0蔗糖 | brand_claim（缺依据，未升级为 confirmed） | 无糖 |
| 高蛋白 | brand_claim（缺依据） | — |
| 饱腹感 | subjective_experience | 减重、抑制食欲 |
| 低负担 | unverified | 不长胖、零负担、减肥 |

"控糖"仅为人群兴趣标签；未编造任何营养数值；缺失数据写入 missing_information。

## 6. 路径安全

- source_file 统一为相对路径：`data/raw/qingxing_brief.md`；
- 验证脚本扫描 data/processed、reports、config，无盘符/用户目录/本地绝对路径。

## 7. 验证结果（真实运行）

```text
python scripts/build_brief.py
  → error=0 warning=0；score=90 status=ready_with_warnings
  → research_ready=True final_selection_ready=False；构建成功
python scripts/validate_stage_0.py → PASS=67 WARNING=0 FAIL=0，passed
python scripts/validate_stage_1.py → PASS=49 WARNING=0 FAIL=0，passed
python -m pytest → 156 passed（旧 107 + 新 49）
python -m ruff check src scripts tests → All checks passed!
```

## 8. 边界与限制

- 解析器仍为规则版，适配固定格式 Brief；LLM 接入契约见 `prompts/brief_analyzer.md`；
- human_verified=false，待人工执行者确认；
- 未安装任何 Stage 2 候选组件；当前仅"候选调研"被放行，最终定案待品牌方补齐 5 项商务信息。
