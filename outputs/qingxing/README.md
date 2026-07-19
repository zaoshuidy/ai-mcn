# 轻醒商单脚本全链路交付（P0）

品牌：轻醒 0蔗糖高蛋白希腊酸奶 ｜ 平台：小红书短视频 ｜ 场景：上班族早餐/通勤
风格对象：欧盈Kelly（v2 评分 93，research_style_reference，仅用于风格研究）
生成日期：2026-07-19 ｜ 目标时长：45s ｜ 形态：voiceover（口播型）

## 一、链路总览

```
真实风格证据（data/processed/stage_3_top3_video_timelines.json，note 6989ab01000000001a0360c5，153.5s 口播型上班 vlog）
  → ① 风格蒸馏 style_profile_kelly.json（creator-style-distiller）
  → ② 脚本生成 script_v1.json（xhs-commercial-script，输入 inputs/script_generation_input.json）
  → ③ 自然化 script_v2_humanized.json（xhs-script-humanizer，R1-R8）
  → ④ 合规审核 compliance_report.json（xhs-food-ad-compliance，FAC-001~010）
  → 最终脚本 script_final.json（自然化稿 0 整改放行，回归 xhs-commercial-script 契约复核）
  → ⑤ 分镜 storyboard_final.json（xhs-storyboard-generator，输入 inputs/storyboard_input.json）
```

## 二、交付文件

| 文件 | 说明 | 校验器 | 退出码 |
| --- | --- | --- | --- |
| `outputs/qingxing/style_profile_kelly.json` | CreatorStyleProfile（风格蒸馏） | `python skills/creator-style-distiller/scripts/validate_output.py outputs/qingxing/style_profile_kelly.json --input data/processed/stage_3_top3_video_timelines.json` | 0 |
| `outputs/qingxing/script_v1.json` | 商单脚本 v1（7 段，45s） | `python skills/xhs-commercial-script/scripts/validate_output.py outputs/qingxing/script_v1.json --input outputs/qingxing/inputs/script_generation_input.json --timelines data/processed/stage_3_top3_video_timelines.json` | 0（6/6 项 PASS） |
| `outputs/qingxing/script_v2_humanized.json` | 自然化稿（R4/R5/R6 改写 + R7/R8 红线自查） | `python skills/xhs-script-humanizer/scripts/validate_output.py outputs/qingxing/script_v2_humanized.json --brand-term 轻醒` | 0 |
| `outputs/qingxing/compliance_report.json` | 合规审核报告（审核对象=自然化稿+标题+字幕+CTA） | `python skills/xhs-food-ad-compliance/scripts/validate_output.py outputs/qingxing/compliance_report.json` | 0 |
| `outputs/qingxing/script_final.json` | 最终脚本（=自然化稿结构化，合规 0 整改） | 同 script_v1 校验命令（替换文件路径） | 0（6/6 项 PASS） |
| `outputs/qingxing/storyboard_final.json` | 分镜表（19 镜，45.0s，9:16） | `python skills/xhs-storyboard-generator/scripts/validate_output.py outputs/qingxing/storyboard_final.json --script outputs/qingxing/inputs/storyboard_input.json` | 0（0 error / 0 warning） |

辅助文件（证据用，非独立交付物）：`inputs/script_generation_input.json`（生成输入：品牌 Brief 卖点 + 证据 ID 映射 + 风格画像摘要）、`inputs/storyboard_input.json`（分镜输入）。

回归证据：`python -m pytest tests/ -q` → **651 passed**（未改动 tests/、src/、skills/ 等任何范围外文件；本次未新增 Python 代码，ruff 不适用）。

## 三、各步要点与证据

### ① 风格蒸馏（style_profile_kelly.json）
- 证据全部取自真实时间线：hook_analysis、style_summary、10 个 segments（时间戳可回溯，evidence_timestamps 含 [0,4]/[4,18]/14.0/18.0/33.2/38.0/[48,64]/[148,153.5]）。
- 蒸馏结论：口播型打工人一日线性叙事；时间戳字幕为骨架；饮品/三餐贯穿生活流（18s/33.2s 冰美式两杯、38s 早餐）；avg_shot_s=2.4；自拍+固定机位混合；夜景空镜收尾。
- 禁复制清单（creator_specific_elements_not_to_copy）：早上坏/都市隶人/呕血个人梗、INTP 人设、具体香水描述、固定结束语句式。
- 校验器含禁复制检查（与输入 transcript 不得有 >15 字连续相同子串）：PASS。

