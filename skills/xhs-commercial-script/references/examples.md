# 完整示例：轻醒酸奶·早餐场景·voiceover 版

本示例展示一次完整的输入→输出。脚本为**原创文案**，风格借鉴真实证据（`data/processed/stage_3_top3_video_timelines.json` 中欧盈Kelly 153.5s 口播型上班 vlog、小季没烦恼 114s 字幕型植入结构），并在 `style_evidence_map` 中逐条标注。

> 说明：示例中的 `product_evidence` 为演示占位（`source` 以 `_placeholder` 结尾），真实投放前必须替换为品牌方提供的真实依据；`brand_brief.selling_points` 取自真实 Stage 1 产物 `data/processed/qingxing_brief.json`。

## 1. 输入（Generation Input）

```json
{
  "brand_brief": {
    "brand_name": "轻醒",
    "product_name": "0蔗糖高蛋白希腊酸奶",
    "campaign_goal": "自然种草，不要硬广，需要符合原博主创作风格",
    "selling_points": [
      {"claim": "高蛋白", "claim_type": "brand_claim", "forbidden_interpretations": []},
      {"claim": "饱腹感", "claim_type": "subjective_experience", "forbidden_interpretations": ["减重", "抑制食欲"]},
      {"claim": "低负担", "claim_type": "unverified", "forbidden_interpretations": ["不长胖", "零负担", "减肥"]},
      {"claim": "0蔗糖", "claim_type": "brand_claim", "forbidden_interpretations": ["无糖"]}
    ]
  },
  "product_evidence": [
    {
      "evidence_id": "EV-001",
      "claim": "0蔗糖",
      "claim_type": "brand_claim",
      "evidence_text": "产品包装正面标注「0蔗糖」（演示占位，正式使用时须替换为品牌方真实依据）",
      "source": "brand_provided_packaging_placeholder",
      "as_of": "2026-07"
    },
    {
      "evidence_id": "EV-002",
      "claim": "高蛋白",
      "claim_type": "brand_claim",
      "evidence_text": "品牌方营养成分表支持高蛋白宣称（演示占位，脚本中不得标注未经证实的克数）",
      "source": "brand_provided_nutrition_table_placeholder",
      "as_of": "2026-07"
    },
    {
      "evidence_id": "EV-003",
      "claim": "饱腹感",
      "claim_type": "subjective_experience",
      "evidence_text": "主观体验类卖点：允许个人体验语境表达，禁止减重/抑制食欲解读",
      "source": "brief_rules",
      "as_of": "2026-07"
    }
  ],
  "creator_style_profile": {
    "creator_id": "60bb90f00000000001002887",
    "nickname": "欧盈Kelly",
    "primary_format": "voiceover",
    "structure_summary": "时间戳字幕驱动的打工人一日叙事：晨间准备→通勤→早餐→办公",
    "product_integration_pattern": {
      "pattern": "饮品/食品贯穿生活流动线，自然位置前置露出",
      "first_appearance_evidence": "冰美式 18s/153.5s≈11.7% 首现并在 33s 复现；自用香水 14s≈9.1%（data/processed/stage_3_top3_video_timelines.json）"
    },
    "do_not_copy": [
      "'早上坏/都市隶人/呕血'等个人化打工人梗",
      "INTP等人格标签人设",
      "固定结束语句式"
    ],
    "evidence": [
      {
        "note_id": "6989ab01000000001a0360c5",
        "quote": "然后这杯是我昨天冻在冰箱的冰美",
        "what_it_shows": "饮品自然融入出门动线（贯穿式植入）"
      },
      {
        "note_id": "6989ab01000000001a0360c5",
        "quote": "一边看信息 一边吃早餐",
        "what_it_shows": "工位早餐场景的真实感"
      }
    ]
  },
  "target_duration": 60,
  "content_scene": "早餐",
  "format": "voiceover"
}
```

## 2. 生成决策（规则落地）

