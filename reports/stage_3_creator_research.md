# Stage 3 真实小红书达人采集与评分报告

- 生成时间：2026-07-19
- 阶段状态：`blocked_by_insufficient_verified_candidates`（最终候选 6/10，不虚构补齐）
- 基础设施：复用 Stage 2 冻结的只读 CDP 链路，本阶段未开发任何新的浏览器/下载/转写能力
- 数据边界：所有页面事实为 `page_observed`，受众与商业自然度为 `ai_inferred`，全部候选 `human_verified=false`；未读取/保存 Cookie、storage 与登录信息
- 结论性质：仅为研究候选名单，不构成商业合作定案；`commercial_selected_creator` 未设置

---

## 1. 搜索执行摘要

使用 Stage 2 冻结的 CDP 已登录会话，对任务书规定的 8 个关键词逐一搜索，每词查看前 22 条返回结果：

| # | 搜索词 | 返回 | 新增候选 |
|---|---|---:|---:|
| 1 | 独居女生早餐vlog | 22 | 16 |
| 2 | 通勤女生早餐vlog | 22 | 6 |
| 3 | 上班族女生晨间vlog | 22 | 16 |
| 4 | 沉浸式一人食vlog | 22 | 16 |
| 5 | 办公室下午茶vlog | 22 | 15 |
| 6 | 健身女生运动后加餐vlog | 22 | 15 |
| 7 | 酸奶碗女生日常 | 22 | 18 |
| 8 | 都市女生生活vlog | 22 | 11 |

- 去重后原始候选 **113 位**（按真实 creator_id 去重，非昵称），保存于 `data/processed/stage_3_creator_pool.json`
- 搜索日志：`data/raw/stage_3_search_log.json`（含搜索词/时间/返回数/检查数/保留淘汰数）
- 主要召回问题：通勤/办公室类关键词混入大量图文知识号与品牌号；健身类关键词高频命中“减脂/掉秤”结果承诺型账号（预筛淘汰主因）
- 期间发生 1 次平台安全验证：自动化立即停止并记录于 `data/processed/stage_3_verification_events.json`，由人工完成验证后从断点恢复；未绕过、未导出 Cookie、未高频重试

## 2. 原始候选池（113 位）

- 文件：`data/processed/stage_3_creator_pool.json`（满足 ≥20 的硬性要求）
- 每位记录 creator_id、昵称、来源关键词、来源笔记、预筛场景与风险初判
- 基于搜索结果页证据预筛出 30 位进入主页核验：`data/processed/stage_3_prefiltered_30.json`
- 预筛维度：真实个人创作者 / 视频或 Vlog / 目标场景 / 180 天活跃 / 非品牌店铺号 / 非纯图文知识号 / 非减肥结果承诺 / 非医疗降糖 / creator_id 有效 / creator_id 去重

## 3. 主页深度核验（15 位通过）

- 实际访问主页 21 位，达到 15 位合格深度候选后按规则停止，未访问剩余账号
- 通过 15 位，保存于 `data/processed/stage_3_deep_review_15.json`；每位检查最近 10 篇内容（不足则最近 180 天全部）
- 采集字段：creator_id / nickname / profile_url / bio / followers / latest_post_time / posts_reviewed_count / same_category_posts_count / commercial_posts_count / commercial_post_ratio / content_categories / primary_format / main_scenes / update_frequency / observed_at / source=page_observed / human_verified=false
- 形式判定（口播 vs 字幕）经真实视频探测与关键帧视觉判定合并，存于 `stage_3_format_probe.json` 与 `stage_3_visual_verdicts.json`

## 4. 最终候选（6 位，目标 10 未达成）

评分模型 8 维度 100 分（受众 20 / 赛道 15 / 场景 15 / 视频表达 10 / 食品植入 15 / 商业自然度 10 / 可执行性 10 / 合规 5），逐项分数与依据见 `data/processed/stage_3_scores.json`，评分函数 `src/stage_3_scoring.py` 可复现。

**15 位深核候选中仅 6 位达到 85 分正式候选线。按任务书允许少于 10 位，不虚构账号补齐。**

