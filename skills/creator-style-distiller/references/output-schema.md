# 输出契约（output-schema）

输出为单个 UTF-8 JSON 对象。字段名、类型、约束如下，校验器
`skills/creator-style-distiller/scripts/validate_output.py` 与本文件逐条对应。

## 顶层必填字段

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| hook_patterns | array<object> | 非空；item 见下 |
| narrative_structure | object | 含非空 `phases` |
| sentence_rhythm | object | 含 `style`、`features` |
| voiceover_density | object | `mode` 为枚举 |
| subtitle_density | object | `level` 为枚举 |
| shot_rhythm | object | `avg_shot_s` 为正数 |
| scene_patterns | array<object> | 非空 |
| food_integration_patterns | array<object> | 可为空数组（无食物内容时） |
| commercial_integration_patterns | array<object> | 可为空数组（无商业表达时） |
| CTA_patterns | array<object> | 可为空数组（无 CTA 时） |
| reusable_style_rules | array<string> | 非空；每条为转述后的手法规则 |
| creator_specific_elements_not_to_copy | array<string> | 非空；个人专属元素清单 |
| confidence | number | 0 ≤ x ≤ 1 |
| evidence_timestamps | array<number \| [number, number]> | 非空；单点或 [起, 止] 区间 |

## item 结构

### hook_patterns[]

```json
{ "pattern": "钩子手法（转述）", "evidence": "证据定位（段/时间戳/字段）", "timestamps": [0.0, 4.0] }
```

- `pattern`（string，必填）、`evidence`（string，必填）、`timestamps`（array<number>，可选）。

### narrative_structure

```json
{
  "arc": "整体叙事弧线概括（转述）",
  "phases": [ { "name": "阶段名", "description": "该阶段功能", "time_range_s": [0.0, 4.0] } ],
  "notes": "可选补充"
}
```

- `arc`（string，必填）；`phases`（非空 array，item 必填 `name`、`description`，`time_range_s` 可选）。

### sentence_rhythm

```json
{ "style": "句式节奏概括", "features": ["特征1", "特征2"], "avg_sentence_length_chars": 18 }
```

- `style`（string，必填）、`features`（array<string>，必填）；`avg_sentence_length_chars`（number，可选）。

### voiceover_density

```json
{ "mode": "voiceover", "estimated_speech_ratio": 0.7, "notes": "可选" }
```

- `mode`（必填，枚举：`voiceover` / `subtitle_immersive` / `mixed` / `none`）；
  `estimated_speech_ratio`（number，0-1，可选）。

### subtitle_density

```json
{ "level": "high", "functions": ["时间戳", "情绪梗"], "notes": "可选" }
```

- `level`（必填，枚举：`none` / `low` / `medium` / `high`）；`functions`（array<string>，必填）。

### shot_rhythm

```json
{ "avg_shot_s": 2.4, "pacing": "快切", "shot_types": ["自拍仰拍", "固定机位中景"] }
```

- `avg_shot_s`（number > 0，必填）、`pacing`（string，必填）、`shot_types`（array<string>，必填）。

### scene_patterns[]

```json
{ "scene": "场景名", "role": "在叙事中的功能（可选）" }
```

- `scene`（string，必填）。

### food_integration_patterns[] / commercial_integration_patterns[]

```json
{ "pattern": "植入手法（转述）", "evidence": "证据定位", "insertion_point_s": 14.0 }
```

- `pattern`、`evidence`（string，必填）；`insertion_point_s`（number，可选）。

### CTA_patterns[]

```json
{ "pattern": "行动引导手法（转述）", "evidence": "可选" }
```

- `pattern`（string，必填）；无 CTA 时整个字段给空数组 `[]`。

## 全局硬校验（validate_output.py）

1. 顶层为 JSON 对象，14 个必填字段全部存在。
2. 类型、枚举、数值范围如上表。
3. `confidence ∈ [0, 1]`。
4. `evidence_timestamps` 非空，元素为 number 或二元 number 数组。
5. 传入 `--input <input.json>` 时执行禁复制校验：输出中任意字符串与输入里的
   transcript 类文本（`transcript_summary`、`on_screen_text`、`transcript`、`asr_text`、
   `subtitle(s)`、`voiceover_text` 字段，递归收集）不得存在超过 15 字的连续相同子串
   （比较前剔除全部空白字符）。命中即失败。
6. 退出码：0 = 通过；1 = 校验失败；2 = 用法/文件错误。
