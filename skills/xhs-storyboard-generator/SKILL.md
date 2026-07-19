---
name: xhs-storyboard-generator
description: 将小红书商单脚本（full_script）结合达人风格画像（style_profile）与场景约束，展开为逐镜头分镜表。当需要把脚本转成可拍摄的分镜、规划镜头时长/运镜/产品露出时点，或校验分镜是否满足小红书单人手机实拍时使用。
---

# 小红书分镜生成 Skill

把一份商单脚本展开为**单人 + 手机即可执行**的逐镜头分镜表，并保证成片总时长与脚本一致、产品露出时点不早于脚本设定。

## 适用范围

- 平台：小红书竖屏短视频（9:16）。
- 品牌语境：轻醒 0 蔗糖高蛋白希腊酸奶；场景为早餐 / 一人食 / 通勤 / 办公室下午茶 / 运动后加餐。
- 执行约束：1 人拍摄、手机拍摄、家庭 / 通勤 / 办公室真实场景、道具数量受控。
- 合规红线：禁止减肥 / 燃脂 / 掉秤 / 降糖 / 医疗效果 / 绝对化表达；「0 蔗糖」不得写作「无糖」；功效表述须有 ProductEvidence 支撑（详见 `rules.md`）。

## 输入

```json
{
  "full_script": {
    "script_id": "string",
    "title": "string",
    "format": "voiceover | subtitle_immersive",
    "total_duration_s": 21.0,
    "product_first_appearance_s": 6.4,
    "beats": [
      {
        "beat_id": "b1",
        "start_time": 0.0,
        "end_time": 2.0,
        "purpose": "hook | process | product | lifestyle | ending",
        "scene": "餐桌",
        "action": "端起成品酸奶碗展示",
        "spoken_line": null,
        "on_screen_text": null
      }
    ]
  },
  "target_duration": 21.0,
  "style_profile": {
    "creator_id": "5ad034864eacab543fa98374",
    "primary_format": "subtitle_immersive",
    "avg_shot_s": 2.0,
    "narration_relation": "无口播；字幕极少且只做制作说明与口感点评",
    "reusable_high_level": ["成品先行开场", "线性制作流程"]
  },
  "scene_constraints": {
    "scene": "早餐",
    "location_options": ["家中厨房台面", "餐桌"],
    "max_props": 8,
    "crew": 1,
    "equipment": ["手机"]
  }
}
```

- `full_script`：上游脚本 Skill 的产出，beats 时间轴连续且总时长等于 `total_duration_s`。
- `target_duration`：成片目标时长（秒），默认取 `full_script.total_duration_s`。
- `style_profile`：达人风格画像，决定镜头平均时长、口播 / 字幕形态、机位偏好。真实证据见 `data/processed/stage_3_top3_video_timelines.json`：欧盈Kelly 平均镜头 2.4s（口播型）、小季没烦恼 2.5s（字幕型）、一只牛 2.0s（字幕型）。
- `scene_constraints`：场景与资源约束；缺省按 `rules.md` 的默认值（1 人、手机、道具 ≤8 件）。

## 输出

分镜 JSON（schema_version `1.0`）。顶层字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema_version` | str | 固定 `"1.0"` |
| `storyboard_id` | str | 分镜唯一标识 |
| `scene` | str | 场景名，如 `早餐` |
| `aspect_ratio` | str | 固定 `"9:16"` |
| `target_duration_s` | number | 目标时长 |
| `actual_total_duration_s` | number | 末镜头 `end_time`，与目标偏差 ≤3s |
| `product_first_appearance_s` | number \| null | 取自脚本的产品首次露出时点 |
| `shots` | list | 镜头数组，时间轴从 0.0 连续无重叠 |

每个镜头 21 个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `shot_id` | str | 如 `s01` |
| `start_time` / `end_time` / `duration` | number | 秒；`duration = end_time - start_time` |
| `visual` | str | 画面内容描述（拍什么、怎么构图） |
| `shot_size` | str | 特写 / 近景 / 中景 / 全景 / 空镜，可用 `+` 组合 |
| `camera_position` | str | 俯拍 / 平视 / 仰拍 / 第一人称 / 自拍视角 / 固定机位 |
| `camera_motion` | str | 仅允许单人手机可完成的：固定 / 手持微晃 / 缓慢推进 / 跟随平移 / 俯拍下移 / 抬起转向；**禁止无人机、航拍、轨道、滑轨、摇臂、吊臂、斯坦尼康等**（完整黑名单见 `rules.md`，命中即判失败） |
| `person_action` | str | 人物动作 |
| `spoken_line` | str \| null | 口播台词；字幕沉浸式形态为 null |
| `on_screen_text` | str \| null | 屏幕字幕；口播型可为时间戳 / 情绪梗 |
| `product_state` | str | 未出现 / 入镜静置 / 手持展示 / 特写展示 / 开封·使用中 / 食用·饮用中 |
| `product_exposure` | bool | 是否为产品露出镜头；露出镜头的 `start_time` 不得早于 `product_first_appearance_s` |
| `props` | list[str] | 道具清单，单镜 ≤8 件 |
| `location` | str | 真实可拍地点，如 `家中厨房台面` |
| `bgm_or_sound` | str \| null | BGM 或环境音说明 |
| `transition` | str | 硬切 / 跳切 / 淡入淡出 / 叠化 |
| `shooting_difficulty` | str | `easy` / `medium` / `hard` |
| `compliance_note` | str \| null | 本镜合规说明（卖点依据、个人体验语境等） |
| `script_source` | str | 对应脚本 beat_id |
| `style_evidence` | str | 风格依据，须可溯源，如 `一只牛 avg_shot_s=2.0（data/processed/stage_3_top3_video_timelines.json）` |

## 工作流

1. 读取 `full_script`，确认 beats 时间轴连续、记录 `product_first_appearance_s`。
2. 按 `style_profile.avg_shot_s` 估算镜头数：`镜头数 ≈ target_duration / avg_shot_s`；口播型可适当拉长至 2–4s，字幕沉浸式保持 2–3s 快切。
3. 逐 beat 拆镜：hook 镜优先用「成品先行」或「口语化问候 + 标题卡」；产品露出首镜不得早于 `product_first_appearance_s`；植入段采用「需求场景 → 产品解法」结构。
4. 逐镜填写 21 个字段，`camera_motion` 只从可执行集合中选取；道具合并同类项，单镜 ≤8 件。
5. 每镜写 `compliance_note`：对照品牌红线自查本镜字幕 / 口播；涉及「饱腹感」等主观体验必须使用个人体验语境（「我觉得」「对我来说」）。
6. 汇总 `actual_total_duration_s`（= 末镜头 `end_time`），与 `target_duration_s` 偏差须 ≤3s，否则增删镜头或调整单镜时长。
7. **必须**运行校验器通过后才可交付：

```bash
python skills/xhs-storyboard-generator/scripts/validate_output.py storyboard.json --script script.json
```

退出码 0 为通过（允许 warning），1 为失败；失败项须逐条修复后重验。

## 配套文件

- `references/rules.md`：可执行性铁律、运镜黑名单、时长证据、合规红线、道具与场景约束。
- `references/examples.md`：早餐场景脚本 → 9 镜完整分镜示例（可直接当模板）。
- `references/output-schema.md`：输出契约逐条说明（与校验器一一对应）。
- `evals/evals.json`：3 个真实 eval（2 正例 + 1 反校验例）+ 1 个不可执行运镜反例。
- `scripts/validate_output.py`：输出校验器（schema / 时间轴 / 总时长 / 可执行性 / 产品露出时点）。
