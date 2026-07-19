# 完整示例：早餐场景脚本 → 9 镜分镜

本示例演示一次完整的分镜生成：输入为 21.0s 字幕沉浸式早餐脚本（一只牛风格），输出 9 镜分镜，镜头平均 2.33s，落在真实证据区间内（欧盈Kelly 2.4s / 小季没烦恼 2.5s / 一只牛 2.0s，见 `data/processed/stage_3_top3_video_timelines.json`）。该分镜即 `evals.json` 的 `eval_001`，可通过 `validate_output.py` 全部校验。

## 1. 输入

```json
{
  "full_script": {
    "script_id": "script-breakfast-001",
    "title": "独居早餐｜酸奶碗与冰美式",
    "format": "subtitle_immersive",
    "total_duration_s": 21.0,
    "product_first_appearance_s": 6.4,
    "beats": [
      {"beat_id": "b1", "start_time": 0.0, "end_time": 2.0, "purpose": "hook", "scene": "餐桌", "action": "端起成品早餐展示", "spoken_line": null, "on_screen_text": null},
      {"beat_id": "b2", "start_time": 2.0, "end_time": 6.4, "purpose": "process", "scene": "厨房台面", "action": "备料、烤吐司、煎蛋", "spoken_line": null, "on_screen_text": "蓝莓最后放，颜色更好看"},
      {"beat_id": "b3", "start_time": 6.4, "end_time": 13.0, "purpose": "product", "scene": "餐桌", "action": "取酸奶、开盖、组装酸奶碗", "spoken_line": null, "on_screen_text": "0蔗糖，奶香很浓"},
      {"beat_id": "b4", "start_time": 13.0, "end_time": 18.2, "purpose": "lifestyle", "scene": "餐桌", "action": "倒冰美式、用餐", "spoken_line": null, "on_screen_text": "这个天气还是要冰美式"},
      {"beat_id": "b5", "start_time": 18.2, "end_time": 21.0, "purpose": "ending", "scene": "餐桌", "action": "收尾展示", "spoken_line": null, "on_screen_text": "好好吃早饭~"}
    ]
  },
  "target_duration": 21.0,
  "style_profile": {
    "creator_id": "5ad034864eacab543fa98374",
    "primary_format": "subtitle_immersive",
    "avg_shot_s": 2.0,
    "narration_relation": "无口播；字幕极少且只做制作说明与口感点评（每段<=15字），环境音为主",
    "reusable_high_level": ["成品先行开场", "线性制作流程", "少字幕+环境音的沉浸感", "饮品与主餐的固定搭配位"]
  },
  "scene_constraints": {
    "scene": "早餐",
    "location_options": ["家中厨房台面", "灶台", "餐桌"],
    "max_props": 8,
    "crew": 1,
    "equipment": ["手机", "手机三脚架"]
  }
}
```

## 2. 拆镜思路

1. 镜头数 ≈ 21.0 / 2.0 ≈ 10，按 beat 边界合并为 9 镜，平均 2.33s。
2. hook（s01）用「成品先行」：0s 直接给成品特写，**不露出产品包装**，因此不构成产品露出，产品首露仍按脚本放在 6.4s（s04）。
3. 产品段（s04–s06）采用「需求场景 → 产品解法」：先取酸奶入镜，再开盖特写给卖点字幕「0蔗糖，奶香很浓」，最后组装时给个人体验语境的「我觉得挺顶饱的」。
4. 饮品位（s07）放在主餐之后，对应「饮品与主餐的固定搭配位」。
5. 运镜全部来自白名单：固定 / 手持微晃 / 俯拍下移 / 缓慢推进；转场以硬切、跳切为主。

## 3. 输出分镜（完整 JSON）

