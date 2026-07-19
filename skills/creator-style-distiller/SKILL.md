---
name: creator-style-distiller
description: 从达人真实视频证据中蒸馏"可复用风格规则"，供轻醒商单脚本生成借鉴。当需要分析指定达人的钩子、叙事结构、口播/字幕密度、镜头节奏、食物与商业植入方式并产出结构化风格卡时使用。严禁逐句复制、口头禅复制与身份仿冒。
---

# creator-style-distiller（达人风格蒸馏）

把一位达人的 ≥3 条真实视频证据蒸馏成一张**结构化风格卡**：只提炼"可迁移的手法"，
明确划出"不可复制的个人专属元素"。产物供脚本生成 Skill 借鉴风格，而非替达人写稿。

## 输入契约（缺一不可）

| 输入 | 说明 |
| --- | --- |
| creator profile | 达人基础画像（昵称、creator_id、主场景、主形式等） |
| ≥3 条视频 timeline | 分段结构须含起止时间、transcript_summary、on_screen_text、场景、镜头类型、证据时间戳 |
| transcript summary | 每段的转写摘要（转述文本，非逐字稿） |
| keyframe evidence | 关键帧抽样统计（如 interval/scene/deduped 数量） |
| commercial signals | 商单信号：产品首现时间、商业表达、是否自用展示等 |
| compliance risks | 每段合规风险标注（减肥/燃脂/医疗宣称等） |

参考样本：`data/processed/stage_3_top3_video_timelines.json`（真实数据，只读）。

## 输出契约

输出单个 JSON 对象，必填字段与类型见 `references/output-schema.md`：
hook_patterns、narrative_structure、sentence_rhythm、voiceover_density、
subtitle_density、shot_rhythm、scene_patterns、food_integration_patterns、
commercial_integration_patterns、CTA_patterns、reusable_style_rules、
creator_specific_elements_not_to_copy、confidence（0-1）、evidence_timestamps（非空）。

交付前必须运行校验器，退出码 0 方可交付：

```bash
python skills/creator-style-distiller/scripts/validate_output.py <output.json> --input <input.json>
```

## 工作流

1. 通读全部 timeline 与商业信号，按 `references/rules.md` 的取证规则逐字段提炼。
2. 每条风格规则必须挂证据（时间戳/字段引用），无证据不得写入；拿不准就降 confidence。
3. 区分"可复用手法"与"个人专属元素"，后者全部进 `creator_specific_elements_not_to_copy`。
4. 参照 `references/examples.md` 的转述示范写输出（基于欧盈Kelly真实 timeline）。
5. 运行校验器自检；用 `evals/evals.json` 中的用例回归。

## 铁律（详见 references/rules.md）

- 禁逐句复制达人台词/字幕；禁复制固定口头禅；禁身份仿冒；禁声称达人本人创作。
- 禁无证据的风格推断；所有结论可回溯到 timeline 时间戳。
- 风格借鉴不等于内容搬运：输出中不得出现与输入 transcript 超过 15 字的连续相同子串（校验器强制）。
