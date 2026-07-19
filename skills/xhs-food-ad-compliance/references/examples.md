# 审核示例（xhs-food-ad-compliance）

> 示例品牌为轻醒「0蔗糖高蛋白希腊酸奶」，ProductEvidence 取自项目真实数据契约
> `data/processed/qingxing_brief.json` 的 `selling_points`（截至 Stage 1 全部无品牌方
> 依据文件：高蛋白=brand_claim、饱腹感=subjective_experience、低负担=unverified、
> 0蔗糖=brand_claim）。

## 示例 1：含多处违规的脚本（字幕型早餐 vlog，约 55s）

### 输入

```json
{
  "script_text": "标题：控糖期最健康的早餐，无糖酸奶真的绝了\n字幕1：打工人早餐不知道吃啥的姐妹看过来\n字幕2：最近挖到轻醒这款无糖希腊酸奶，0糖0负担\n字幕3：每杯15g蛋白质，喝一杯扛饿一上午\n字幕4：不升糖，控糖期放心喝，还能养胃\n字幕5：喝它不怕胖，小肚子都平了\n字幕6：比其他酸奶配料干净多了，完胜便利店\n话题标签：#早餐 #减肥餐 #控糖饮食",
  "text_kind": "script",
  "product_evidence": [
    {"claim": "高蛋白", "claim_type": "brand_claim", "evidence": null,
     "note": null, "forbidden_interpretations": []},
    {"claim": "饱腹感", "claim_type": "subjective_experience", "evidence": null,
     "note": null, "forbidden_interpretations": ["减重", "抑制食欲"]},
    {"claim": "低负担", "claim_type": "unverified", "evidence": null,
     "note": null, "forbidden_interpretations": ["不长胖", "零负担", "减肥"]},
    {"claim": "0蔗糖", "claim_type": "brand_claim", "evidence": null,
     "note": "提取自产品名称，依据待品牌方提供", "forbidden_interpretations": ["无糖"]}
  ],
  "brand_rules": []
}
```

### 输出（审核报告）

