"""Stage 4 欧盈Kelly 剩余 2 条视频时间线构建：合并音频转写与关键帧视觉分析。

模式复用 scripts/build_stage_3_timelines.py（不开发新架构）。
时间线内容来源：
- 关键帧多模态逐帧读取（tmp/stage4_kelly/<note_id>/contact_sheet_*.jpg 及
  keyframes/interval_*.jpg 单帧复核，开场卡/调酒段/看剧段字幕以单帧为准）；
- faster-whisper small 本地转写（繁体噪声，同音错字以画面字幕交叉校正；
  video1 约 97-111s 存在 ASR 重复幻觉循环，已在 asr_note 标注）；
- 页面证据与文件/关键帧统计（tmp/stage4_kelly/stage_4_kelly_video_manifest.json，
  仅本地产物；Git 侧不落签名 URL，只落其 SHA-256 与域名）。

规则：不确定视觉字段写 null；不根据音频编造画面；不根据画面编造口播；
完整逐字稿不进 Git，只保留短证据片段。

输出：data/processed/stage_4_kelly_video_timelines.json
用法：python scripts/build_stage_4_kelly_timelines.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/processed/stage_4_kelly_video_timelines.json"
MANIFEST = ROOT / "tmp/stage4_kelly/stage_4_kelly_video_manifest.json"

CREATOR_ID = "60bb90f00000000001002887"  # 欧盈Kelly


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


TIMELINES = {
    "6a5c556e000000000c0162f5": {
        "title": "深圳MKTer vlog |打工的唯一目的赚钱享受",
        "duration_s": 219.43,
        "primary_format": "voiceover",
        "asr_reliability": "reliable_with_noise",
        "asr_note": ("faster-whisper small 转写为繁体且有同音错字（如'螺丝粉'实为螺蛳粉、"
                     "'调金烤肉'实为调金汤力、'红烧'实为泉州），语义以画面字幕交叉校正；"
                     "约97-111s存在ASR重复幻觉循环（同三句重复3次），已剔除不计证据"),
        "hook_analysis": ("0-4s 晚间餐厅内自拍冷开场+中英双语大标题卡"
                          "（深圳Marketing打工人一天劳作/A full day of work...），"
                          "2s 即给螺蛳粉特写预告当晚高光，4s 起倒带回 16:58 办公室"
                          "——结果前置+时间戳倒带结构，与第一条的线性晨起结构不同"),
        "segments": [
            {"start_time": 0.0, "end_time": 4.0,
             "transcript_summary": "开场问候，欢迎收看深圳打工的一日",
             "on_screen_text": ("深圳Marketing打工人一天劳作；A full day of work as a "
                              "Marketing girl in ShenZhen；欢迎收看深圳打工人的一日劳作"),
             "scene": "餐厅（晚间）", "person_action": "举相机自拍环视",
             "shot_type": "自拍仰拍+中英双语大标题卡",
             "food_or_product": "螺蛳粉（2s特写预告）",
             "product_first_appearance": 2.0, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [0.0, 2.0],
             "audio_evidence_timestamps": [[0.0, 3.2]], "confidence": 0.9},
            {"start_time": 4.0, "end_time": 16.0,
             "transcript_summary": "改完方案没什么事可以准时下班，很开心",
             "on_screen_text": ("16:58；全公司都给我甩需求 唯独客户没动静；今天改完方案；"
                              "每次准时下班都好开心"),
             "scene": "办公室工位", "person_action": "工位办公、收拾电脑拎包",
             "shot_type": "固定机位中景+手持特写", "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [4.0, 6.0, 8.0, 12.0, 14.0],
             "audio_evidence_timestamps": [[8.1, 16.9]], "confidence": 0.9},
            {"start_time": 16.0, "end_time": 28.0,
             "transcript_summary": "下班天气好可以拍素材；打车去吃饭",
             "on_screen_text": ("17:08 等车间隙分享下美甲和戒指；17:10 下班起这个天气很好看；"
                              "17:13 很幸运 打到一辆不臭的车；17:20 又被我赚到了"),
             "scene": "户外街道/网约车", "person_action": "等车、车内自拍",
             "shot_type": "全身跟拍+车内自拍", "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [16.0, 18.0, 24.0, 26.0],
             "audio_evidence_timestamps": [[18.2, 22.2]], "confidence": 0.9},
            {"start_time": 28.0, "end_time": 48.0,
             "transcript_summary": "到店吃螺蛳粉，重温第一条视频的一人食题材",
             "on_screen_text": ("17:25 一个人吃晚饭；18:05 今天打算去吃个螺蛳粉；"
                              "又想起我第一条视频就是拍一人食；18:12 这有个手牌；"
                              "风一吹他就动了；但是挺适合社恐的"),
             "scene": "螺蛳粉店门面/店内格子间",
             "person_action": "进店、手机点餐、落座格子间",
             "shot_type": "门面固定镜头+店内第一人称+手机屏幕特写",
             "food_or_product": "螺蛳粉（点餐）",
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [28.0, 30.0, 32.0, 34.0, 38.0, 40.0, 42.0,
                                           44.0, 46.0],
             "audio_evidence_timestamps": [[23.2, 37.2], [45.2, 48.2]],
             "confidence": 0.9},
            {"start_time": 48.0, "end_time": 66.0,
             "transcript_summary": "加单水果和豆花；戴眼镜方便捞豆花（吃前仪式感）",
             "on_screen_text": ("18:12 一个人在小小的格子间 终于能放下所有装出来的体面；"
                              "18:15 跟着又加单水果和豆花；看这满满一大桌 感觉又点多了；"
                              "18:16 吃前仪式感；下饭剧准备好"),
             "scene": "店内格子间",
             "person_action": "扎头发戴眼镜、架手机播下饭剧、摆拍满桌餐食",
             "shot_type": "自拍中近景+餐食特写",
             "food_or_product": "螺蛳粉+豆花+水果+瓶装豆奶",
             "product_first_appearance": 52.0, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [48.0, 50.0, 52.0, 54.0, 56.0, 58.0, 60.0,
                                           62.0, 64.0],
             "audio_evidence_timestamps": [[48.2, 56.2], [58.2, 65.2]],
             "confidence": 0.85},
            {"start_time": 66.0, "end_time": 88.0,
             "transcript_summary": None,
             "on_screen_text": ("18:18 开动 大口摄入碳水；就很难再凑到一起；"
                              "没关系 一个人也要…；有点辣；18:40 吃不完也别浪费粮食 "
                              "通通打包；意满离；19:38 刚吃完之后呢"),
             "scene": "店内格子间", "person_action": "吃粉、喝豆奶、手持小风扇、打包",
             "shot_type": "自拍中近景+手持特写",
             "food_or_product": "螺蛳粉+瓶装豆奶",
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [66.0, 68.0, 70.0, 72.0, 74.0, 76.0, 78.0,
                                           80.0, 84.0, 86.0],
             "audio_evidence_timestamps": [[80.2, 88.2]], "confidence": 0.85},
            {"start_time": 88.0, "end_time": 108.0,
             "transcript_summary": ("带着一身螺蛳粉味去按摩有点不好意思，肩颈不舒服；"
                                  "到店闻到香薰精油很放松，选了60分钟全身精油按摩，可选精油味道"),
             "on_screen_text": ("19:38 带着我一身螺蛳粉味；去按摩有点不好意思；"
                              "19:40 但是最近肩颈特别不舒服；到啦；"
                              "就已经闻到他们的香薰精油味啦；19:42 真的好放松的感觉；"
                              "19:48 侘寂风装修的房间很舒服；我就选这个60分钟的全身精油按摩；"
                              "还可以挑选精油的味道"),
             "scene": "城市夜景/SPA店",
             "person_action": "夜行、进店、闻香、选精油",
             "shot_type": "夜景空镜+自拍仰拍+手持精油特写",
             "food_or_product": None,
             "product_first_appearance": None,
             "commercial_expression": ("按摩店体验式消费记录（60分钟全身精油按摩/可选味道），"
                                     "无卖点话术，是否软广无法确认"),
             "compliance_risks": [],
             "evidence_frame_timestamps": [88.0, 90.0, 92.0, 94.0, 96.0, 98.0, 100.0,
                                           102.0, 104.0, 106.0],
             "audio_evidence_timestamps": [[88.2, 93.2], [97.2, 99.2]],
             "confidence": 0.9},
            {"start_time": 108.0, "end_time": 130.0,
             "transcript_summary": ("开始按摩，力度刚刚好，按得超级舒服；"
                                  "回忆在广州工作时经常和同事一起按摩"),
             "on_screen_text": ("19:55 好啦 开始啦；完全就是4D体验嘛；感觉整个人彻底松下来了；"
                              "20:15 比起谈恋爱 我更愿意花钱哄自己开心；"
                              "没有中间商 这份安全感谁也拿不走"),
             "scene": "按摩房", "person_action": "躺床接受全身精油按摩",
             "shot_type": "暗光固定机位+走廊空镜", "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [108.0, 112.0, 120.0, 124.0, 126.0, 128.0],
             "audio_evidence_timestamps": [[112.2, 118.2], [129.2, 140.2]],
             "confidence": 0.85},
            {"start_time": 130.0, "end_time": 148.0,
             "transcript_summary": "按好了挺舒服，洗完手上精油就出去吃点东西",
             "on_screen_text": ("按好了挺舒服的；蛮怀念的；20:58；就出去吃点东西"),
             "scene": "SPA休息区/洗手台", "person_action": "换浴袍躺靠、洗手、走向餐区",
             "shot_type": "自拍近景+第一人称+店内空镜", "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [130.0, 138.0, 140.0, 144.0, 146.0],
             "audio_evidence_timestamps": [[142.2, 145.2]], "confidence": 0.8},
            {"start_time": 148.0, "end_time": 160.0,
             "transcript_summary": ("店里有汤水、水饺、大鱼蛋之类提供，24小时可以煮，"
                                  "选项非常多，这个体验打10分"),
             "on_screen_text": ("这里面有汤、水饺；而且可以二十四小时煮的；选项非常多；"
                              "我这个体验就打十分"),
             "scene": "SPA餐区", "person_action": "盛汤、取茶叶蛋、进食",
             "shot_type": "第一人称俯拍+餐食特写",
             "food_or_product": "按摩店配套餐食（汤/水饺/大鱼蛋/茶叶蛋）",
             "product_first_appearance": 148.0,
             "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [148.0, 150.0, 152.0, 154.0, 156.0, 158.0],
             "audio_evidence_timestamps": [[147.2, 156.2]], "confidence": 0.9},
            {"start_time": 160.0, "end_time": 168.0,
             "transcript_summary": "出门回家",
             "on_screen_text": ("21:21 回快乐老家了；美丽刑具拜拜；"
                              "21:25 世界上最舒服的地方 除了床就是沙发"),
             "scene": "车窗夜景/家中玄关客厅",
             "person_action": "乘车、进门换拖鞋、瘫坐沙发",
             "shot_type": "车窗空镜+背影跟拍+第一人称脚部特写",
             "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [160.0, 162.0, 164.0, 166.0],
             "audio_evidence_timestamps": [[159.2, 160.2]], "confidence": 0.85},
            {"start_time": 168.0, "end_time": 198.0,
             "transcript_summary": ("拆朋友去泉州买的手信（师傅手写的中式灯笼），期待好久；"
                                  "师傅很出名，很多明星也去探店"),
             "on_screen_text": ("21:40 这是我朋友去泉州买的一个手信；这个本身是师傅写的；"
                              "比我想象中的…（部分字迹不清）；是很简单的那种；"
                              "而且很中式美学；这个师父很出名了；很多明星过去探店"),
             "scene": "家中沙发",
             "person_action": "拆箱展示红色中式灯笼、手持手机展示店家照片",
             "shot_type": "固定机位中景+手持特写", "food_or_product": None,
             "product_first_appearance": None,
             "commercial_expression": "朋友手信拆箱（非售卖引导），未确认软广",
             "compliance_risks": [],
             "evidence_frame_timestamps": [168.0, 170.0, 178.0, 180.0, 184.0, 186.0,
                                           190.0, 192.0, 194.0],
             "audio_evidence_timestamps": [[169.2, 199.2]], "confidence": 0.9},
            {"start_time": 198.0, "end_time": 219.43,
             "transcript_summary": "今天也是调金汤力，这瓶快喝完了；今天的日常就到这里",
             "on_screen_text": ("21:48 松弛人格上线；22:03 今天也是调金汤力；"
                              "好久没拍在家调酒 是不是忘了我是酒蒙子；"
                              "究竟是谁会在家里囤冰杯；这瓶快喝完了；"
                              "好啦 今天的日常就到这里啦；"
                              "画面右侧竖排固定提示：未成年禁止饮酒"),
             "scene": "家中客厅",
             "person_action": "对镜自拍换睡衣、调金汤力（冰杯+柠檬+酒瓶）、饮用",
             "shot_type": "固定机位中景+俯拍调酒特写",
             "food_or_product": "金汤力（居家自调酒）",
             "product_first_appearance": 200.0, "commercial_expression": None,
             "compliance_risks": [
                 "含居家调酒/饮酒内容（画面已自带'未成年禁止饮酒'竖排提示）；"
                 "酒类场景与乳制品品牌调性适配需评估"],
             "evidence_frame_timestamps": [198.0, 200.0, 202.0, 204.0, 206.0, 208.0,
                                           210.0, 212.0, 214.0, 216.0],
             "audio_evidence_timestamps": [[200.2, 202.2], [216.2, 219.2]],
             "confidence": 0.9},
        ],
        "style_summary": {
            "structure": ("冷开场（晚间餐厅+螺蛳粉预告）→时间戳倒带回16:58办公室→准时下班→"
                "一人食螺蛳粉→精油按摩→店内配套简餐→回家拆手信→调酒收尾的下班后叙事"),
            "avg_shot_s": 2.5,
            "narration_relation": ("口播旁白为主线（SRT有声段合计约136s，约占62%时长）；"
                "字幕承担24h时间戳（16:58→22:03）+情绪点评；"
                "画面为自拍+第一人称操作+固定机位混合"),
            "food_insertion_points": ("2s螺蛳粉预告、36s瓶装豆奶、48-88s螺蛳粉正餐、"
                "148s按摩店配套简餐、200s居家调酒；均落在生活流自然位置"),
            "product_first_appearance_s": 2.0,
            "commercial_pattern": ("无明确商单；按摩店为体验式消费记录（是否软广无法确认），"
                "泉州灯笼为朋友手信拆箱；无链接/橱窗/同款类口播"),
            "reusable_high_level": ["结果前置冷开场+时间戳倒带", "24h时间戳字幕推进全天",
                "饮品/餐食沿生活动线贯穿", "第一人称操作视角与自拍混合",
                "情绪点评式短字幕", "固定收束语+夜景/居家空镜收尾"],
            "do_not_copy": ["'打工的唯一目的赚钱享受'类个人价值观标题句式",
                "'意满离/美丽刑具拜拜/松弛人格上线'等个人梗",
                "INTP等人格标签人设", "具体按摩店/手信店与师傅信息",
                "'酒蒙子'饮酒人设表达与调酒桥段"],
            "compliance_scan": ("未见减肥/燃脂/掉秤/降糖/医疗类表达；风险词'第一'命中语境为"
                "'第一条视频'，非绝对化宣称；200s起含居家调酒内容"
                "（画面自带'未成年禁止饮酒'提示），酒类场景与乳制品品牌适配需评估"),
        },
    },
    "6a5616b600000000220164a4": {
        "title": "i人vlog｜一个人尝试潜水 不完美也没关系",
        "duration_s": 164.77,
        "primary_format": "voiceover",
        "asr_reliability": "reliable_with_noise",
        "asr_note": ("faster-whisper small 转写为繁体且有同音错字（如'水費'实为水肺、"
                     "'克拉克森的美妆'实为克拉克森的农场），语义以画面字幕交叉校正；"
                     "约59.8-76.8s水下段为BGM无口播"),
        "hook_analysis": ("0-6s 户外现代建筑旁+衬线大标题卡（INTP DAILY VLOG/"
                          "自由潜 一人食 发呆/富养自己的一天），"
                          "口播直抛'今天挑战水肺潜水'的挑战悬念，'富养自己'主题定调"),
        "segments": [
            {"start_time": 0.0, "end_time": 6.0,
             "transcript_summary": "周末富养自己的一天，今天挑战的是水肺潜水",
             "on_screen_text": ("INTP DAILY VLOG；自由潜 一人食 发呆；富养自己的一天；"
                              "今天挑战的是水肺潜水"),
             "scene": "户外现代建筑旁", "person_action": "手持饮品走动、家中背影出门",
             "shot_type": "衬线大标题卡+人物中景", "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [0.0, 2.0, 4.0],
             "audio_evidence_timestamps": [[0.0, 3.6]], "confidence": 0.9},
            {"start_time": 6.0, "end_time": 22.0,
             "transcript_summary": ("来到深圳新开的全民潜水馆，有自由潜和水肺可选；"
                                  "本身不太会游泳所以选了较能挑战的；装备都是备好的"),
             "on_screen_text": ("这次来到的是；深圳最近新开的一个全民潜水馆；"
                              "进门就是很宽敞的大堂；有自由潜和水肺选择；"
                              "因为我本身不太会游泳；装备他们都是备好的"),
             "scene": "潜水馆外观/大堂/装备间",
             "person_action": "电梯镜前自拍、前台咨询、参观装备架",
             "shot_type": "镜子自拍+第一人称跟拍", "food_or_product": None,
             "product_first_appearance": None,
             "commercial_expression": "潜水馆体验式消费记录（新店），无卖点话术，是否软广无法确认",
             "compliance_risks": [],
             "evidence_frame_timestamps": [6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0],
             "audio_evidence_timestamps": [[6.8, 22.4]], "confidence": 0.9},
            {"start_time": 22.0, "end_time": 34.0,
             "transcript_summary": ("换好装备准备下潜，看到池子已经有点害怕，"
                                  "最近看太多洞潜视频，确实有点压力"),
             "on_screen_text": "我准备下潜；已经有点害怕了；看着确实有点压力",
             "scene": "更衣区/室内大泳池",
             "person_action": "换潜水服、池边观望迟疑",
             "shot_type": "第一人称脚部特写+泳池大全景+池边自拍",
             "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [22.0, 24.0, 26.0, 28.0, 30.0],
             "audio_evidence_timestamps": [[22.4, 33.4]], "confidence": 0.9},
            {"start_time": 34.0, "end_time": 54.0,
             "transcript_summary": ("教练带整个流程：怎么带装备、怎么下水呼吸；"
                                  "带上装备那一刻很害怕，最后还是挑战了；"
                                  "呼吸有点急促下潜不久，但来都来了"),
             "on_screen_text": ("现在教练都会带你过一个；怎么下水呼吸；确实是有点害怕的；"
                              "最后还是挑战了一下"),
             "scene": "泳池浅水区",
             "person_action": "穿戴水肺装备、扶梯下水、水中练习呼吸",
             "shot_type": "他人跟拍+水中镜头", "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [34.0, 38.0, 40.0, 42.0, 44.0, 46.0, 48.0,
                                           50.0, 52.0],
             "audio_evidence_timestamps": [[33.4, 54.0]], "confidence": 0.9},
            {"start_time": 54.0, "end_time": 84.0,
             "transcript_summary": ("水下要把身体和注意力放心交给自己；还是有些紧张；"
                                  "能下潜已经很厉害了；开始适应好时时间已经到了；"
                                  "handle不了没关系，下次继续挑战"),
             "on_screen_text": ("教练说在水下 要把身体和注意力放心交给自己；"
                              "潜水天赋点发掘失败；虽然但是 能下潜已经很厉害了；"
                              "不敢看下面 确实好深；时间已经到了"),
             "scene": "水下",
             "person_action": "水下坐立调息、环视、上潜出水",
             "shot_type": "水下拍摄（面镜特写/全身/他人自由潜远景）",
             "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [54.0, 56.0, 58.0, 60.0, 62.0, 64.0, 66.0,
                                           68.0, 70.0, 72.0, 74.0, 76.0, 80.0, 82.0],
             "audio_evidence_timestamps": [[54.0, 59.8], [76.8, 88.8]],
             "confidence": 0.85},
            {"start_time": 84.0, "end_time": 96.0,
             "transcript_summary": "下次再来我一定可以下去；潜完水还有点时间，就去做个美甲",
             "on_screen_text": "等再过来；我一定可以下去；潜完水还有点时间",
             "scene": "馆内电梯/网约车",
             "person_action": "电梯自拍比手势、乘车看城市天际线",
             "shot_type": "镜子自拍+车窗空镜", "food_or_product": None,
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [86.0, 88.0, 90.0, 92.0, 94.0],
             "audio_evidence_timestamps": [[94.0, 97.8]], "confidence": 0.85},
            {"start_time": 96.0, "end_time": 108.0,
             "transcript_summary": ("大家猜做了什么颜色；这也是我经常在广州吃的一家店；"
                                  "做了美甲心情都变美了"),
             "on_screen_text": ("大家猜一下我做的什么颜色；人生能像猪肠粉一样美味吗；"
                              "选了一个简单的；请直视我的新皮肤 满意 欣赏之；心情都变美了"),
             "scene": "美甲店",
             "person_action": "手持猪肠粉和柠檬茶、翻色板、照灯做美甲",
             "shot_type": "手持食物特写+第一人称色板+美甲过程近景",
             "food_or_product": "猪肠粉+柠檬茶",
             "product_first_appearance": 98.0,
             "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [96.0, 98.0, 100.0, 102.0, 104.0, 106.0],
             "audio_evidence_timestamps": [[94.0, 97.8], [99.6, 102.0], [107.8, 109.4]],
             "confidence": 0.9},
            {"start_time": 108.0, "end_time": 138.0,
             "transcript_summary": "今天挑战一个新的菜谱；每天都在挑战我不擅长的东西",
             "on_screen_text": ("今天挑战一个新的菜谱；简单做个辣肥牛乌冬吧；来煎个蛋；"
                              "形状不太美好 忽视掉；最后一步 成功在即；"
                              "我就说网上能学到真东西吧 起码卖相还不错；维持生命餐get"),
             "scene": "家中厨房",
             "person_action": "开冰箱取料、煎蛋、煮乌冬、加肥牛午餐肉出锅",
             "shot_type": "第一人称俯拍操作+灶台特写",
             "food_or_product": "辣肥牛乌冬（自制）",
             "product_first_appearance": 114.0, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [108.0, 112.0, 114.0, 116.0, 118.0, 120.0,
                                           134.0, 136.0, 138.0],
             "audio_evidence_timestamps": [[111.8, 113.8], [117.8, 120.8]],
             "confidence": 0.9},
            {"start_time": 138.0, "end_time": 164.77,
             "transcript_summary": ("好久没做指甲，做了白色清新款；人还是要勇于踏出那一步，"
                                  "不然不知道极限在哪里；做了美甲潜了水，今天也是满足的一天"),
             "on_screen_text": ("克拉克森的农场（下饭）；找部喜欢的剧 开始干饭；"
                              "折腾这大半天 累是累 但心里舒服多了；好久没做过指甲了；"
                              "做了一个白色；不然你也不知道你的极限去哪里"),
             "scene": "家中客厅沙发",
             "person_action": "边吃乌冬边看笔记本、展示脚部白色美甲、盘腿总结",
             "shot_type": "固定机位中景+第一人称脚部特写",
             "food_or_product": "辣肥牛乌冬（进食）",
             "product_first_appearance": None, "commercial_expression": None,
             "compliance_risks": [],
             "evidence_frame_timestamps": [140.0, 142.0, 146.0, 148.0, 150.0, 152.0,
                                           156.0, 158.0, 160.0],
             "audio_evidence_timestamps": [[138.8, 142.8], [146.8, 164.8]],
             "confidence": 0.9},
        ],
        "style_summary": {
            "structure": ("挑战主题开场→到馆选项目→换装备见池害怕→教练教学下水→"
                "水下体验（害怕到适应）→离场→美甲→回家做辣肥牛乌冬→沙发干饭+感悟收尾"),
            "avg_shot_s": 2.4,
            "narration_relation": ("口播旁白为主线（SRT有声段合计约94s，约占57%时长）；"
                "水下段约17s纯BGM留白无口播；字幕承担情绪解说与梗"),
            "food_insertion_points": ("98s猪肠粉+柠檬茶（美甲店场景）、114s起自制辣肥牛乌冬；"
                "食品整体后置，前96s无食品"),
            "product_first_appearance_s": 98.0,
            "commercial_pattern": ("无明确商单；潜水馆/美甲店为体验式消费记录"
                "（是否软广无法确认）；无链接/橱窗/同款类口播"),
            "reusable_high_level": ["挑战型开场直抛悬念", "害怕→尝试→接纳的情绪弧线",
                "高强度场景用BGM留白而非硬口播", "结尾感悟落到'踏出舒适区'母题",
                "美甲/做饭等生活场景承接主场景余温"],
            "do_not_copy": ["'富养自己的一天'系列主题句与'i人'人设标签",
                "INTP DAILY VLOG衬线标题卡模板与'自由潜 一人食 发呆'主题词组合",
                "'潜水天赋点发掘失败'等个人自嘲梗", "具体潜水馆/美甲店信息"],
            "compliance_scan": ("未见减肥/燃脂/掉秤/降糖/医疗/绝对化表达；"
                "'挑战极限'为励志语境非功效宣称；风险词扫描无命中"),
        },
    },
}


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_note = {v["note_id"]: v for v in manifest["videos"]}
    doc = {"generated_at": utc_now(),
           "source": "ai_inferred（关键帧多模态读取+转写合并，证据时间戳可追溯）",
           "stage": "stage_4_kelly_remaining_2_videos",
           "timelines": []}
    for note_id, tl in TIMELINES.items():
        m = by_note.get(note_id)
        if not m or m.get("status") != "media_processed":
            print(f"[ERR] manifest 缺少已处理条目: {note_id}")
            return 1
        entry = dict(tl)
        entry["creator_id"] = CREATOR_ID
        entry["note_id"] = note_id
        entry["canonical_url"] = m["canonical_url"]
        entry["page_evidence"] = m.get("page_evidence")
        entry["file"] = m.get("file")
        entry["media_url_sha256"] = m.get("media_url_sha256")
        entry["media_domain"] = m.get("media_domain")
        entry["download_source"] = m.get("download_source")
        entry["asr"] = m.get("asr")
        entry["keyframes"] = {k: v for k, v in (m.get("keyframes") or {}).items()
                              if k in ("interval_total", "scene_total", "deduped_total",
                                       "valid_interval", "contact_sheets")}
        entry["segments_count"] = len(tl["segments"])
        doc["timelines"].append(entry)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] {OUT.name}: {len(doc['timelines'])} 条时间线，"
          f"共 {sum(t['segments_count'] for t in doc['timelines'])} 个片段")
    return 0


if __name__ == "__main__":
    sys.exit(main())
