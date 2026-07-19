# 审核报告输出 Schema（xhs-food-ad-compliance）

> 本文件是 SKILL.md 第 4 节输出契约的机器可校验表达（JSON Schema，Draft 2020-12 风格）。
> 审核 Agent 产出报告后，可用任意 JSON Schema 校验器对照本 Schema 自检；
> 七个顶层强制字段缺一不可。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "XhsFoodAdComplianceReport",
  "type": "object",
  "required": [
    "risk_level",
    "violations",
    "evidence_mapping",
    "required_changes",
    "optional_changes",
    "passed",
    "human_review_required"
  ],
  "additionalProperties": true,
  "properties": {
    "risk_level": {
      "type": "string",
      "enum": ["none", "low", "medium", "high", "critical"],
      "description": "取 violations 中最高严重级；无违规为 none"
    },
    "violations": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "rule_id",
          "rule_name",
          "severity",
          "matched_text",
          "location",
          "issue",
          "suggestion"
        ],
        "properties": {
          "rule_id": {
            "type": "string",
            "pattern": "^(FAC-0(0[1-9]|10)|BRAND-CUSTOM)$",
            "description": "必须来自 references/rules.md；未覆盖问题不得发明 ID"
          },
          "rule_name": { "type": "string" },
          "severity": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"]
          },
          "matched_text": { "type": "string", "minLength": 1 },
          "location": {
            "type": "string",
            "description": "口播第N句 / 字幕第N条 / 标题 / 话题标签 / 分镜第N镜"
          },
          "issue": { "type": "string" },
          "suggestion": { "type": "string" }
        }
      }
    },
    "evidence_mapping": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "claim_in_script",
          "matched_product_claim",
          "claim_type",
          "status",
          "note"
        ],
        "properties": {
          "claim_in_script": { "type": "string", "minLength": 1 },
          "matched_product_claim": {
            "type": ["string", "null"],
            "description": "映射到的 ProductEvidence.claim；无映射为 null"
          },
          "claim_type": {
            "type": ["string", "null"],
            "enum": ["confirmed", "brand_claim", "subjective_experience", "unverified", null]
          },
          "status": {
            "type": "string",
            "enum": ["supported", "brand_claim_context", "subjective_only", "blocked"]
          },
          "note": { "type": "string" }
        }
      }
    },
    "required_changes": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["violation_rule_id", "original", "replacement", "reason"],
        "properties": {
          "violation_rule_id": { "type": "string" },
          "original": { "type": "string", "minLength": 1 },
          "replacement": {
            "type": "string",
            "description": "修改后文本，或「删除」；只允许最小修改，不允许整段重写"
          },
          "reason": { "type": "string" }
        }
      }
    },
    "optional_changes": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["original", "suggestion", "reason"],
        "properties": {
          "original": { "type": "string" },
          "suggestion": { "type": "string" },
          "reason": { "type": "string" }
        }
      }
    },
    "passed": {
      "type": "boolean",
      "description": "无 critical/high 违规且无 blocked 卖点方为 true"
    },
    "human_review_required": {
      "type": "boolean",
      "description": "判定条件见 SKILL.md 第 6 节"
    }
  }
}
```

## 一致性约束（Schema 无法表达、需人工或流程校验）

1. `violations` 非空时，`risk_level` 不得为 `none`；存在 `severity=critical` 的违规时，
   `risk_level` 必须为 `critical`。
2. `evidence_mapping` 中存在 `status=blocked` 时，`passed` 必须为 `false` 且
   `human_review_required` 必须为 `true`。
3. `passed=true` 时，`violations` 中不得存在 `severity` 为 `critical` 或 `high` 的条目。
4. 每条 `required_changes.violation_rule_id` 必须能在 `violations.rule_id` 中找到对应项。
5. `evidence_mapping` 中存在 `brand_claim_context` 时，`human_review_required` 必须为
   `true`。