```json
{
  "risk_level": "critical",
  "violations": [
    {
      "rule_id": "FAC-001",
      "rule_name": "0蔗糖不得表述为无糖",
      "severity": "high",
      "matched_text": "无糖酸奶真的绝了",
      "location": "标题",
      "issue": "ProductEvidence 仅有「0蔗糖」（brand_claim，forbidden_interpretations 含「无糖」），标题升级为「无糖」",
      "suggestion": "改为「0蔗糖酸奶」或删除糖分表述"
    },
    {
      "rule_id": "FAC-001",
      "rule_name": "0蔗糖不得表述为无糖",
      "severity": "high",
      "matched_text": "无糖希腊酸奶，0糖0负担",
      "location": "字幕2",
      "issue": "「无糖」「0糖」均属 0蔗糖→无糖 的禁止解释",
      "suggestion": "改为「0蔗糖希腊酸奶」"
    },
    {
      "rule_id": "FAC-009",
      "rule_name": "unverified 卖点不得表述为事实（低负担类）",
      "severity": "high",
      "matched_text": "0负担",
      "location": "字幕2",
      "issue": "「低负担」claim_type=unverified，且「0负担/零负担」命中其 forbidden_interpretations",
      "suggestion": "删除「0负担」"
    },
    {
      "rule_id": "FAC-002",
      "rule_name": "无证据不得标注营养数值",
      "severity": "high",
      "matched_text": "每杯15g蛋白质",
      "location": "字幕3",
      "issue": "ProductEvidence 无 confirmed 营养数据（蛋白质=brand_claim，evidence=null），不得标注具体克数",
      "suggestion": "删除「15g」，改为「高蛋白」定性表述（保留 brand_claim 语境，不加数值）"
    },
    {
      "rule_id": "FAC-007",
      "rule_name": "主观体验不得表述为客观功效",
      "severity": "medium",
      "matched_text": "喝一杯扛饿一上午",
      "location": "字幕3",
      "issue": "饱腹感为 subjective_experience，此处量化为普遍功效（扛饿一上午），未使用个人体验语境",
      "suggestion": "改为「我吃完到中午都不太想零食」式个人体验表达，或删除"
    },
    {
      "rule_id": "FAC-004",
      "rule_name": "禁止降糖/控糖功效承诺",
      "severity": "high",
      "matched_text": "不升糖，控糖期放心喝",
      "location": "字幕4",
      "issue": "「不升糖」为血糖功效承诺；「控糖」指向产品能力而非人群标签",
      "suggestion": "整句删除；如需保留人群语境，改为「控糖的姐妹看过来」并移至开头人群定位"
    },
    {
      "rule_id": "FAC-005",
      "rule_name": "禁止医疗效果",
      "severity": "critical",
      "matched_text": "还能养胃",
      "location": "字幕4",
      "issue": "「养胃」属医疗效果暗示，食品广告不得涉及疾病预防、治疗功能",
      "suggestion": "删除「还能养胃」"
    },
    {
      "rule_id": "FAC-003",
      "rule_name": "禁止减肥/燃脂/掉秤等减重功效",
      "severity": "high",
      "matched_text": "喝它不怕胖，小肚子都平了",
      "location": "字幕5",
      "issue": "「不怕胖」「小肚子都平了」为减重功效的明示/暗示表达",
      "suggestion": "整句删除，改为口感或场景描述"
    },
    {
      "rule_id": "FAC-010",
      "rule_name": "禁止贬低竞品",
      "severity": "medium",
      "matched_text": "比其他酸奶配料干净多了，完胜便利店",
      "location": "字幕6",
      "issue": "「完胜」及「比其他酸奶…多了」构成对其他生产经营者的贬低性对比",
      "suggestion": "删除对比，仅保留「配料表很干净」式自身特点描述（且不含对比贬损）"
    },
    {
      "rule_id": "FAC-006",
      "rule_name": "禁止绝对化表达",
      "severity": "medium",
      "matched_text": "最健康的早餐",
      "location": "标题",
      "issue": "「最健康」为指向产品的绝对化用语",
      "suggestion": "改为具体场景描述，如「打工人的快手早餐」"
    },
    {
      "rule_id": "FAC-003",
      "rule_name": "禁止减肥/燃脂/掉秤等减重功效",
      "severity": "high",
      "matched_text": "#减肥餐",
      "location": "话题标签",
      "issue": "话题标签同样属于广告文本，#减肥餐 暗示减重功效",
      "suggestion": "删除该标签，可换为 #快手早餐 #打工人早餐"
    }
  ],
  "evidence_mapping": [
    {
      "claim_in_script": "无糖 / 0糖",
      "matched_product_claim": "0蔗糖",
      "claim_type": "brand_claim",
      "status": "blocked",
      "note": "命中 forbidden_interpretations（无糖），属禁止解释方向"
    },
    {
      "claim_in_script": "每杯15g蛋白质",
      "matched_product_claim": "高蛋白",
      "claim_type": "brand_claim",
      "status": "blocked",
      "note": "brand_claim 不得升级为事实并标注数值；品牌方未提供营养成分表"
    },
    {
      "claim_in_script": "扛饿一上午",
      "matched_product_claim": "饱腹感",
      "claim_type": "subjective_experience",
      "status": "subjective_only",
      "note": "仅允许个人体验语境，当前为量化功效表达"
    },
    {
      "claim_in_script": "0负担",
      "matched_product_claim": "低负担",
      "claim_type": "unverified",
      "status": "blocked",
      "note": "unverified 不得表述为事实，且命中 forbidden_interpretations（零负担）"
    },
    {
      "claim_in_script": "不升糖 / 养胃 / 不怕胖",
      "matched_product_claim": null,
      "claim_type": null,
      "status": "blocked",
      "note": "ProductEvidence 中无任何对应卖点，且分别命中 FAC-004 / FAC-005 / FAC-003"
    }
  ],
  "required_changes": [
    {
      "violation_rule_id": "FAC-001",
      "original": "标题：控糖期最健康的早餐，无糖酸奶真的绝了",
      "replacement": "标题：打工人的快手早餐，0蔗糖酸奶真的绝了",
      "reason": "FAC-001 无糖→0蔗糖；FAC-006 删除绝对化「最健康」；「控糖」移出产品语境"
    },
    {
      "violation_rule_id": "FAC-001",
      "original": "字幕2：最近挖到轻醒这款无糖希腊酸奶，0糖0负担",
      "replacement": "字幕2：最近挖到轻醒这款0蔗糖希腊酸奶",
      "reason": "FAC-001 无糖/0糖→0蔗糖；FAC-009 删除「0负担」"
    },
    {
      "violation_rule_id": "FAC-002",
      "original": "字幕3：每杯15g蛋白质，喝一杯扛饿一上午",
      "replacement": "字幕3：高蛋白的一杯，我吃完到中午都不太想零食",
      "reason": "FAC-002 删除无证据数值；FAC-007 改个人体验语境"
    },
    {
      "violation_rule_id": "FAC-004",
      "original": "字幕4：不升糖，控糖期放心喝，还能养胃",
      "replacement": "删除",
      "reason": "FAC-004 血糖功效承诺；FAC-005 医疗效果暗示，整句不可局部修补"
    },
    {
      "violation_rule_id": "FAC-003",
      "original": "字幕5：喝它不怕胖，小肚子都平了",
      "replacement": "删除",
      "reason": "FAC-003 减重功效"
    },
    {
      "violation_rule_id": "FAC-010",
      "original": "字幕6：比其他酸奶配料干净多了，完胜便利店",
      "replacement": "字幕6：配料表很干净，早餐来一杯很清爽",
      "reason": "FAC-010 删除竞品贬低，仅保留自身特点"
    },
    {
      "violation_rule_id": "FAC-003",
      "original": "话题标签：#早餐 #减肥餐 #控糖饮食",
      "replacement": "话题标签：#早餐 #快手早餐 #打工人早餐",
      "reason": "FAC-003 删除 #减肥餐；#控糖饮食 仅指向人群，建议同步复核（见 optional_changes）"
    }
  ],
  "optional_changes": [
    {
      "original": "话题标签 #控糖饮食",
      "suggestion": "「控糖」作为人群兴趣标签可保留，但建议人工复核其与正文语境的组合效果，避免被读为产品功效",
      "reason": "轻醒 brief 契约：控糖仅可作为人群兴趣标签（audience_interest_not_product_claim）"
    },
    {
      "original": "字幕1：打工人早餐不知道吃啥的姐妹看过来",
      "suggestion": "无违规；如需强化人群定位，可把「控糖的姐妹」类人群标签放在此处，远离产品卖点句",
      "reason": "预防性提示，保持人群语境与产品功效隔离"
    }
  ],
  "passed": false,
  "human_review_required": true
}
```