```json
{
  "schema_version": "1.0",
  "storyboard_id": "sb-breakfast-001",
  "scene": "早餐",
  "aspect_ratio": "9:16",
  "target_duration_s": 21.0,
  "actual_total_duration_s": 21.0,
  "product_first_appearance_s": 6.4,
  "shots": [
    {
      "shot_id": "s01",
      "start_time": 0.0,
      "end_time": 2.0,
      "duration": 2.0,
      "visual": "俯拍特写：双手把成品酸奶碗与吐司餐盘放到餐桌中央，画面只呈现成品，产品包装不入镜",
      "shot_size": "特写",
      "camera_position": "俯拍",
      "camera_motion": "固定",
      "person_action": "双手端起成品早餐放下展示",
      "spoken_line": null,
      "on_screen_text": null,
      "product_state": "未出现",
      "product_exposure": false,
      "props": ["酸奶碗（成品，无包装露出）", "吐司餐盘"],
      "location": "餐桌",
      "bgm_or_sound": "环境音：餐具轻响",
      "transition": "硬切",
      "shooting_difficulty": "easy",
      "compliance_note": "成品入镜但包装未露出，不构成产品露出；无卖点表述，无合规风险",
      "script_source": "b1",
      "style_evidence": "成品先行开场：一只牛 0s 成品三明治特写直接开场（data/processed/stage_3_top3_video_timelines.json）"
    },
    {
      "shot_id": "s02",
      "start_time": 2.0,
      "end_time": 4.2,
      "duration": 2.2,
      "visual": "第一人称手持俯拍：流水下冲洗蓝莓，随后在砧板上切香蕉片",
      "shot_size": "特写",
      "camera_position": "第一人称",
      "camera_motion": "手持微晃",
      "person_action": "洗蓝莓、切香蕉片",
      "spoken_line": null,
      "on_screen_text": "蓝莓最后放，颜色更好看",
      "product_state": "未出现",
      "product_exposure": false,
      "props": ["蓝莓", "香蕉", "砧板", "水果刀"],
      "location": "家中厨房台面",
      "bgm_or_sound": "环境音：水流声",
      "transition": "跳切",
      "shooting_difficulty": "easy",
      "compliance_note": "无卖点表述，无合规风险",
      "script_source": "b2",
      "style_evidence": "第一人称操作视角做食品（小季没烦恼 28-46s 钵钵鸡制作段，data/processed/stage_3_top3_video_timelines.json）"
    },
    {
      "shot_id": "s03",
      "start_time": 4.2,
      "end_time": 6.4,
      "duration": 2.2,
      "visual": "俯拍特写：吐司弹入烤面包机，旁边平底锅小火煎蛋",
      "shot_size": "特写",
      "camera_position": "俯拍",
      "camera_motion": "固定",
      "person_action": "烤吐司、煎溏心蛋",
      "spoken_line": null,
      "on_screen_text": "溏心蛋小火慢煎",
      "product_state": "未出现",
      "product_exposure": false,
      "props": ["吐司", "鸡蛋", "烤面包机", "平底锅"],
      "location": "灶台",
      "bgm_or_sound": "环境音：煎蛋滋滋声",
      "transition": "跳切",
      "shooting_difficulty": "easy",
      "compliance_note": "无卖点表述，无合规风险",
      "script_source": "b2",
      "style_evidence": "线性制作流程（一只牛 style_summary.reusable_high_level，data/processed/stage_3_top3_video_timelines.json）"
    },
    {
      "shot_id": "s04",
      "start_time": 6.4,
      "end_time": 8.6,
      "duration": 2.2,
      "visual": "手持中景：打开冰箱取出轻醒酸奶，走到餐桌前放下",
      "shot_size": "中景",
      "camera_position": "平视",
      "camera_motion": "手持微晃",
      "person_action": "开冰箱取出酸奶放到桌上",
      "spoken_line": null,
      "on_screen_text": "打开冰箱就是它",
      "product_state": "入镜静置",
      "product_exposure": true,
      "props": ["轻醒酸奶（原味）"],
      "location": "家中厨房（冰箱前）",
      "bgm_or_sound": "环境音：冰箱门开关声",
      "transition": "硬切",
      "shooting_difficulty": "easy",
      "compliance_note": "产品首次入镜，与脚本 product_first_appearance_s=6.4 对齐；无卖点表述",
      "script_source": "b3",
      "style_evidence": "需求场景→产品解法的植入结构（小季没烦恼 16s 饮品植入段，data/processed/stage_3_top3_video_timelines.json）"
    },
    {
      "shot_id": "s05",
      "start_time": 8.6,
      "end_time": 10.8,
      "duration": 2.2,
      "visual": "俯拍特写：撕开酸奶盖，勺子舀起展示浓稠质地",
      "shot_size": "特写",
      "camera_position": "俯拍",
      "camera_motion": "俯拍下移",
      "person_action": "撕盖、舀起一勺酸奶展示质地",
      "spoken_line": null,
      "on_screen_text": "0蔗糖，奶香很浓",
      "product_state": "特写展示",
      "product_exposure": true,
      "props": ["轻醒酸奶（原味）", "勺子"],
      "location": "餐桌",
      "bgm_or_sound": "环境音：撕盖声",
      "transition": "跳切",
      "shooting_difficulty": "easy",
      "compliance_note": "「0蔗糖」为品牌宣称，依据品牌方资料；未表述为「无糖」，未标注任何营养数值",
      "script_source": "b3",
      "style_evidence": "字幕承担卖点（小季没烦恼 narration_relation：字幕承担叙事+情绪+卖点，data/processed/stage_3_top3_video_timelines.json）"
    },
    {
      "shot_id": "s06",
      "start_time": 10.8,
      "end_time": 13.0,
      "duration": 2.2,
      "visual": "第一人称俯拍：酸奶倒入玻璃碗，依次铺香蕉片、蓝莓，撒燕麦",
      "shot_size": "特写",
      "camera_position": "第一人称",
      "camera_motion": "固定",
      "person_action": "倒酸奶、铺水果、撒燕麦组装酸奶碗",
      "spoken_line": null,
      "on_screen_text": "我觉得挺顶饱的",
      "product_state": "开封/使用中",
      "product_exposure": true,
      "props": ["轻醒酸奶（原味）", "蓝莓", "香蕉", "燕麦", "玻璃碗", "勺子"],
      "location": "餐桌",
      "bgm_or_sound": "环境音：燕麦洒落声",
      "transition": "跳切",
      "shooting_difficulty": "medium",
      "compliance_note": "饱腹感表述采用个人体验语境（「我觉得」），未延伸至减重/抑制食欲",
      "script_source": "b3",
      "style_evidence": "组装段第一人称操作视角（一只牛 26-34s 组装三明治段，data/processed/stage_3_top3_video_timelines.json）"
    },
    {
      "shot_id": "s07",
      "start_time": 13.0,
      "end_time": 15.4,
      "duration": 2.4,
      "visual": "俯拍特写：冰块入杯，倒入咖啡液，画面只拍咖啡",
      "shot_size": "特写",
      "camera_position": "俯拍",
      "camera_motion": "固定",
      "person_action": "倒冰块、倒咖啡",
      "spoken_line": null,
      "on_screen_text": "这个天气还是要冰美式",
      "product_state": "未出现",
      "product_exposure": false,
      "props": ["玻璃杯", "冰块", "咖啡液"],
      "location": "餐桌",
      "bgm_or_sound": "环境音：冰块碰撞声",
      "transition": "跳切",
      "shooting_difficulty": "easy",
      "compliance_note": "无卖点表述，无合规风险",
      "script_source": "b4",
      "style_evidence": "饮品与主餐的固定搭配位（一只牛 36s 冰美式位，data/processed/stage_3_top3_video_timelines.json）"
    },
    {
      "shot_id": "s08",
      "start_time": 15.4,
      "end_time": 18.2,
      "duration": 2.8,
      "visual": "三脚架中景：坐在餐桌前舀食酸奶碗，手边放冰美式，余光扫平板",
      "shot_size": "中景",
      "camera_position": "平视",
      "camera_motion": "固定",
      "person_action": "舀食酸奶碗、翻平板",
      "spoken_line": null,
      "on_screen_text": "酸奶加咖啡，早餐齐了",
      "product_state": "食用/饮用中",
      "product_exposure": true,
      "props": ["酸奶碗", "勺子", "冰美式", "平板"],
      "location": "餐桌",
      "bgm_or_sound": "轻BGM渐入",
      "transition": "硬切",
      "shooting_difficulty": "easy",
      "compliance_note": "无卖点表述，无合规风险",
      "script_source": "b4",
      "style_evidence": "边吃边看iPad的用餐中景（一只牛 40-48s 用餐段，data/processed/stage_3_top3_video_timelines.json）"
    },
    {
      "shot_id": "s09",
      "start_time": 18.2,
      "end_time": 21.0,
      "duration": 2.8,
      "visual": "俯拍中景：吃完的餐盘与酸奶杯摆齐收尾，结束字幕浮现",
      "shot_size": "中景",
      "camera_position": "俯拍",
      "camera_motion": "缓慢推进",
      "person_action": "把空碗与咖啡杯摆齐",
      "spoken_line": null,
      "on_screen_text": "好好吃早饭~",
      "product_state": "入镜静置",
      "product_exposure": true,
      "props": ["餐盘", "酸奶杯", "咖啡杯"],
      "location": "餐桌",
      "bgm_or_sound": "轻BGM收尾",
      "transition": "淡入淡出",
      "shooting_difficulty": "easy",
      "compliance_note": "结束语为原创，未抄袭达人固定句式；无卖点表述",
      "script_source": "b5",
      "style_evidence": "收尾展示+固定结束语结构（一只牛 48-54.7s 收尾段，data/processed/stage_3_top3_video_timelines.json）"
    }
  ]
}
```

## 4. 校验

```bash
python skills/xhs-storyboard-generator/scripts/validate_output.py storyboard.json --script script.json
```

预期输出 `ok: true`。逐条对照：时间轴 0.0→21.0 连续无重叠；`actual_total_duration_s` 与目标偏差 0s；运镜全白名单；产品露出首镜 s04 `start_time=6.4`，不早于脚本 `product_first_appearance_s=6.4`；单镜道具最多 6 件（s06）；镜头平均 2.33s 处于 1.0–4.0s 证据区间。