| 排名 | 达人 | 总分 | 分级 | 形式 | 粉丝 | 主页 |
|---:|---|---:|---|---|---:|---|
| 1 | 欧盈Kelly | 95 | 重点候选 | 口播 | 278,129 | /user/profile/60bb90f00000000001002887 |
| 2 | 小季没烦恼 | 91 | 重点候选 | 字幕 | 277,674 | /user/profile/586733cd50c4b43cccffc5c8 |
| 3 | 一只牛🐮 | 90 | 重点候选 | 字幕 | 139 | /user/profile/5ad034864eacab543fa98374 |
| 4 | 小王不忙 | 88 | 正式研究候选 | 字幕 | 381 | /user/profile/63b001c0000000002600681f |
| 5 | yeline | 87 | 正式研究候选 | 口播 | 67,811 | /user/profile/61de867a000000001000ffa0 |
| 6 | 叁壹_ | 86 | 正式研究候选 | 口播 | 5,396 | /user/profile/5dd0fe8f000000000100b124 |

结构平衡核验（`stage_3_final_10.json` → structure_balance）：

| 约束 | 要求 | 实际 | 达标 |
|---|---|---|---|
| 口播/旁白型 | ≥3 | 3 | ✓ |
| 沉浸式字幕型 | ≥3 | 3 | ✓ |
| 通勤/办公室场景 | ≥2 | 2 | ✓ |
| 早餐/一人食场景 | ≥2 | 6 | ✓ |
| 健身/运动后场景 | ≥2 | 1 | ✗ |
| 单一类型占比 | ≤50% | 3/6 | ✓ |

健身场景未达标原因：健身赛道候选在预筛与深核中大量命中“减脂/掉秤”结果承诺型表达（硬淘汰或身材焦虑扣分），仅叁壹_ 以非焦虑型健身记录通过。是否追加搜索预算由项目总控决策。

## 5. 前 3 位重点候选

`data/processed/stage_3_top3.json`：**欧盈Kelly（95）/ 小季没烦恼（91）/ 一只牛🐮（90）**，均 ≥90 为重点候选。三位各完成 1 条代表视频的完整理解管线，详见 `reports/stage_3_top3_video_summary.md`。

## 6. 脚本风格研究对象：欧盈Kelly

`data/processed/stage_3_style_reference.json`，`selection_status: research_style_reference`（非商业定案，未标记 commercially_selected / confirmed_collaboration / brand_approved）。

决胜链（确定性、可复现）：食品自然植入分（13/15，Top3 最高）→ 商业自然度（9/10）→ 总分（95）。

**为什么优于其他候选**：

1. 受众匹配 20/20 满分：都市职场女性 + 独居生活形态，与轻醒目标人群完全重合；
2. 场景 14/15：一人食 + 通勤/办公室 + 下午茶三场景齐备，覆盖轻醒全部核心消费时刻；
3. 视频表达 10/10：近 10 篇视频占比 100%，实测真人口播，代表视频 153.5s 适合脚本拆解；
4. 食品植入 13/15：饮品贯穿 + 早餐/午餐/晚餐四位置天然植入点（153.5s 代表视频实测）；
5. 合规 5/5：无减肥/燃脂/医疗表达，身材焦虑扣分 0；
6. 3 条真实视频证据：1 条完整管线处理（6989ab01…）+ 2 条页面证据（6a5c556e… / 6a5616b6…），Stage 4 再做三视频深度拆解。

## 7. 最终候选代表笔记（每位 2–3 篇）

canonical URL 统一为 `https://www.xiaohongshu.com/explore/{note_id}`，不含 xsec_token。完整字段（互动量/场景/形式/食品/合规/截图路径）见 `stage_3_final_10.json`。

- **欧盈Kelly**：69df136e…（一个人开车去打匹克球 喝咖啡，video 211.1s，2026-04-15）；6989ab01…（深圳INTP独立女上班vlog，video 153.5s，2026-02-09）
- **小季没烦恼**：6a58b7ea…（晚间日记 下班后才是生活的开始，video 114.0s，2026-07-16）；6a50d6a4…（独处一人食 手鞠寿司，video 93.1s，2026-07-11）
- **一只牛🐮**：6a59b5ac…（Vlog 独居早餐，video 54.7s，2026-07-17）；6a586910…（Vlog 独居早餐，video 72.3s，2026-07-16）
- **小王不忙**：6a5c84fe…（蒜香黄油杏鲍菇，video 53.5s，2026-07-19）；6a58993b…（苹果黄瓜蟹柳沙拉，video 58.4s，2026-07-16）
- **yeline**：6a38d927…（不上班和自己出门约会一天，video 196.0s，2026-06-22）；6a1fdbe3…（归家后的治愈 卧室松弛感，video 118.3s，2026-06-03）
- **叁壹_**：69800dca…（Gym Vlog 井然有序，video 65.6s，2026-02-02）；681c9e47…（运动Vlog 高能量一天，video 138.8s，2025-05-08）

