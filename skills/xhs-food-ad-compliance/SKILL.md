---
name: xhs-food-ad-compliance
description: 小红书食品商单脚本/分镜的合规预审 Skill（只审核不创作）。当需要检查脚本或分镜文本是否触碰食品广告合规红线（减肥/燃脂/掉秤、降糖/控糖功效、医疗效果、绝对化用语、主观体验客观化、无证据卖点、竞品贬低），并产出结构化审核报告（risk_level / violations / evidence_mapping / required_changes / optional_changes / passed / human_review_required）时使用。位于脚本生成、Humanizer、分镜之后，交付之前。
---

# 小红书食品广告合规审核 Skill

## 1. 定位

- 本 Skill 对应工作流「食品广告合规与事实质检」阶段的审核环节，位于脚本生成、
  Humanizer、分镜（storyboard）之后，飞书交付/对外发布之前。
- **只审核，不创作**：不重写整段脚本、不新增卖点、不美化文案。对违规处只给出最小
  修改指令（删除 / 替换 / 弱化 / 标 blocked）；需要整段改写的，退回脚本生成侧处理。
- 审核对象是文本：口播稿、屏幕字幕、标题、话题标签，以及分镜中的文案字段
  （on_screen_text / 口播台词 / 产品露出说明）。
- 本 Skill 是内容预审，不替代品牌方法务意见；拿不准的一律
  `human_review_required=true`，宁可多报、不可漏报。

## 2. 铁律

1. **不虚构证据**：ProductEvidence 中不存在的依据不得当作存在；`claim_type` 不得擅自
   升级（如 brand_claim 不得当 confirmed 用）。
2. **违规必须落到规则 ID**：每条 violation 必须引用 `references/rules.md` 中已有的规则
   ID；规则库未覆盖的疑似问题，记入 `optional_changes` 并置
   `human_review_required=true`，不得自行发明规则 ID。
3. **卖点必须完成证据映射**：脚本中所有成分/营养/功效类主张逐条映射 ProductEvidence；
   映射不到 confirmed / brand_claim 证据的，`status=blocked`。
4. **结论可复核**：violations 必须引用 `matched_text` 原文与位置（口播第 N 句 / 字幕第
   N 条 / 标题 / 话题标签 / 分镜第 N 镜），不得只给结论不给证据。

## 3. 输入契约

```json
{
  "script_text": "脚本文本（口播/字幕/标题/话题标签），或分镜文案的拼接文本",
  "text_kind": "script | storyboard",
  "product_evidence": [
    {
      "claim": "0蔗糖",
      "claim_type": "brand_claim",
      "evidence": null,
      "note": "提取自产品名称，依据待品牌方提供",
      "forbidden_interpretations": ["无糖"]
    }
  ],
  "brand_rules": ["可选：品牌方追加的自定义禁用表达"]
}
```

- `product_evidence` 即 ProductEvidence 清单，字段对齐 Stage 1 数据契约
  （`src/brief_models.py` 的 `SellingPoint`：claim / claim_type / evidence / note /
  forbidden_interpretations）；真实样例见 `data/processed/qingxing_brief.json` 的
  `selling_points`。
- `claim_type` 四档，决定卖点可用的表述方式：
  - `confirmed`：有包装/检测报告等品牌方依据的事实声明，可按依据原文使用；
  - `brand_claim`：品牌方主张但暂无依据，可提及但不得升级为事实、不得加数值；
  - `subjective_experience`：主观体验，只允许出现在个人体验语境
    （「我觉得」「对我来说」）；
  - `unverified`：未经验证，不得作为产品卖点表述为事实或功效。
- 缺少 `product_evidence` 时不得凭空审核：直接输出 `passed=false`、
  `human_review_required=true`，并在 `optional_changes` 说明缺少证据清单。

## 4. 输出契约

只输出一个 JSON 对象，字段如下（七个字段为强制字段，不得缺省）：

