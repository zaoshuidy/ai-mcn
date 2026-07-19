# 输入/输出契约（output-schema）

本文件定义 xhs-commercial-script 的输入与输出 JSON 契约，并给出每条校验规则与 `scripts/validate_output.py` 检查项的对应关系。

## 1. 生成输入（Generation Input）

```json
{
  "brand_brief": {
    "brand_name": "轻醒",
    "product_name": "0蔗糖高蛋白希腊酸奶",
    "campaign_goal": "自然种草，不要硬广",
    "selling_points": [
      {"claim": "0蔗糖", "claim_type": "brand_claim", "forbidden_interpretations": ["无糖"]}
    ]
  },
  "product_evidence": [
    {
      "evidence_id": "EV-001",
      "claim": "0蔗糖",
      "claim_type": "brand_claim",
      "evidence_text": "……依据描述……",
      "source": "brand_provided_packaging",
      "as_of": "2026-07"
    }
  ],
  "creator_style_profile": {
    "creator_id": "……",
    "nickname": "……",
    "primary_format": "voiceover | subtitle_immersive",
    "structure_summary": "……",
    "product_integration_pattern": {"pattern": "……", "first_appearance_evidence": "……"},
    "do_not_copy": ["……"],
    "evidence": [{"note_id": "……", "quote": "……", "what_it_shows": "……"}]
  },
  "target_duration": 60,
  "content_scene": "早餐",
  "format": "voiceover | subtitle | hybrid"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `brand_brief.brand_name` / `product_name` | string | 是 | 品牌与产品名 |
| `brand_brief.selling_points[].claim` | string | 是 | 卖点关键词（校验器据此检测卖点句） |
| `brand_brief.selling_points[].forbidden_interpretations` | string[] | 是 | 禁用解读词（出现即判失败） |
| `product_evidence[].evidence_id` | string | 是 | 证据 ID，输出映射时引用 |
| `product_evidence[].claim` | string | 是 | 该证据支撑的卖点 |
| `creator_style_profile.do_not_copy[]` | string[] | 是 | 禁止复制的达人元素（原句语料来源之一） |
| `creator_style_profile.evidence[].quote` | string | 是 | 风格证据引文（原句语料来源之一，禁止复用） |
| `target_duration` | number | 是 | 目标时长（秒） |
| `content_scene` | string | 是 | 内容场景 |
| `format` | enum | 是 | `voiceover` / `subtitle` / `hybrid` |

## 2. 脚本输出（Script Output）

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `title_options` | string[] | ≥1 条候选标题 |
| `selected_title` | string | 必须属于 `title_options` |
| `hook` | object | `text`（非空）、`duration_s`（>0）、`design_basis`（借鉴依据） |
| `full_script` | Segment[] | ≥1 个分段；时间轴升序不重叠 |
| `full_script[].segment_id` | int | 分段编号 |
| `full_script[].start_time` / `end_time` | number | ≥0，且 `end_time > start_time` |
| `full_script[].voiceover` | string \| null | `voiceover`/`hybrid` 形态每段必填 |
| `full_script[].on_screen_text` | string \| null | `subtitle`/`hybrid` 形态每段必填 |
| `full_script[].shot_note` / `purpose` | string \| null | 分镜提示/分段目的 |
| `product_first_appearance` | object | `time_s`（≥0，须落入某分段区间且不超 `estimated_duration`）、`segment_id`、`rationale`（引用真实证据） |
| `integration_sentence` | string | 植入句，必须在 `full_script` 中逐字出现 |
| `CTA` | string | 行动号召，非空 |
| `estimated_duration` | number | >0；与 `target_duration` 偏差 ≤30% |
| `claim_evidence_map` | Entry[] | 见第 3 节 |
| `style_evidence_map` | Entry[] | ≥1 条，见第 4 节 |
| `unresolved_questions` | string[] | 可为空数组 |
| `format` | enum | 可选冗余字段；校验以输入 `format` 为准 |

## 3. claim_evidence_map 条目

```json
{"script_sentence": "……脚本中的原句……", "claim": "0蔗糖", "evidence_ids": ["EV-001"]}
```

- `script_sentence`：必须能在 `full_script`（voiceover/on_screen_text 切句后）中逐字找到。
- `claim`：必须属于输入的卖点词表（BrandBrief.selling_points + ProductEvidence.claim）。
- `evidence_ids`：≥1 个，且全部存在于 ProductEvidence。
- 覆盖要求：`full_script` 中每句含卖点关键词的句子（卖点句）都必须被条目覆盖，且句中每个关键词都有对应 `claim` 的条目。

## 4. style_evidence_map 条目

```json
{
  "script_element": "hook",
  "borrowed_pattern": "口语化问候+标题卡的共鸣开场",
  "source": {"creator": "欧盈Kelly", "note_id": "6989ab01000000001a0360c5", "evidence": "hook_analysis：……"},
  "adaptation": "文案原创，仅沿用结构"
}
```

- `source.evidence` 必须能指回真实证据位置（时间线 JSON 的 `hook_analysis`/`style_summary`/`segments`）。

## 5. 校验规则对应表

| 校验项（validate_output.py） | 规则 | 失败条件 |
| --- | --- | --- |
| `schema_valid` | 输出结构合法（pydantic 模型） | 缺字段/类型错误/时长非正数 |
| `internal_consistency` | 标题 ∈ 候选；时间轴升序不重叠；首现落入分段；植入句逐字出现 | 任一不满足 |
| `format_requirements` | 三种形态载体完整 | voiceover/hybrid 缺 `voiceover`；subtitle/hybrid 缺 `on_screen_text` |
| `claim_evidence_coverage` | 卖点句全覆盖；证据 ID 存在；无禁用解读词 | 未映射/假证据/出现 forbidden_interpretations |
| `duration_deviation` | 偏差 ≤30% | `abs(est-target)/target > 0.30` |
| `verbatim_copy_check` | 不得复制达人原句 | 语料（风格画像引文/do_not_copy 引号片段/时间线字幕与标题）归一化后 ≥6 字且出现于输出文本 |

## 6. CLI

```bash
python skills/xhs-commercial-script/scripts/validate_output.py OUTPUT.json \
    --input INPUT.json \
    --timelines data/processed/stage_3_top3_video_timelines.json \
    [--target-duration 60] [--min-copy-len 6]
```

退出码：0 = 全部通过；1 = 存在失败项或文件读取错误。
