# 输出契约（output-schema）

输出为单个 UTF-8 JSON 对象。字段名、类型、约束如下，校验器
`skills/xhs-script-humanizer/scripts/validate_output.py` 与本文件逐条对应。

## 顶层必填字段

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| original_script | string | 与输入原始脚本逐字一致 |
| humanized_script | string | 非空；自然化后的脚本全文 |
| changes | array<object> | 每处实质改动一条；item 见下 |
| preserved_facts | array<string> | 事实锚点清单（数字/百分比/品牌名/规格/品牌限定词） |
| possible_fact_drift | array<string> | 可为空数组；拿捏不准的改写必须列入 |
| style_match_score | number | 0 ≤ x ≤ 1 |

## item 结构

### changes[]

```json
{ "rule": "R1", "before": "改写前片段", "after": "改写后片段", "reason": "改写理由" }
```

- `rule`（string，必填）：只能取 `references/rules.md` 中的规则编号 `R1` ~ `R8`；
- `before` / `after` / `reason`（string，必填）。

## 全局硬校验（scripts/validate_output.py）

1. 顶层为 JSON 对象，6 个必填字段全部存在，类型如上表。
2. `changes[].rule ∈ {R1..R8}`。
3. `original_script` 中出现的全部数字/百分比 token 与品牌名（`--brand-term` 指定）
   必须出现在 `preserved_facts` 中，且在 `humanized_script` 里逐字保留、未被改变。
4. `possible_fact_drift` 非空时，`style_match_score ≤ 0.9`。
5. `style_match_score ∈ [0, 1]`。
6. 退出码：0 = 通过；1 = 校验失败（schema 错误、事实锚点丢失/被篡改或评分
   一致性问题，错误以 JSON 输出到 stdout）；2 = 用法/文件错误。

## 用法

```bash
python skills/xhs-script-humanizer/scripts/validate_output.py output.json --brand-term 轻醒
```