```json
{
  "risk_level": "none | low | medium | high | critical",
  "violations": [
    {
      "rule_id": "FAC-001",
      "rule_name": "0蔗糖不得表述为无糖",
      "severity": "high",
      "matched_text": "违规原文",
      "location": "口播第3句 / 字幕第2条 / 标题 / 话题标签 / 分镜第N镜",
      "issue": "问题说明",
      "suggestion": "最小修改指令"
    }
  ],
  "evidence_mapping": [
    {
      "claim_in_script": "脚本中出现的卖点表述",
      "matched_product_claim": "映射到的 ProductEvidence.claim，无映射为 null",
      "claim_type": "confirmed | brand_claim | subjective_experience | unverified | null",
      "status": "supported | brand_claim_context | subjective_only | blocked",
      "note": "映射说明（如 forbidden_interpretations 命中情况）"
    }
  ],
  "required_changes": [
    {
      "violation_rule_id": "FAC-001",
      "original": "原文",
      "replacement": "修改后文本或「删除」",
      "reason": "修改理由（含规则 ID）"
    }
  ],
  "optional_changes": [
    {
      "original": "原文",
      "suggestion": "可选优化建议",
      "reason": "理由"
    }
  ],
  "passed": true,
  "human_review_required": false
}
```

### 证据映射状态（evidence_mapping.status）

| status | 含义 | 对脚本的要求 |
| --- | --- | --- |
| supported | 映射到 confirmed 且有 evidence | 可按依据原文使用 |
| brand_claim_context | 映射到 brand_claim | 可提及，不得升级为事实/数值；须人工复核 |
| subjective_only | 映射到 subjective_experience | 仅允许个人体验语境 |
| blocked | 映射到 unverified 却被表述为事实/功效，或映射不到任何证据条目 | 必须删除或退回脚本生成侧改写 |

## 5. 审核流程

1. **文本归一化**：合并口播、字幕、标题、话题标签与分镜文案，逐句/逐条编号，保留
   位置信息（位置写法见 violations.location）。
2. **规则扫描**：加载 `references/rules.md`，按 FAC-001 ~ FAC-010 逐条匹配；命中时记录
   matched_text 与位置，并按规则中的「判定」小节做语境豁免判断（如「我最爱」不构成
   绝对化用语）。
3. **证据映射**：提取脚本中全部成分/营养/功效类主张，逐条映射 `product_evidence`，
   产出 evidence_mapping；检查 forbidden_interpretations 命中情况。
4. **定级与产出**：取所有违规的最高严重级为 risk_level；组装 required_changes /
   optional_changes，判定 passed 与 human_review_required。

## 6. 判定规则

- `risk_level`：等于 violations 中的最高严重级（critical > high > medium > low）；
  无违规为 `none`。
- `passed`：无 critical / high 违规，且 evidence_mapping 中无 `blocked`，方为 `true`。
- `human_review_required`：满足任一条件即为 `true`——
  1. 任一 critical / high 违规；
  2. evidence_mapping 中存在 `blocked` 或 `brand_claim_context`；
  3. 文本含规则库未覆盖的疑似灰色表达（记入 optional_changes）；
  4. 输入缺少 product_evidence 或脚本上下文不足以判断语境。

## 7. 配套文件

- 规则库：`references/rules.md`（FAC-001 ~ FAC-010，逐条含规则 ID / 模式 / 严重级 /
  判定 / 修改建议 / 依据）。
- 输出 Schema：`references/output-schema.md`（审核报告 JSON Schema，机器可校验）。
- 示例：`references/examples.md`（一段含多处违规的轻醒脚本示例 + 完整审核输出 +
  通过样例对照）。
- Evals：`evals/evals.json`（3 条真实 eval：示例 1 违规报告 / 示例 2 全合规报告 /
  真实轻醒自然化稿审核报告 + 1 条一致性冲突反例，校验器必须判失败）。

## 8. 边界

- 法规引用仅为合规依据方向（《广告法》《食品安全法》相关条款），具体案件以品牌方
  法务意见为准。
- 本 Skill 不审核画面内容（产品露出、镜头）；画面合规属于分镜阶段的独立检查项。
- 本 Skill 不判断脚本质量与风格匹配度，只判断合规与证据映射。