- **形态**：`voiceover` → 每个分段必须有 `voiceover`（rules §3）。
- **结构**：7 段 60s；hook 0-4s（借鉴 Kelly「口语化问候+标题卡」）。
- **产品首现**：8.0s（13.3%），落在真实证据区间（Kelly 9.1%-11.7%、小季 14.0%）；并在分段 2/4/6 复现，对应 Kelly「饮品贯穿式」动线（rules §5）。
- **卖点取舍**：只写有证据的「0蔗糖（EV-001）」「高蛋白（EV-002）」「饱腹感（EV-003，主观体验语境）」；「低负担」无证据 → 不写入正文，列入未决问题思路（rules §1/§6）。
- **合规**：无减肥/燃脂/降糖/医疗/绝对化表达；「0蔗糖」未写成「无糖」；未标注任何营养数值。

## 3. 输出（Script Output）

```json
{
  "format": "voiceover",
  "title_options": [
    "打工人的30秒早餐碗，起晚了也能吃好",
    "起晚了的早晨，靠这个酸奶碗救场",
    "工作日早餐记录：30秒搞定的酸奶碗"
  ],
  "selected_title": "打工人的30秒早餐碗，起晚了也能吃好",
  "hook": {
    "text": "早上好，欢迎收看打工人的工作日早餐",
    "duration_s": 4.0,
    "design_basis": "借鉴欧盈Kelly「口语化问候+标题卡」开场模式（证据：note 6989ab01000000001a0360c5 hook_analysis），问候语与标题文案均为原创"
  },
  "full_script": [
    {
      "segment_id": 1,
      "start_time": 0.0,
      "end_time": 4.0,
      "voiceover": "早上好，欢迎收看打工人的工作日早餐",
      "on_screen_text": "07:20 工作日早餐",
      "shot_note": "户外自拍仰拍+标题卡",
      "purpose": "hook"
    },
    {
      "segment_id": 2,
      "start_time": 4.0,
      "end_time": 12.0,
      "voiceover": "今天起晚了，早餐得整个快的，拿一杯轻醒希腊酸奶再走",
      "on_screen_text": "07:24 起晚了的早晨",
      "shot_note": "开冰箱拿酸奶特写（8s 产品首次入镜）+换装快切",
      "purpose": "场景铺垫+产品首现"
    },
    {
      "segment_id": 3,
      "start_time": 12.0,
      "end_time": 22.0,
      "voiceover": "酸奶倒进碗里，撒点蓝莓和燕麦，三十秒搞定",
      "on_screen_text": "07:28 30秒早餐碗",
      "shot_note": "俯拍特写+第一人称操作视角",
      "purpose": "制作流"
    },
    {
      "segment_id": 4,
      "start_time": 22.0,
      "end_time": 34.0,
      "voiceover": "选它主要是看中0蔗糖，配料表干净，甜味来自水果本身",
      "on_screen_text": "07:33 配料表我看过",
      "shot_note": "手持酸奶杯身特写转用餐中景",
      "purpose": "卖点段1"
    },
    {
      "segment_id": 5,
      "start_time": 34.0,
      "end_time": 46.0,
      "voiceover": "高蛋白这点对健身的姐妹也友好，我一般到中午都不觉得饿，饱腹感对我来说很真实",
      "on_screen_text": "08:05 地铁上",
      "shot_note": "通勤跟拍+车内自拍",
      "purpose": "卖点段2"
    },
    {
      "segment_id": 6,
      "start_time": 46.0,
      "end_time": 54.0,
      "voiceover": "到工位把最后两口喝完，今天上午的早餐就算交差了",
      "on_screen_text": "08:58 工位收尾",
      "shot_note": "固定机位中景，工位用餐",
      "purpose": "贯穿式收尾"
    },
    {
      "segment_id": 7,
      "start_time": 54.0,
      "end_time": 60.0,
      "voiceover": "明天见，记得好好吃早餐",
      "on_screen_text": "工作日早餐 明天见",
      "shot_note": "窗外空镜+结尾字幕卡",
      "purpose": "ending"
    }
  ],
  "product_first_appearance": {
    "time_s": 8.0,
    "segment_id": 2,
    "rationale": "取 8s（13.3%），落在真实证据的前置露出区间：欧盈Kelly 冰美式 18s/153.5s≈11.7%、小季没烦恼商单 16s/114s≈14.0%；且产品在分段 2/4/6 复现，对应 Kelly「饮品贯穿式」动线"
  },
  "integration_sentence": "选它主要是看中0蔗糖，配料表干净，甜味来自水果本身",
  "CTA": "早餐不知道吃啥的姐妹，可以先试试这个搭配",
  "estimated_duration": 60.0,
  "claim_evidence_map": [
    {
      "script_sentence": "选它主要是看中0蔗糖，配料表干净，甜味来自水果本身",
      "claim": "0蔗糖",
      "evidence_ids": ["EV-001"]
    },
    {
      "script_sentence": "高蛋白这点对健身的姐妹也友好，我一般到中午都不觉得饿，饱腹感对我来说很真实",
      "claim": "高蛋白",
      "evidence_ids": ["EV-002"]
    },
    {
      "script_sentence": "高蛋白这点对健身的姐妹也友好，我一般到中午都不觉得饿，饱腹感对我来说很真实",
      "claim": "饱腹感",
      "evidence_ids": ["EV-003"]
    }
  ],
  "style_evidence_map": [
    {
      "script_element": "hook",
      "borrowed_pattern": "口语化问候+大字标题卡的打工人共鸣开场",
      "source": {
        "creator": "欧盈Kelly",
        "note_id": "6989ab01000000001a0360c5",
        "evidence": "hook_analysis：口语化问候制造打工人共鸣，标题卡建立都市通勤语境"
      },
      "adaptation": "问候语与标题文案全部原创，仅沿用「问候+时间戳标题卡」结构"
    },
    {
      "script_element": "分段 2/4/6 产品动线",
      "borrowed_pattern": "饮品贯穿的生活流动线",
      "source": {
        "creator": "欧盈Kelly",
        "note_id": "6989ab01000000001a0360c5",
        "evidence": "style_summary.food_insertion_points：冰美式贯穿（18s/33s 两杯），均为生活流自然位置"
      },
      "adaptation": "改为酸奶在「拿取-食用-工位收尾」三节点出现"
    },
    {
      "script_element": "全片字幕",
      "borrowed_pattern": "时间戳字幕结构",
      "source": {
        "creator": "欧盈Kelly",
        "note_id": "6989ab01000000001a0360c5",
        "evidence": "style_summary.reusable_high_level：时间戳字幕结构"
      },
      "adaptation": "按 60s 短时长重排时间戳，字幕文案原创"
    },
    {
      "script_element": "分段 4-5 卖点表达",
      "borrowed_pattern": "需求场景→产品解法的植入结构",
      "source": {
        "creator": "小季没烦恼",
        "note_id": "6a58b7ea000000001101a7bb",
        "evidence": "style_summary.commercial_pattern：主商单用「需求场景→产品解法」结构，自然度高"
      },
      "adaptation": "需求=「起晚了没时间吃早餐」，解法=「30秒酸奶碗」，句式原创"
    }
  ],
  "unresolved_questions": [
    "购买渠道与价格待品牌方确认，CTA 暂不引导具体链接",
    "产品包装图未提供，分段 4 杯身特写画面需拍摄前确认"
  ]
}
```

## 4. 校验

```bash
python skills/xhs-commercial-script/scripts/validate_output.py output.json \
    --input input.json --timelines data/processed/stage_3_top3_video_timelines.json
```

预期 6 项全部 PASS（schema_valid / internal_consistency / format_requirements / claim_evidence_coverage / duration_deviation / verbatim_copy_check）。本示例与 `evals/evals.json` 中 `eval-001-voiceover-breakfast` 一致，已由 `tests/test_skill_xhs_commercial_script.py` 自动回归。
