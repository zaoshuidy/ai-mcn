# 生成规则（rules）

本文件是 `SKILL.md` 的执行细则。生成脚本前必须通读；任何与「铁律」冲突的产出都视为不合格。
文中真实证据均出自 `data/processed/stage_3_top3_video_timelines.json`（3 条真实视频时间线）：

| 达人 | note_id | 时长 | 形态 |
| --- | --- | --- | --- |
| 欧盈Kelly | `6989ab01000000001a0360c5` | 153.5s | voiceover（口播型上班 vlog） |
| 小季没烦恼 | `6a58b7ea000000001101a7bb` | 114.0s | subtitle_immersive（字幕型，含霸王茶姬植入） |
| 一只牛🐮 | `6a59b5ac00000000100295fe` | 54.7s | subtitle_immersive（字幕型早餐） |

## 1. 铁律（不可违反）

1. **原创优先**：不得直接复制达人原句（口播、字幕、标题、固定结束语）。风格只借鉴「高层模式」，文案必须重写。达人语料中的 `do_not_copy` 项一律禁用。
2. **证据先行**：`full_script` 中每一句产品卖点句都必须进入 `claim_evidence_map`，且 `evidence_ids` 必须存在于输入的 ProductEvidence 中。**无证据的功效不得写**（例如「低负担」只有口头卖点、无依据时，不得出现在脚本正文）。
3. **合规红线**：禁止减肥/燃脂/掉秤/降糖/医疗效果/绝对化表达；「0蔗糖」不得写成「无糖」；主观体验（如饱腹感）必须使用个人体验语境（「我觉得」「对我来说」），且不得触碰 `forbidden_interpretations`（减重/抑制食欲/不长胖/零负担等）。
4. **未证实数值**：无品牌方营养成分表/检测报告时，不得标注任何营养数值（蛋白质克数、糖含量、热量）。
5. **不得虚构证据**：ProductEvidence 中不存在的 `evidence_id` 不得引用；缺失信息写入 `unresolved_questions`，而不是编造。

## 2. 输入确认

- **BrandBrief**：品牌/产品/人群/场景/合规边界（结构参考 `data/processed/qingxing_brief.json`）。
- **ProductEvidence**：逐条核对哪些卖点「有证据可写」，记录 `evidence_id`。
- **CreatorStyleProfile**：结构、植入模式、`do_not_copy`、风格证据引文（含 `note_id`）。
- **target_duration / content_scene / format**：决定篇幅、场景与载体规则。

## 3. 形态规则（format，三种必须都支持）

| format | 载体要求 | 节奏参考（真实证据） |
| --- | --- | --- |
| `voiceover` | 每个分段必须有 `voiceover` | 口播 3-5 字/秒；字幕做时间戳/情绪辅助（欧盈Kelly：口播旁白为主线） |
| `subtitle` | 每个分段必须有 `on_screen_text`，无口播 | 短字幕（单条 ≤15 字为佳）+环境音（一只牛：字幕每段 ≤15 字；小季：字幕承担叙事+情绪+卖点） |
| `hybrid` | 每个分段必须同时有 `voiceover` 与 `on_screen_text` | 口播主线+字幕补充，二者信息不重复 |

## 4. Hook 规则

- 0-5s 内完成。可借鉴的真实 hook 模式：
  - **欧盈Kelly**：口语化问候+大字标题卡，建立打工人共鸣（`6989ab01000000001a0360c5` hook_analysis）。
  - **小季没烦恼**：场景点题式字幕，直接立「下班后治愈」预期（`6a58b7ea000000001101a7bb` hook_analysis）。
  - **一只牛🐮**：成品特写先行，靠食物质感抓注意力（`6a59b5ac00000000100295fe` hook_analysis）。
- `hook.design_basis` 必须写明借鉴了哪种模式；`hook.text` 必须原创。

## 5. 产品首次出现与植入节奏

真实证据（时间线 `segments[].product_first_appearance` 与 `style_summary`）：

- **欧盈Kelly（贯穿式）**：自用香水 14.0s（9.1%）；冰美式 18s/33s 两杯，「饮品贯穿的生活流动线」，均为生活流自然位置。
- **小季没烦恼（需求场景→产品解法）**：商单产品 16.0s（14.0%）首现；16-26s 为「需求场景（晚上想喝但怕失眠）→产品解法（轻因系列）」集中卖点段，约 10s、占片长 9%。
- **一只牛🐮（成品先行）**：`product_first_appearance_s=0.0`，成品即开场。

执行规则：

1. **首现窗口**：`target_duration` 的前 0-15% 内完成首现；超出须在 `product_first_appearance.rationale` 说明理由。
2. **两种推荐节奏**（按达人风格二选一，也可组合）：
   - 贯穿式（Kelly 证据）：产品在 ≥2 个自然生活节点复现，无集中卖点段；
   - 需求场景→产品解法（小季证据）：先 5-15s 需求铺垫，随后集中段给卖点，集中段占比约 10%。
3. `product_first_appearance.time_s` 必须落在某个分段区间内，`rationale` 必须引用真实证据说明取值理由。

## 6. 卖点与 claim_evidence_map

- **检测口径**：凡含 ProductEvidence/BrandBrief 中卖点关键词（如「0蔗糖」「高蛋白」「饱腹感」「低负担」）或其 `forbidden_interpretations`（如「无糖」「减肥」）的脚本句子，都是「产品卖点句」。
- 每一句卖点句：至少一条 `claim_evidence_map` 条目覆盖；句中**每个**卖点关键词都要有对应 `claim` 的条目；`evidence_ids` 全部存在于 ProductEvidence。
- 条目 `script_sentence` 必须能在 `full_script` 中逐字找到（不允许映射不存在的句子）。
- 主观体验卖点（`subjective_experience`）也要映射到对应证据条目，并在句中使用「我觉得/对我来说」等限定。
- 无证据卖点：写入 `unresolved_questions`，脚本正文不得出现。

## 7. 风格借鉴与 style_evidence_map

- 只借鉴「可复用高层模式」（结构、节奏、植入方式、镜头习惯），并在 `style_evidence_map` 中标注：`script_element`、`borrowed_pattern`、`source`（creator + note_id + 证据位置）、`adaptation`（怎么改的）。
- 每条借鉴必须能指回真实证据（时间线 JSON 的 `hook_analysis` / `style_summary` / `segments`）。
- `do_not_copy` 清单中的元素（个人梗、人设标签、固定句式、系列标题模板）一律不得使用。

## 8. 时长估算

- `voiceover`：按口播总字数 3-5 字/秒估算，含停顿与空镜。
- `subtitle`：按镜头数 × 2-3s/镜头估算（三条真实视频 `avg_shot_s` 为 2.0-2.5s）。
- `hybrid`：两者取较大值。
- `estimated_duration` 与 `target_duration` 偏差超过 ±30% 视为不合格（`validate_output.py` 硬检查）。

## 9. CTA 与未决问题

- CTA 自然、不硬广（对齐 BrandBrief.campaign_goal）；购买渠道/价格缺失时不得编造，写入 `unresolved_questions`。
- `unresolved_questions` 至少列出阻塞合规与转化的问题（如：购买渠道、包装图、真实营养数据）。
