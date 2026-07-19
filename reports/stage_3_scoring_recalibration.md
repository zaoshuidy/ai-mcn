# Stage 3 评分校准报告（v1 → v2）

- 日期：2026-07-19
- 背景：项目总控复评指出 v1 旧 8 维评分模型未纳入粉丝量级与近期互动质量（139 粉丝账号「一只牛🐮」获 90 分进入 Top3），Stage 3 不放行，要求以 10 维 v2 模型重评分并定向补足候选。
- 数据文件：`data/processed/stage_3_scores_v2.json`（24 位 v2 评分）、`data/processed/stage_3_final_candidates_v2.json`、`data/processed/stage_3_top3_v2.json`、`data/processed/stage_3_style_reference_v2.json`、`data/processed/stage_3_prefiltered_gapfill.json`、`data/processed/stage_3_eliminated.json`；v1 存档 `data/processed/stage_3_scores.json` 已标记 superseded，仅供追溯。
- 评分实现：`src/stage_3_scoring_v2.py`；执行脚本：`scripts/run_stage_3_rescore_v2.py`。

## 1. v1 → v2 模型变化

v1（`src/stage_3_scoring.py`，8 维）与 v2（`src/stage_3_scoring_v2.py`，10 维）权重对照：

| 维度 | v1 权重 | v2 权重 | 变化 |
| -- | -- | -- | -- |
| 目标受众匹配 target_audience | 20 | 18 | -2 |
| 内容赛道匹配 content_track | 15 | 13 | -2 |
| 场景匹配 scene_match | 15 | 12 | -3 |
| 视频表达能力 video_expression | 10 | 10 | 不变 |
| 食品自然植入能力 food_integration | 15 | 13 | -2 |
| 商业内容自然度 commercial_naturalness | 10 | 8 | -2 |
| 拍摄与脚本可执行性 executability | 10 | 8 | -2 |
| 合规安全 compliance | 5 | 5 | 不变 |
| 粉丝量级适配 follower_scale_fit | — | 7 | 新增 |
| 近期互动质量 engagement_quality | — | 6 | 新增 |
| 合计 | 100 | 100 | 旧 8 维压缩 13 分让位于新 2 维 |

## 2. 粉丝量级规则（follower_scale_fit，7 分）

- 粉丝不是越多越好；品牌预算未确认，**量级分上限 5/7**（`FOLLOWER_SCALE_FIT_CAP = 5`），任何量级档位均不给满 7 分。
- 分档给分：under_1k → 2；1k_to_10k → 4；10k_to_100k → 5；100k_to_500k → 5；over_500k → 3；unknown → 2（保守给分）。
- **under_1k 硬规则**：粉丝 <1000 的账号标记 `selection_tier=koc_seed_candidate`，**总分封顶 84**，评级不得为「重点候选/正式研究候选」（强制降级为「仅风格参考」），不得进入 Top3。Top3 粉丝下限 `TOP3_MIN_FOLLOWERS = 1000`。
- 实例：一只牛🐮（139 粉丝）v2 raw 80，未触发 84 封顶线，但因 under_1k 被标记 koc_seed_candidate 并降级为「仅风格参考」，v1 的 Top3 身份作废。

## 3. 互动质量口径（engagement_quality，6 分）

- 数据源：每位候选最近 10 篇笔记的 page_observed 点赞/收藏/评论（`data/processed/stage_3_engagement_15.json`，24 位 × 10 篇 = 240 篇互动数据）。
- `median_total_engagement`：最近 10 篇互动总量（赞+藏+评）中位数。
- `median_engagement_rate = median_total_engagement / followers`：**仅用于本候选池内部相对比较，不是平台官方互动率**，不得根据点赞反推粉丝数。
- `viral_dependency_ratio = highest_post_engagement / median_total_engagement`：爆款依赖度；≤5 视为互动稳定（+1），>5 标注单篇爆款驱动风险。
- 商业内容互动对照：`organic_post_median_engagement` 与 `commercial_post_median_engagement` 分离计算。

## 4. 商业统计修正

- v1 问题：以「平台标识商业笔记 = 0」直接得出「内容自然」结论，混淆了证据来源。
- v2 修正（`commercial_breakdown`）：
  - `platform_labeled_commercial_posts`（来源 `page_observed`，页面实际观察到的平台商单标识）；
  - `ai_inferred_commercial_posts`（来源 `ai_inferred`，AI 软广信号判断）；
  - 两者**分离统计、不得混为同一证据来源**；`total_commercial_signals` 为两者之和。
- 评分口径：`platform_labeled = 0 且 ai_inferred = 0` 时表述为「近10篇无平台标识商单且无AI识别软广信号，内容自然」（基准 6/8），**不得再说「商业笔记 0 因此自然」**；有商业信号时以商业/自然内容互动对照定档（8/6/4）。
- 实例：欧盈Kelly 平台标识 0 条（page_observed）、AI 识别软广 1 条（ai_inferred），商业内容中位互动 3296 略低于自然内容 4332，商业自然度 6/8。

## 5. 15 位重评分前后对照（v1 总分 → v2 总分）

