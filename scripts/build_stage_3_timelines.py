"""Stage 3 Top3 视频时间线构建：合并音频转写与关键帧视觉分析。

时间线内容来源：
- 关键帧多模态逐帧读取（tmp/stage_3_top3_video/<cid>/contact_sheet_*.jpg）；
- faster-whisper small 转写（仅欧盈Kelly为有效口播；两位字幕型达人ASR结果为
  BGM幻觉，标记 asr_reliability=unreliable，不作为口播证据）；
- 页面证据（stage_3_top3_video_manifest.json）。

规则：不确定视觉字段写 null；不根据音频编造画面；不根据画面编造口播；
完整逐字稿不进 Git，只保留短证据片段（<=30字/段）。

输出：data/processed/stage_3_top3_video_timelines.json
用法：python scripts/build_stage_3_timelines.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/processed/stage_3_top3_video_timelines.json"
MANIFEST = ROOT / "data/processed/stage_3_top3_video_manifest.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


TIMELINES = {
    "60bb90f00000000001002887": {  # 欧盈Kelly
        "note_id": "6989ab01000000001a0360c5",
        "title": "深圳INTP独立女上班vlog：又活了一天",
        "duration_s": 153.5,
        "primary_format": "voiceover",
        "asr_reliability": "reliable_with_noise",
        "asr_note": "faster-whisper small 转写为繁体且有个别同音错字，语义可读；"
                    "末尾约148s后重复句为ASR幻觉，已剔除",
        "hook_analysis": "0-4s 户外仰拍自拍视角+大字标题卡（WORKDAY VLOG/早九晚五版），"
                         "口语化问候'早上坏'制造打工人共鸣，城市街景建立都市通勤语境",
        "segments": [
            {"start_time": 0.0, "end_time": 4.0,
             "transcript_summary": "开场问候，欢迎收看日常",
             "on_screen_text": "WORKDAY VLOG 深圳intp独立女上班的一天(早九晚五版)；早上坏 大家",
             "scene": "户外城市街道", "person_action": "边走边举相机自拍",
             "shot_type": "自拍仰拍+标题卡", "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [0.0, 2.0],
             "audio_evidence_timestamps": [[0.0, 3.6]], "confidence": 0.9},
            {"start_time": 4.0, "end_time": 18.0,
             "transcript_summary": "挑选出门穿搭；展示自用香水（橘彩星光）",
             "on_screen_text": ("07:30/07:43/08:02 时间戳；"
                 "出门必带戒指 一定程度上能缓解我的焦虑；就是这一支橘彩星光"),
             "scene": "卧室/衣帽间", "person_action": "换装、佩戴饰品、手持香水展示",
             "shot_type": "固定机位全身+手持特写",
             "food_or_product": "香水（橘彩星光）",
             "product_first_appearance": 14.0,
             "commercial_expression": "自用展示型口播，无卖点话术；是否软广无法确认",
             "compliance_risks": [],
             "evidence_frame_timestamps": [4.0, 8.0, 12.0, 16.0],
             "audio_evidence_timestamps": [[7.2, 12.2], [15.4, 18.8]],
             "confidence": 0.6},
            {"start_time": 18.0, "end_time": 22.0,
             "transcript_summary": "拿起昨晚冻在冰箱的冰美式准备出门",
             "on_screen_text": "08:13；然后这杯是我昨天冻在冰箱的冰美",
             "scene": "家中玄关", "person_action": "手持冰美式出门",
             "shot_type": "手持特写", "food_or_product": "冰美式（咖啡）",
             "product_first_appearance": 18.0, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [18.0, 20.0],
             "audio_evidence_timestamps": [[18.8, 22.6]], "confidence": 0.9},
            {"start_time": 22.0, "end_time": 38.0,
             "transcript_summary": "打车通勤，路上听播客提神；到咖啡店取第二杯冰美式",
             "on_screen_text": ("08:15/08:25/08:32；听点什么让我的大脑清醒一点呢；"
                 "都市隶人也要整点精神早餐"),
             "scene": "车内/咖啡店", "person_action": "乘车听播客、取咖啡",
             "shot_type": "车内自拍+手机屏幕特写+取餐跟拍",
             "food_or_product": "冰美式（第二杯）",
             "product_first_appearance": 33.2, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [22.0, 26.0, 28.0, 30.0, 34.0, 36.0],
             "audio_evidence_timestamps": [[26.0, 29.8], [33.2, 35.4]],
             "confidence": 0.9},
            {"start_time": 38.0, "end_time": 48.0,
             "transcript_summary": "固定早餐炒蛋配冰美式；想念广州点心",
             "on_screen_text": ("08:45；每天早餐都是固定的炒蛋+冰美；"
                 "作为广州人我真的好想念广州的点心"),
             "scene": "咖啡店/早餐区", "person_action": "吃早餐",
             "shot_type": "低角度自拍+餐食特写", "food_or_product": "炒蛋+冰美式",
             "product_first_appearance": 38.0, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [38.0, 42.0, 44.0, 46.0],
             "audio_evidence_timestamps": [[38.6, 40.6]], "confidence": 0.9},
            {"start_time": 48.0, "end_time": 64.0,
             "transcript_summary": "踩点到公司；工位一边看信息一边吃早餐；开始回复工作",
             "on_screen_text": ("08:58/09:02/09:15/09:35；差一分钟就要迟到 好在走快两步；"
                 "一边看信息 一边吃早餐"),
             "scene": "写字楼大堂/办公室工位", "person_action": "进电梯、工位用餐、开电脑",
             "shot_type": "跟拍+固定机位中景", "food_or_product": "工位早餐",
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [48.0, 52.0, 54.0, 58.0, 62.0],
             "audio_evidence_timestamps": None, "confidence": 0.85},
            {"start_time": 66.0, "end_time": 90.0,
             "transcript_summary": "开会对方案到中午；提前点好的午餐是简单意粉",
             "on_screen_text": ("11:05/12:15/12:50；每次对工作都会对着呕血(梗)；"
                 "幸好提前点了午餐；午餐就是吃个简单的意粉"),
             "scene": "会议室/茶水间", "person_action": "开会、取外卖、吃午餐",
             "shot_type": "固定机位中景+外卖特写", "food_or_product": "意粉（午餐）",
             "product_first_appearance": 78.0, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [66.0, 72.0, 78.0, 82.0, 90.0],
             "audio_evidence_timestamps": None, "confidence": 0.85},
            {"start_time": 92.0, "end_time": 106.0,
             "transcript_summary": "午休后继续开会；年中KPI压力；线上会议改期",
             "on_screen_text": ("13:30/14:15/15:00-16:35；午休时间结束就继续开会了；"
                 "听年中kpi 感觉压力山大"),
             "scene": "办公室/会议室", "person_action": "开会、独自办公",
             "shot_type": "固定机位中景+过肩拍", "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [92.0, 96.0, 100.0, 106.0],
             "audio_evidence_timestamps": None, "confidence": 0.85},
            {"start_time": 108.0, "end_time": 146.0,
             "transcript_summary": "准点下班和朋友约饭；吃漂亮饭；把不吃的紫苏鸡腿给朋友",
             "on_screen_text": ("17:05/17:15/17:20/17:30；今天准点下班 和朋友约了一起吃饭；"
                 "吃一顿漂亮饭是我打工应得的"),
             "scene": "餐厅", "person_action": "下班赴约、用餐聊天",
             "shot_type": "手持自拍+餐食特写", "food_or_product": "晚餐（烤鸡/意面/饮品）",
             "product_first_appearance": 120.0, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [108.0, 116.0, 120.0, 132.0, 144.0],
             "audio_evidence_timestamps": None, "confidence": 0.85},
            {"start_time": 148.0, "end_time": 153.5,
             "transcript_summary": None,
             "on_screen_text": "19:15；今天的打工日记就到这吧 下次见",
             "scene": "城市夜景", "person_action": None,
             "shot_type": "夜景空镜+结尾字幕卡", "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [150.0, 152.0],
             "audio_evidence_timestamps": None,
             "confidence": 0.9},
        ],
        "style_summary": {
            "structure": ("时间戳字幕驱动的打工人一日叙事：晨间准备→通勤→早餐→办公→午餐→"
                "下班晚餐→夜景收尾"),
            "avg_shot_s": 2.4,
            "narration_relation": ("口播旁白为主线，字幕承担时间戳+情绪梗（'呕血''都市隶人'），"
                "画面为自拍+固定机位混合"),
            "food_insertion_points": ("冰美式贯穿（18s/33s两杯）、早餐炒蛋38s、午餐意粉78s、"
                "晚餐120s；均为生活流自然位置"),
            "product_first_appearance_s": 14.0,
            "commercial_pattern": "本视频无明确商单；香水为自用展示型口播（未确认软广）",
            "reusable_high_level": ["时间戳字幕结构", "打工人共鸣开场问候", "饮品贯穿的生活流动线",
                                  "自拍+固定机位混合视角", "夜景空镜+固定结束语"],
            "do_not_copy": ["'早上坏/都市隶人/呕血'等个人化打工人梗", "INTP等人格标签人设",
                          "具体香水自用描述", "固定结束语句式"],
            "compliance_scan": "未发现减肥/燃脂/降糖/医疗类表达；'呕血'为情绪梗非健康宣称",
        },
    },
    "586733cd50c4b43cccffc5c8": {  # 小季没烦恼
        "note_id": "6a58b7ea000000001101a7bb",
        "title": "晚间日记🧺6.pm—11pm下班后才是生活的开始",
        "duration_s": 114.0,
        "primary_format": "subtitle_immersive",
        "asr_reliability": "unreliable",
        "asr_note": "无口播，仅BGM与环境音；faster-whisper small 对BGM产生幻觉文本"
                    "（'好美啊/古典沙夫'），不作为口播证据",
        "hook_analysis": "0-6s 到家仍亮的天色+浴室放松快切，字幕'好喜欢这个季节 到家了天还是亮的' "
                         "直接点题'下班后才是生活的开始'，晚霞空镜制造治愈预期",
        "segments": [
            {"start_time": 0.0, "end_time": 6.0,
             "transcript_summary": None,
             "on_screen_text": "好喜欢这个季节 到家了天还是亮的",
             "scene": "家中玄关/浴室", "person_action": "回家、洗漱放松",
             "shot_type": "固定机位中近景快切", "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [0.0, 2.0, 4.0],
             "audio_evidence_timestamps": None, "confidence": 0.9},
            {"start_time": 6.0, "end_time": 16.0,
             "transcript_summary": None,
             "on_screen_text": "被今天的绝美晚霞击中；小鱼先吃",
             "scene": "窗边/鱼缸", "person_action": "拍晚霞、喂鱼",
             "shot_type": "窗外空镜+俯拍特写", "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [8.0, 10.0, 12.0],
             "audio_evidence_timestamps": None, "confidence": 0.9},
            {"start_time": 16.0, "end_time": 28.0,
             "transcript_summary": None,
             "on_screen_text": (
                 "自从霸王茶姬出了轻因系列 一到晚上就想来一杯；"
                 "他们现在还更新了咖啡因仪表盘；"
                 "不用担心因为不清楚咖啡因含量导致喝了睡不着；开启我的治愈夜晚"
             ),
             "scene": "客厅/吧台", "person_action": "取外卖袋、展示新品、试喝",
             "shot_type": "第一人称手持特写+中景展示",
             "food_or_product": "霸王茶姬轻因系列（CHAGEE）",
             "product_first_appearance": 16.0,
             "commercial_expression": (
                 "品牌植入段：外卖取货→新品展示→"
                 "卖点字幕（咖啡因仪表盘/低咖啡因不失眠）→试喝，约10s占比9%"
             ),
             "compliance_risks": ["轻因(低咖啡因)概念宣称，引用时需品牌方提供依据"],
             "evidence_frame_timestamps": [16.0, 18.0, 20.0, 22.0, 24.0, 26.0],
             "audio_evidence_timestamps": None, "confidence": 0.95},
            {"start_time": 28.0, "end_time": 46.0,
             "transcript_summary": None,
             "on_screen_text": ("爱上做红油钵钵鸡；荤素搭配全都是自己喜欢的；水开下食材；"
                 "荤素分开煮；放入冰水晾凉"),
             "scene": "厨房", "person_action": "串食材、煮制、过冰水、调汁浸泡",
             "shot_type": "俯拍特写+第一人称操作视角",
             "food_or_product": "自制红油钵钵鸡",
             "product_first_appearance": 28.0, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [28.0, 30.0, 34.0, 36.0, 38.0, 40.0, 44.0],
             "audio_evidence_timestamps": None, "confidence": 0.9},
            {"start_time": 46.0, "end_time": 58.0,
             "transcript_summary": None,
             "on_screen_text": "汁水很足；夏日 空调 美食 电影 爽；幸福就藏匿在这些微小的缝隙里✨",
             "scene": "客厅", "person_action": "切香瓜、摆盘、边看电视边吃",
             "shot_type": "俯拍特写+客厅全景",
             "food_or_product": "香瓜+钵钵鸡",
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [48.0, 50.0, 52.0, 54.0, 56.0],
             "audio_evidence_timestamps": None, "confidence": 0.9},
            {"start_time": 58.0, "end_time": 72.0,
             "transcript_summary": None,
             "on_screen_text": "换了柠檬奶绿舒服多了；放弃了很多不必要的社交；不再内耗",
             "scene": "客厅地毯", "person_action": "独食、喝饮品",
             "shot_type": "中近景+第一人称手持",
             "food_or_product": "柠檬奶绿（饮品）",
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [58.0, 60.0, 62.0, 64.0, 70.0],
             "audio_evidence_timestamps": None, "confidence": 0.85},
            {"start_time": 72.0, "end_time": 94.0,
             "transcript_summary": None,
             "on_screen_text": "防蚊喷雾是夏天出门必带的",
             "scene": "厨房/客厅", "person_action": "洗碗、点香薰、拆快递展示润本防蚊喷雾",
             "shot_type": "第一人称特写+开箱俯拍",
             "food_or_product": "润本防蚊喷雾",
             "product_first_appearance": 90.0,
             "commercial_expression": "开箱短暂展示（约2-3s），非卖点口播，植入存在感低",
             "compliance_risks": [],
             "evidence_frame_timestamps": [76.0, 84.0, 88.0, 90.0, 92.0],
             "audio_evidence_timestamps": None, "confidence": 0.85},
            {"start_time": 94.0, "end_time": 114.0,
             "transcript_summary": None,
             "on_screen_text": ("睡前尽量不玩手机；大脑里乱七八糟的事情没有了；"
                 "在自己喜欢的时间里按照自己喜欢的方式去做自己喜欢做的事；晚安🌛"),
             "scene": "书桌", "person_action": "点蜡烛、练毛笔字",
             "shot_type": "侧拍中景+字帖特写+黑底结尾字幕",
             "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [96.0, 100.0, 102.0, 104.0, 110.0, 112.0],
             "audio_evidence_timestamps": None, "confidence": 0.9},
        ],
        "style_summary": {
            "structure": "晚间治愈流程叙事：回家放松→晚霞喂鱼→饮品植入→做饭→独食→家务开箱→练字晚安",
            "avg_shot_s": 2.5,
            "narration_relation": ("无口播；字幕承担叙事+情绪+卖点，BGM治愈系，"
                "画面以第一人称操作视角为主"),
            "food_insertion_points": ("饮品16s（商单）、自制钵钵鸡28s、香瓜46s、奶绿58s；"
                "食品贯穿全片"),
            "product_first_appearance_s": 16.0,
            "commercial_pattern": (
                "双植入：霸王茶姬（16-26s集中卖点段）+润本防蚊喷雾（90s开箱露出）；"
                "主商单用'需求场景（晚上想喝但怕失眠）→产品解法（轻因系列）'结构，自然度高"
            ),
            "reusable_high_level": ["下班后治愈场景框架", "需求场景→产品解法的植入结构",
                                  "第一人称操作视角做食品", "结尾黑底固定问候"],
            "do_not_copy": [
                "'6.pm—11pm下班后才是生活的开始'系列标题句式",
                "练字/喂鱼/晚霞的个人治愈符号组合",
                "治愈系长文案字幕原文",
            ],
            "compliance_scan": (
                "未发现减肥/燃脂/降糖/医疗表达；'轻因'为咖啡因概念，引用时需提供品牌依据"
            ),
        },
    },
    "5ad034864eacab543fa98374": {  # 一只牛🐮
        "note_id": "6a59b5ac00000000100295fe",
        "title": "Vlog | 独居 早餐",
        "duration_s": 54.7,
        "primary_format": "subtitle_immersive",
        "asr_reliability": "unreliable",
        "asr_note": "无口播，仅环境音；faster-whisper small 对烹饪声/BGM产生幻觉文本"
                    "（'白糖/盐'循环），不作为口播证据",
        "hook_analysis": "0s 成品三明治特写直接开场（先看结果再回溯过程），无标题卡，"
                         "靠食物质感抓注意力，符合沉浸式早餐号惯例",
        "segments": [
            {"start_time": 0.0, "end_time": 2.0,
             "transcript_summary": None, "on_screen_text": None,
             "scene": "餐桌", "person_action": "端起成品三明治展示",
             "shot_type": "俯拍特写", "food_or_product": "法棍三明治（成品）",
             "product_first_appearance": 0.0, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [0.0],
             "audio_evidence_timestamps": None, "confidence": 0.9},
            {"start_time": 2.0, "end_time": 12.0,
             "transcript_summary": None, "on_screen_text": None,
             "scene": "厨房台面", "person_action": "拆法棍、削黄瓜片",
             "shot_type": "俯拍特写+第一人称操作视角", "food_or_product": "法棍、黄瓜",
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [2.0, 6.0, 8.0, 10.0],
             "audio_evidence_timestamps": None, "confidence": 0.9},
            {"start_time": 12.0, "end_time": 26.0,
             "transcript_summary": None,
             "on_screen_text": "试试不加牛奶的滑蛋；更容易滑熟，蛋味更浓😋；刚烤好的，铁手也怕烫hh",
             "scene": "灶台", "person_action": "打蛋、炒滑蛋、煎火腿、烤法棍",
             "shot_type": "俯拍特写", "food_or_product": "滑蛋、火腿",
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [14.0, 16.0, 18.0, 20.0, 22.0, 24.0],
             "audio_evidence_timestamps": None, "confidence": 0.9},
            {"start_time": 26.0, "end_time": 34.0,
             "transcript_summary": None, "on_screen_text": None,
             "scene": "餐桌", "person_action": "组装三明治（抹酱、叠黄瓜火腿滑蛋）",
             "shot_type": "俯拍特写+第一人称操作视角", "food_or_product": "三明治组装",
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [26.0, 28.0, 30.0, 32.0],
             "audio_evidence_timestamps": None, "confidence": 0.9},
            {"start_time": 34.0, "end_time": 40.0,
             "transcript_summary": None,
             "on_screen_text": "这个天气，需要冰美式🧊",
             "scene": "餐桌", "person_action": "倒冰美式",
             "shot_type": "俯拍特写", "food_or_product": "冰美式（咖啡）",
             "product_first_appearance": 36.0, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [36.0, 38.0, 40.0],
             "audio_evidence_timestamps": None, "confidence": 0.9},
            {"start_time": 40.0, "end_time": 48.0,
             "transcript_summary": None,
             "on_screen_text": "三明治里加黄瓜，很清爽~；法棍也是脆脆的，很有嚼劲😋",
             "scene": "餐桌", "person_action": "边吃边看iPad",
             "shot_type": "手持特写+中景", "food_or_product": "三明治+冰美式",
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [42.0, 44.0, 46.0, 48.0],
             "audio_evidence_timestamps": None, "confidence": 0.9},
            {"start_time": 48.0, "end_time": 54.7,
             "transcript_summary": None,
             "on_screen_text": "Thanks for following~",
             "scene": "餐桌", "person_action": "收尾展示盘中三明治",
             "shot_type": "俯拍中景+结尾字幕", "food_or_product": "三明治",
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [50.0, 52.0],
             "audio_evidence_timestamps": None, "confidence": 0.9},
        ],
        "style_summary": {
            "structure": "线性制作流：成品开场→备料→烹饪→组装→饮品→用餐→固定英文结束语",
            "avg_shot_s": 2.0,
            "narration_relation": (
                "无口播；字幕极少且只做制作说明与口感点评（每段<=15字），环境音为主"
            ),
            "food_insertion_points": "全片即食品制作流；冰美式36s为唯一饮品位",
            "product_first_appearance_s": 0.0,
            "commercial_pattern": "无商单；纯自制早餐内容",
            "reusable_high_level": ["成品先行开场", "线性制作流程", "少字幕+环境音的沉浸感",
                                  "饮品与主餐的固定搭配位"],
            "do_not_copy": ["'Vlog | 独居 早餐'极简标题模板", "Thanks for following~固定英文结束语",
                          "'铁手也怕烫hh'等个人化语气"],
            "compliance_scan": "未发现减肥/燃脂/降糖/医疗表达；无风险",
        },
    },
}


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_creator = {v["creator_id"]: v for v in manifest["videos"]}
    doc = {"generated_at": utc_now(),
           "source": "ai_inferred（关键帧多模态读取+转写合并，证据时间戳可追溯）",
           "timelines": []}
    for cid, tl in TIMELINES.items():
        m = by_creator.get(cid, {})
        entry = dict(tl)
        entry["creator_id"] = cid
        entry["file"] = m.get("file")
        entry["keyframes"] = {k: v for k, v in (m.get("keyframes") or {}).items()
                              if k in ("interval_total", "scene_total", "deduped_total",
                                       "valid_interval")}
        entry["segments_count"] = len(tl["segments"])
        doc["timelines"].append(entry)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] {OUT.name}: {len(doc['timelines'])} 条时间线，"
          f"共 {sum(t['segments_count'] for t in doc['timelines'])} 个片段")
    return 0


if __name__ == "__main__":
    sys.exit(main())
