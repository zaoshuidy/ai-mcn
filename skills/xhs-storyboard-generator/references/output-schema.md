# 输出契约（output-schema）

输出为单个 UTF-8 JSON 对象（分镜表，schema_version `1.0`）。字段名、类型、约束如下，
校验器 `skills/xhs-storyboard-generator/scripts/validate_output.py` 与本文件逐条对应。

## 顶层必填字段

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| schema_version | string | 固定 `"1.0"` |
| storyboard_id | string | 非空，分镜唯一标识 |
| scene | string | 场景名，如 `早餐` |
| aspect_ratio | string | 固定 `"9:16"` |
| target_duration_s | number | > 0，目标时长（秒） |
| actual_total_duration_s | number | 末镜头 `end_time`；与目标偏差 ≤ 3s |
| product_first_appearance_s | number \| null | 取自脚本的产品首次露出时点 |
| shots | array<object> | 非空；时间轴从 0.0 起连续、无重叠 |

## shots[] item（21 个字段）

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| shot_id | string | 如 `s01`，唯一 |
| start_time / end_time / duration | number | `duration = end_time - start_time` |
| visual | string | 画面内容描述 |
| shot_size | string | 特写 / 近景 / 中景 / 全景 / 空镜，可 `+` 组合 |
| camera_position | string | 俯拍 / 平视 / 仰拍 / 第一人称 / 自拍视角 / 固定机位 |
| camera_motion | string | 仅允许：固定 / 手持微晃 / 缓慢推进 / 跟随平移 / 俯拍下移 / 抬起转向；运镜黑名单（无人机、航拍、轨道、滑轨、摇臂、吊臂、斯坦尼康等）命中即判失败 |
| person_action | string | 人物动作 |
| spoken_line | string \| null | 口播台词；字幕沉浸式形态为 null |
| on_screen_text | string \| null | 屏幕字幕 |
| product_state | string | 未出现 / 入镜静置 / 手持展示 / 特写展示 / 开封·使用中 / 食用·饮用中 |
| product_exposure | boolean | 露出镜头的 `start_time` 不得早于 `product_first_appearance_s` |
| props | array<string> | 单镜 ≤ 8 件 |
| location | string | 真实可拍地点 |
| bgm_or_sound | string \| null | BGM 或环境音说明 |
| transition | string | 硬切 / 跳切 / 淡入淡出 / 叠化 |
| shooting_difficulty | string | `easy` / `medium` / `hard` |
| compliance_note | string \| null | 本镜合规说明 |
| script_source | string | 对应脚本 beat_id |
| style_evidence | string | 风格依据，须可溯源到证据文件 |

## 全局硬校验（scripts/validate_output.py）

1. 顶层 8 个必填字段全部存在，类型与取值如上表。
2. `shots` 时间轴从 0.0 起连续、无重叠；每镜 `duration = end_time - start_time`。
3. `actual_total_duration_s` 与 `target_duration_s` 偏差 ≤ 3s。
4. 产品露出首镜 `start_time ≥ product_first_appearance_s`。
5. `camera_motion` 全部来自单人手机可执行集合，黑名单命中即失败。
6. 单镜 `props ≤ 8` 件。
7. 传入 `--script <script.json>` 时执行脚本一致性校验（beat 来源与时长）。
8. 退出码：0 = 通过（允许 warning）；1 = 校验失败；2 = 用法/文件错误。

## 用法

```bash
python skills/xhs-storyboard-generator/scripts/validate_output.py storyboard.json --script script.json
```