| 昵称 | 粉丝 | v1 总分 | v2 raw | 身材焦虑扣分 | 量级分 | 互动质量分 | 封顶/降级 | v2 总分 | 变化 |
| -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| 欧盈Kelly | 278,129 | 95 | 93 | 0 | 5/7 | 5/6 | — | 93 | -2 |
| 小季没烦恼 | 277,674 | 91 | 85 | 0 | 5/7 | 4/6 | — | 85 | -6 |
| yeline | 67,811 | 87 | 84 | 0 | 5/7 | 3/6 | — | 84 | -3 |
| 叁壹_ | 5,396 | 86 | 83 | 0 | 4/7 | 2/6 | — | 83 | -3 |
| 一只牛🐮 | 139 | 90 | 80 | 0 | 2/7 | 3/6 | under_1k→koc_seed_candidate，降级仅风格参考 | 80 | -10 |
| 白菜张张 | 77,724 | 76 | 84 | 6 | 5/7 | 4/6 | — | 78 | +2 |
| 小王不忙 | 381 | 88 | 78 | 0 | 2/7 | 2/6 | under_1k→koc_seed_candidate | 78 | -10 |
| 燃崽日记 | 85,076 | 77 | 78 | 3 | 5/7 | 4/6 | — | 75 | -2 |
| 无糖小钟 | 66,202 | 72 | 67 | 0 | 5/7 | 4/6 | — | 67 | -5 |
| 薯到叁 | 49,033 | 74 | 68 | 3 | 5/7 | 6/6 | — | 65 | -9 |
| 是粥粥吖 | 921 | 77 | 64 | 0 | 2/7 | 4/6 | under_1k→koc_seed_candidate | 64 | -13 |
| 肉卷超好吃😋 | 10,248 | 64 | 58 | 0 | 5/7 | 5/6 | — | 58 | -6 |
| ItsDani | 57,962 | 50 | 57 | 0 | 5/7 | 4/6 | — | 57 | +7 |
| 徐个愿 | 43,235 | 55 | 61 | 8 | 5/7 | 2/6 | — | 53 | -2 |
| azizi- | 579 | 44 | 49 | 3 | 2/7 | 3/6 | under_1k→koc_seed_candidate | 46 | +2 |

要点：v1 Top3 全部下降——欧盈Kelly 95→93（仍为唯一 ≥90）、小季没烦恼 91→85、一只牛🐮 90→80（139 粉丝账号量级与互动短板显性化）；小王不忙 88→78、是粥粥吖 77→64 同为 under_1k 量级修正。

## 6. 补足过程（gapfill）

- 来源：原 8 关键词搜索 113 位真实原始候选、预筛 30 位中未深核者，定向补足 20 位（`data/processed/stage_3_prefiltered_gapfill.json`，生成于 2026-07-19T14:03:14Z）。关键词分布：沉浸式一人食vlog 5、独居女生早餐vlog 4、健身女生运动后加餐vlog 4、上班族女生晨间vlog 3、通勤女生早餐vlog 2、办公室下午茶vlog 1、都市女生生活vlog 1。
- 新淘汰 4 位（均因 `inactive_180d_or_unverifiable`，180 天未更新或无法核验）：小藤日紀、碳水小姨妈、肉桂冰美、小橘日记（已并入 `data/processed/stage_3_eliminated.json`，淘汰总数 10 位）。
- 新深核 9 位（完成主页深核 + 最近 10 篇互动采集，纳入 v2 评分）：屁屁一人食（79）、卷一卷（78）、is_爽姨（71）、蛋崽（70）、00饱（63）、小小羚.（62）、极个别同志（55）、16楼（53）、Ggui呀（49）——全部 <85，无人进入候选。
- gapfill 其余 7 位未深核：欣晴做饭记、念念喵呜、加辣土豆饼、爱吃火锅的妮妮、盐西不早、魔都打工媛、Ni 莫愁（资源集中于高潜候选，未进入深核，无评分，不虚构）。
- 深核规模由 15 位补足至 24 位；互动数据 24 × 10 = 240 篇；同期完成 6 个参考类组件登记 CAND-012~017（reference_only，见 `registry/component_candidates.csv` 与 `registry/THIRD_PARTY_NOTICES.md`）。

## 7. 最终结论

- 24 位 v2 评分：**≥85 仅 2 位**（欧盈Kelly 93、小季没烦恼 85）；**≥90 仅 1 位**（欧盈Kelly 93）。
- Top3 门槛（v2 总分 ≥90 且 followers ≥1000、非单篇爆款驱动）仅 1 位达标，`data/processed/stage_3_top3_v2.json` 只列 1 位并附 `below_threshold_top_scores`（小季没烦恼 85、yeline 84、叁壹_ 83）。**Top3 无法按门槛凑满 3 位，不虚构、不降级纳入低分账号**，差额如实记录，放行与否由项目总控决策。
- 风格研究对象恢复为欧盈Kelly（`data/processed/stage_3_style_reference_v2.json`，selection_status=research_style_reference，仅用于脚本风格研究，非商业定案）。
- 结构平衡缺口（在 ≥85 的 2 位候选中）：口播 1/3、字幕 1/3、健身 0/2、通勤 1/2（仅早餐/一人食 2/2 达标；`structure_balance.all_met=false`）。
- `stage_3_final_10_ready=false`（v2 后真实达标候选 2/10，不虚构补齐）、`stage_3_top3_ready=false`、`stage_3_style_reference_ready=true`。

## 8. 未解决问题与总控决策点

1. Top3 门槛缺口：是否接受 1 位达标结果、放宽门槛，或追加搜索预算继续补足？（不建议降低门槛纳入低分账号。）
2. 最终 10 位定案缺口：v2 后 ≥85 真实候选仅 2/10，是否追加搜索预算，或确认以小规模真实候选推进？
3. 结构平衡缺口（健身 0、字幕 1、口播 1）：若追加搜索，建议定向补足健身场景与字幕型候选。
4. 风格研究对象已恢复为欧盈Kelly，Stage 4 三视频风格拆解是否先行启动，待总控放行。
5. 全部候选 `human_verified=false`，商业合作定案未做（Stage 3 仅产出研究候选，边界不变）。