截图证据 18 张（6 主页 + 12 笔记，JPEG ≤300KB）：`screenshots/stage_3_creators/`、`screenshots/stage_3_notes/`，与 `stage_3_evidence_manifest.json` 一致。

## 8. 淘汰名单与证据

### 8.1 深核阶段硬淘汰（6 位，`stage_3_eliminated.json`）

| 达人 | 原因 |
|---|---|
| 鸡蛋妹儿 / 每天都好困 / sugarrr / 黄白胖ya / 奶茶还不困 | 最近 180 天无更新或活跃性无法核验 |
| 奥聪满壹学校 | 医疗类内容（硬性淘汰） |

### 8.2 评分淘汰（9 位，均 <85，`stage_3_scores.json` 含逐项依据）

| 达人 | 总分 | 主要失分/扣分原因 |
|---|---:|---|
| 是粥粥吖 | 77 | 场景匹配弱；身材相关表达扣分 |
| 燃崽日记 | 77 | 场景匹配弱；身材相关表达扣分 |
| 白菜张张 | 76 | bio 身高体重数字人设 + 标题“维持体重”表达，身材焦虑扣分 6 |
| 薯到叁 | 74 | 食品植入与场景证据不足 |
| 无糖小钟 | 72 | “无糖”定位靠近控糖宣称边界，场景证据不足 |
| 肉卷超好吃😋 | 64 | 受众与赛道偏离 |
| 徐个愿 | 55 | 身材焦虑扣分 8，多维度证据不足 |
| ItsDani | 50 | 场景命中 0，赛道证据不足 |
| azizi- | 44 | 孕晚期人设（受众匹配封顶 8），多维度证据不足 |

## 9. 数据缺失项（如实记录）

1. 部分候选 following / likes_and_collects 字段为 null（页面未稳定暴露，未编造）；
2. 每位候选第 2 篇代表笔记未做口播/字幕形式探测（仅第 1 篇实测），对应 `has_voiceover` / `has_on_screen_text` 记为缺失并影响证据完整度（欧盈Kelly 0.909、ItsDani 0.818 等）；
3. 小季没烦恼代表视频存在品牌植入画面/字幕证据，但主页近 10 篇无平台“商业笔记”标识，`commercial_posts_count=0` 与视频级软广判断并存，两者来源不同（page_observed vs 视频证据），报告中分别表述；
4. 叁壹_ 第 2 篇代表笔记发布于 2025-05-08，超出 180 天窗口，属“不足 10 篇时检查最近 180 天全部”规则的边界样本，已保留并标注。

## 10. 合规风险

1. 健身赛道整体高风险：预筛与深核中大量“减脂/掉秤/暴瘦”结果承诺型账号，已按硬性条件与扣分模型处理；
2. 白菜张张类“身高体重数字人设”账号：人设即建立在身材数据上，轻醒商单若合作将直接触碰食品广告功效暗示红线，已淘汰；
3. 小季没烦恼视频中“轻因”（咖啡因概念）宣称：若未来引用同类概念，需品牌方提供依据；
4. 无糖小钟类“无糖/控糖”定位账号：接近降糖宣称边界，已淘汰；
5. 最终 6 位候选在已核验内容范围内均未发现减肥/燃脂/降糖/医疗类表达。

## 11. 风格研究对象的 3 条视频证据

| 证据 | note_id | 处理深度 |
|---|---|---|
| 完整管线（下载/转写/抽帧/时间线/分析） | 6989ab01000000001a0360c5 | 已完成（Stage 3） |
| 页面证据（标题/时长/互动/截图） | 6a5c556e…（见 style_reference.json） | Stage 4 处理 |
| 页面证据（标题/时长/互动/截图） | 6a5616b6…（见 style_reference.json） | Stage 4 处理 |

---

## 阶段结论

- `stage_3_creator_pool_ready`：true（113 ≥ 20）
- `stage_3_top3_ready`：true
- `stage_3_style_reference_ready`：true（欧盈Kelly）
- `stage_3_final_10_ready`：**false**（6/10，健身场景平衡未达标）
- `status`：**blocked_by_insufficient_verified_candidates**，`current_stage` 保持 `stage_3`
- 后续路径由项目总控决策：追加搜索预算补足 10 位，或确认以 6 位真实候选进入 Stage 4