### ② 脚本生成（script_v1.json）
- 3 个标题候选，选定「踩点出门的早晨，我的工位早餐搭子」；hook 0-4s（原创问候+标题卡，借鉴 Kelly hook 模式）。
- **产品首现 10.0s（分段 2）**：落在任务给定的 8-15s 证据区间；rationale 引用真实证据（Kelly 香水 14.0s≈9.1%、冰美式 18s≈11.7% 首现并复现），并说明略超 45s 前 15%（6.75s）的理由（先建立晨间日常再露出，避免开场硬广）。
- 卖点取舍：只写「0蔗糖（EV-QX-001）」「高蛋白（EV-QX-002，无具体克数）」「饱腹感（EV-QX-003，对我来说语境）」；「低负担」unverified 无证据 → 未写入正文，列入 unresolved_questions。
- claim_evidence_map 3 条全覆盖；style_evidence_map 5 条（Kelly×4 + 小季×1，均含 note_id 与证据位置）；verbatim_copy_check 语料 70 条未发现复制。

### ③ 自然化（script_v2_humanized.json）
- 5 处表达层改写（R4 停顿×3、R5 拆长句、R6 节奏打散）+ R7/R8 红线自查。
- 事实锚点：0蔗糖、轻醒、高蛋白、饱腹感、希腊酸奶、蓝莓全部逐字保留（校验器实测 token：0蔗糖、品牌词轻醒，均 PASS）。
- possible_fact_drift=[]，style_match_score=0.88。

### ④ 合规审核（compliance_report.json）
- 审核对象：自然化稿全文 + 标题候选 + 字幕 + CTA（source_text 已附）。
- FAC-001~010 扫描：**0 violations，risk_level=none，passed=true**。
- evidence_mapping：0蔗糖→brand_claim_context、高蛋白→brand_claim_context、饱腹感→subjective_only；无 blocked。
- **human_review_required=true**，原因仅为 2 条 brand_claim_context（品牌主张依据待品牌方提供），无其他违规。
- 结论：自然化稿 0 required_changes 放行 → script_final.json 与自然化稿逐字一致，并经 xhs-commercial-script 校验器 6/6 复核通过。

### ⑤ 分镜（storyboard_final.json）
- 19 镜，总时长 45.0s（=target，偏差 0），平均镜头 45.0/19≈2.37s（任务要求 2.0-2.5s，校验器提示区间 1.0-4.0s）。
- 竖屏 9:16；全部运镜取自白名单（固定/手持微晃/缓慢推进/跟随平移/俯拍下移/抬起转向）；1 人+手机可执行；单镜道具 ≤8；难度 easy×18 / medium×1。
- 产品露出时点：首露镜 s05 start=10.0s，不早于脚本 product_first_appearance_s=10.0s（s01-s04 均标记未出现/非露出）；后续露出镜 s06/s07/s09/s10/s12-s17/s19 均 ≥10.0s。
- 每镜 compliance_note 写明卖点依据（EV-QX-001/002/003）或「无卖点表述」；style_evidence 逐镜可溯源至真实时间线文件。

## 四、脚本核心信息

- 标题：踩点出门的早晨，我的工位早餐搭子（备选：起晚了也别空着肚子上班，一杯带走 / 工作日早餐记录：从冰箱到工位）
- 产品首现：10.0s（分段 2，手持酸奶杯特写）
- 植入句：当初选它就是看中0蔗糖，喝起来是酸奶本身的酸甜
- CTA：早餐不知道吃什么的姐妹，评论区聊聊你们的快手早餐搭配
- 时长：estimated_duration=45.0s（target 45s，偏差 0%）

## 五、人工待确认项

1. **0蔗糖/高蛋白依据（阻塞对外发布）**：两者为 brand_claim，包装标识/营养成分表/检测报告待品牌方提供；compliance_report 已置 human_review_required=true。
2. **可选措辞**：「到工位先喝两口压压惊」口语偏重，品牌方可改为「先喝两口缓一缓」（optional_changes，非违规）。
3. **购买渠道与价格**：未提供，CTA 未引导链接；如需转化引导请品牌方补充。
4. **产品包装图与规格**：未提供，s05/s13 杯身特写拍摄前需确认实物与标签可读性。
5. **视频时长要求**：Brief 未明确，本链按任务指定的 45s 设计；若品牌方要求 30/60s 需重排分段与分镜。
6. **「低负担」卖点**：unverified，已按规则排除出正文；如品牌方提供书面依据可评估加回。

## 六、异常与说明

- 无校验失败项；5 个交付文件均一次通过各自校验器（退出码 0）。
- 本次任务未修改 skills/、data/、tests/、config/、README.md、agent/ 等范围外文件；未写入任何 Cookie/Token；未虚构数据（风格证据引用均可回溯至 data/processed/stage_3_top3_video_timelines.json，卖点证据 ID 映射至 data/processed/qingxing_brief.json 与 agent/policies/qingxing_claims.yaml 的真实状态）。
- 证据 ID 说明：qingxing_brief.json 中 selling_points[].evidence 均为 null（依据待品牌方提供），EV-QX-001/002/003 是对该真实状态的登记映射，非品牌方已出具的检测依据；对外发布前须以品牌方真实依据替换。
