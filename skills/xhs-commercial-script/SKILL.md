---
name: xhs-commercial-script
description: 小红书商单短视频脚本生成 Skill。当需要基于 BrandBrief、ProductEvidence 与达人风格画像（CreatorStyleProfile），为指定场景与目标时长生成分段式商单脚本时使用；支持 voiceover（口播）、subtitle（字幕）、hybrid（混合）三种形态，输出含标题候选、Hook、完整脚本、产品首现设计、卖点-证据映射、风格证据映射与未决问题，并可用 scripts/validate_output.py 自动校验。
---

# xhs-commercial-script：小红书商单脚本生成

## 用途

把「品牌 Brief + 产品证据 + 达人风格画像」转化为一份**可直接拍摄、句句卖点有据可查、风格借鉴可追溯**的小红书商单脚本。适用于 MCN 商单策划中 Stage 6-7 的脚本产出环节。

## 输入

| 字段 | 说明 |
| --- | --- |
| `brand_brief` | BrandBrief：品牌/产品/目标人群/场景/合规边界（结构参考 `data/processed/qingxing_brief.json`） |
| `product_evidence` | ProductEvidence 清单：`evidence_id` / `claim` / `claim_type` / `evidence_text` / `source` |
| `creator_style_profile` | CreatorStyleProfile：达人结构、植入模式、`do_not_copy`、风格证据引文（含 `note_id`） |
| `target_duration` | 目标时长（秒） |
| `content_scene` | 内容场景（如早餐/办公室下午茶/运动后） |
| `format` | `voiceover` / `subtitle` / `hybrid`，三种形态必须都支持 |

完整字段约束见 `references/output-schema.md`。

## 输出

JSON 对象，固定字段：`title_options`、`selected_title`、`hook`、`full_script`（分段式）、`product_first_appearance`、`integration_sentence`、`CTA`、`estimated_duration`、`claim_evidence_map`、`style_evidence_map`、`unresolved_questions`。

## 工作流程

1. **核对输入**：先读 `references/rules.md`，盘点 ProductEvidence 覆盖哪些卖点；无证据卖点列入 `unresolved_questions`，正文不得出现。
2. **定结构**：按 `format` 与 `target_duration` 分段；hook 在 0-5s 内完成；产品首现落在时长前 0-15%（贯穿式或「需求场景→产品解法」集中段，须有真实证据依据）。
3. **写脚本**：全部文案原创；只借鉴达人高层风格模式，每条借鉴写入 `style_evidence_map`（标注 creator + note_id + 证据位置 + 改编方式）。
4. **映射卖点**：每一句产品卖点句进入 `claim_evidence_map`，证据 ID 必须存在于 ProductEvidence。
5. **自校**：估算 `estimated_duration`（与 target 偏差须 ≤30%），然后运行校验器：

```bash
python skills/xhs-commercial-script/scripts/validate_output.py OUTPUT.json \
    --input INPUT.json --timelines data/processed/stage_3_top3_video_timelines.json
```

校验器 6 项全部 PASS 才算合格：schema、内部一致性、形态载体、卖点-证据覆盖、时长偏差（>30% 判失败）、达人原句复制检查。

## 关键规则（详见 references/rules.md）

- **不得直接复制达人原句**（口播/字幕/标题/固定结束语）；`do_not_copy` 项一律禁用。
- **所有卖点必须映射 ProductEvidence**；无证据的功效不得写；未证实营养数值（克数/糖含量/热量）不得标注。
- 合规红线：禁止减肥/燃脂/掉秤/降糖/医疗效果/绝对化表达；「0蔗糖」不得写成「无糖」；主观体验须用「我觉得/对我来说」语境。

## 文件说明

- `references/rules.md`：生成规则细则（含三条真实视频证据的首现位置与植入结构）。
- `references/output-schema.md`：输入/输出契约与校验规则对应表。
- `references/examples.md`：轻醒酸奶早餐场景 voiceover 版完整输入输出示例（原创脚本，标注 style_evidence）。
- `evals/evals.json`：3 个真实正例（voiceover/subtitle/hybrid 各一）+ 1 个反例（卖点无证据映射应失败）。
- `scripts/validate_output.py`：输出校验器（可 CLI 调用，退出码 0/1）。

## 边界

- 本 Skill 只产出脚本文本与分镜提示，不生成视频/画面，不承诺未经证据支撑的功效。
- 示例与 eval 中的 `product_evidence` 为演示占位；真实投放前必须替换为品牌方提供的真实依据。
