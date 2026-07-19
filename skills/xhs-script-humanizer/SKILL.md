---
name: xhs-script-humanizer
description: 小红书商单脚本"去 AI 腔"自然化 Skill。把 AI 生成的脚本改写为贴近达人真实语感的口播/字幕文本，同时逐字保留全部事实锚点（数字、百分比、品牌名、规格、品牌限定词），并显式上报可能的事实漂移。本 Skill 是流程中间节点：自然化后必须重新执行 fact_regression、compliance_review、style_consistency_review，三者全部通过才允许进入后续分镜与交付。
---

# xhs-script-humanizer（脚本自然化 Skill）

## 用途

将 AI 生成的小红书商单脚本（口播稿、字幕稿）改写为自然、口语化、贴近目标达人
风格的中文短视频文本，消除"AI 公文感"，同时保证：

- 事实零丢失：数字、百分比、品牌名、规格、口味、人群标签、品牌限定词逐字保留；
- 功效零新增：不得新增原稿没有的功效、对比或数据；
- 漂移必上报：任何拿捏不准的改写都写入 `possible_fact_drift`，交由复检与人工判断。

## 何时使用

- 脚本生成（多方向竞争）完成、且已通过初检之后；
- 分镜设计与最终交付之前；
- 原稿存在明显 AI 腔（公文连接词、连续排比、空洞形容词、句式整齐划一）时。

何时**不**使用：原稿尚未通过事实与合规初检时不得先做自然化——自然化不能替代、
也不能掩盖初检发现的问题。

## 输入

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| original_script | string | 是 | 待自然化的原始脚本（口播稿或字幕稿全文） |
| style_profile | object | 否 | 目标达人风格画像，建议字段：`creator_style`（如"口播型上班vlog"）、`tone`（如"松弛、自嘲"）、`sentence_length`（"短句为主"）、`reference`（画像来源文件路径） |

## 输出（JSON 契约）

```json
{
  "original_script": "原始脚本全文，与输入逐字一致",
  "humanized_script": "自然化后的脚本全文",
  "changes": [
    {
      "rule": "R1",
      "before": "改写前片段",
      "after": "改写后片段",
      "reason": "改写理由（对应 rules.md 规则）"
    }
  ],
  "preserved_facts": ["0蔗糖", "22-35岁", "品牌名：轻醒"],
  "possible_fact_drift": [],
  "style_match_score": 0.88
}
```

字段约束（由 `validate_output.py` 机器校验）：

- `changes[].rule` 只能取 rules.md 中的规则编号 `R1` ~ `R8`；
- `original_script` 中出现的全部数字/百分比 token 与品牌名，必须出现在
  `preserved_facts` 中，且在 `humanized_script` 里逐字保留、未被改变；
- `possible_fact_drift` 非空时，`style_match_score` 不得大于 0.9；
- `style_match_score` 取值范围 [0, 1]。

## 编排位置（强制）

**Humanizer 永远不是最终节点。** 本 Skill 在流水线中的位置固定为：

```
脚本生成（三方向竞争）→ 事实/合规初检
  → xhs-script-humanizer（本 Skill，对应 config/quality_gates.yaml 的 stage_8）
  → fact_regression（事实回归复检：事实锚点与证据逐项比对）
  → compliance_review（合规复检：违禁词、功效表述、绝对化表达）
  → style_consistency_review（风格一致性复检：与 style_profile 比对）
  → 全部通过 → 分镜与拍摄可行性设计（stage_9）→ 交付
```

- 三项复检必须以 `humanized_script` 为对象重新执行，不得沿用初检结论；
- 任一复检不通过，退回脚本生成或人工介入，禁止带着未复检的自然化稿进入交付；
- `possible_fact_drift` 非空的输出必须经人工确认后才能放行。

## 执行步骤

1. 通读 `original_script`，先提取全部事实锚点（数字、百分比、品牌名、规格、
   口味、人群标签、品牌限定词），列出清单——这份清单就是 `preserved_facts` 的底稿；
2. 按 rules.md 的 R1 ~ R6 逐条扫描并改写表达层问题；
3. 改写全程执行 R7（事实锚点锁定）与 R8（功效零新增）两条红线；
4. 有 `style_profile` 时，按其语感校准节奏与用词，给出 `style_match_score`；
   拿捏不准的事实性改写写入 `possible_fact_drift`；
5. 逐条填写 `changes`，保证每处实质改动都可追溯到某条规则；
6. 调用 `validate_output.py` 自检输出契约；
7. 将输出交给下游三项复检（见"编排位置"）。

## 校验

```bash
python skills/xhs-script-humanizer/validate_output.py output.json --brand-term 轻醒
```

退出码 0 表示契约校验通过；非 0 表示存在 schema 错误、事实锚点丢失/被篡改或
评分一致性问题，错误以 JSON 形式输出到 stdout。

## 文件清单

| 文件 | 作用 |
| --- | --- |
| SKILL.md | 本文件：用途、契约、编排位置、执行步骤 |
| rules.md | 中文短视频自然化规则 R1 ~ R8（自研）与红线 |
| examples.md | 一段 AI 腔轻醒酸奶脚本 → 自然化版本的完整对照（原创示例） |
| evals.json | 3 条真实场景 eval + 1 条反例（事实被篡改必须判失败） |
| validate_output.py | 输出契约校验器（schema + 事实保留 + 评分一致性） |

## 方法论来源声明

- 规则（rules.md）全部为项目自研，基于真实达人语料形态
  （data/processed/stage_3_top3_video_timelines.json）与轻醒合规要求总结；
- 组件准入档案中的 CAND-013（blader/humanizer）与 CAND-014（op7418/Humanizer-zh）
  均为 `reference_only`，仅作"识别 AI 痕迹"方法论参考，**未复制其任何
  SKILL.md、规则清单或代码**（见 registry/THIRD_PARTY_NOTICES.md 与
  reports/component_reviews/CAND-013-humanizer.md、CAND-014-Humanizer-zh.md）；
- 示例与 eval 中的品牌事实仅取自 data/raw/qingxing_brief.md
  （0蔗糖、高蛋白、原味/蓝莓/黄桃、22-35岁、早餐/运动后/下午茶），
  不含任何虚构的营养检测数字。