**判定说明**：存在 1 条 critical（FAC-005）与多条 high 违规，evidence_mapping 含多个
blocked，故 `risk_level=critical`、`passed=false`、`human_review_required=true`。整段
脚本主线未依赖医疗表达，按 required_changes 最小修改后可复检；若复检仍有 high 级
违规，退回脚本生成侧重做。

## 示例 2：通过样例（对照）

### 输入脚本（修改后复检版）

```text
标题：打工人的快手早餐，0蔗糖酸奶真的绝了
字幕1：打工人早餐不知道吃啥的姐妹看过来
字幕2：最近挖到轻醒这款0蔗糖希腊酸奶
字幕3：高蛋白的一杯，我吃完到中午都不太想零食
字幕4：配料表很干净，早餐来一杯很清爽
话题标签：#早餐 #快手早餐 #打工人早餐
```

### 输出（摘要）

```json
{
  "risk_level": "none",
  "violations": [],
  "evidence_mapping": [
    {"claim_in_script": "0蔗糖", "matched_product_claim": "0蔗糖",
     "claim_type": "brand_claim", "status": "brand_claim_context",
     "note": "可提及，未升级为无糖、未加数值"},
    {"claim_in_script": "高蛋白", "matched_product_claim": "高蛋白",
     "claim_type": "brand_claim", "status": "brand_claim_context",
     "note": "定性表述，无数值"},
    {"claim_in_script": "我吃完到中午都不太想零食", "matched_product_claim": "饱腹感",
     "claim_type": "subjective_experience", "status": "subjective_only",
     "note": "个人体验语境，符合要求"}
  ],
  "required_changes": [],
  "optional_changes": [
    {"original": "0蔗糖 / 高蛋白（brand_claim）",
     "suggestion": "品牌方提供包装或检测依据后，可将 claim_type 升级为 confirmed",
     "reason": "当前依据待品牌方提供（见 qingxing_brief.json missing_information）"}
  ],
  "passed": true,
  "human_review_required": true
}
```

**判定说明**：无违规（`risk_level=none`）、无 blocked，故 `passed=true`；但存在两条
`brand_claim_context` 映射（依据未到位），按 SKILL.md 第 6 节判定规则，
`human_review_required` 仍为 `true`，须人工确认后方可交付。
