# Stage 2 达人采集与筛选工具选型调研报告

- 调研日期：2026-07-17
- 调研人：项目总控
- 状态：调研结论已定，组件**未安装、未通过准入评审**，正式审查在 Stage 2 执行
- 关联决策：project/decision_log.md D-0003
- 关联登记：registry/component_candidates.csv（CAND-001 ~ CAND-004）

## 结论

**有接近可用的 Skill/MCP，但没有成熟工具能直接完成"根据品牌 Brief 自动找出 10 位最匹配达人并给出可靠评分"。**

最合适的做法是：

> `xiaohongshu-mcp` 负责搜索与读取公开数据，自研 `xhs-benchmark-finder` Skill 负责关键词扩展、达人筛选、风格分析和评分。

`xiaohongshu-mcp` 已支持关键词搜索、笔记详情、互动数据、评论和用户主页信息，能够提供昵称、简介、粉丝量、获赞量及公开笔记列表，基本覆盖本题的资料采集需求。

## 三个实现方向

| 方向 | 方案 | 评分 | 结论 |
| -- | -- | --: | -- |
| A | `xiaohongshu-mcp`＋自研对标达人Skill | 95 | 推荐 |
| B | `xhs-cli`＋自研对标达人Skill | 92 | 备选 |
| C | 通用Browser MCP＋网页操作Prompt | 86 | 仅兜底 |

### 方向A：xiaohongshu-mcp＋自研Skill

能完成：

- 根据关键词搜索小红书笔记；
- 获取搜索结果中的作者；
- 获取笔记标题、正文、图片及互动数据；
- 获取作者主页、粉丝量和公开笔记；
- 收集每位达人的 2—3 条代表内容；
- 将数据传给 AI 进行风格分析和匹配评分。

为什么得分最高：不是通用浏览器自动化，而是已封装小红书相关工具，输入输出更稳定，更容易接入 Claude Code、Cursor 等支持 MCP 的执行环境；项目提供登录检查、搜索、笔记详情和用户主页等接口。

### 方向B：xhs-cli＋自研Skill

`xhs-cli` 自带 `SKILL.md`，通过无头浏览器完成搜索笔记、读取帖子、浏览用户主页等操作，适合作为 Claude Code 中的直接 Skill。使用浏览器而非逆向 API，速度较慢，但作者定位为更能适应风险控制变化的方式。

适用情况：MCP 部署失败；希望通过 CLI 直接执行；执行 AI 主要在终端环境工作；希望调用命令后返回 JSON。

### 方向C：Browser MCP

Browser MCP 可控制已有本地浏览器并使用现有登录状态，适合读取小红书网页和截图。但需要 AI 自己识别页面结构，易受页面改版、元素加载延迟、无限滚动、登录弹窗、风控验证影响，不适合作为主方案。

## 最终架构

```text
品牌Brief结构化
        ↓
搜索策略生成Skill
        ↓
xiaohongshu-mcp
        ↓
关键词搜索笔记
        ↓
提取作者与公开主页
        ↓
获取近期代表内容
        ↓
xhs-benchmark-finder Skill
        ↓
去重、初筛、画像、评分
        ↓
生成15位候选
        ↓
人工确认真实性
        ↓
输出最终10位达人
```

## 自研 Skill 规划（Stage 2 执行，当前不开发）

建议新增：`skills/xhs-benchmark-finder/SKILL.md`。不负责直接操作浏览器，而是编排小红书 MCP 并完成业务判断。

### 输入示例

```yaml
brand_brief:
  product: 0蔗糖高蛋白希腊酸奶
  audience:
    - 22-35岁城市女性
    - 健身
    - 轻食
    - 上班族
  scenarios:
    - 早餐
    - 运动后
    - 下午茶
  prohibited_claims:
    - 减肥
    - 降糖
```

### 执行流程

1. **生成搜索词**：多组场景关键词，如：上班族早餐、健身女孩饮食、运动后加餐、办公室下午茶、控糖饮食记录、轻食一日三餐、都市女性Vlog、高蛋白早餐、一人食、打工人冰箱常备。
2. **搜索笔记**：每词 10—20 条，总原始笔记 100—150 条，设置请求间隔，不点赞/评论/收藏。
3. **提取候选作者**：去重后保留昵称、用户ID、主页链接、粉丝数、简介、笔记标题、互动数据、搜索来源关键词。
4. **初步排除**：品牌官方号、纯店铺号、搬运号、长期停更账号、内容与目标用户明显不符、广告占比极高、主要内容为医疗或疾病建议、主页资料不足。
5. **深度读取**：对初筛后 20—30 位达人获取主页与近期笔记，选 2—3 条代表内容，记录标题、场景、互动量、内容形式，识别相似食品商单。
6. **自动评分**：

   | 维度 | 权重 |
   | -- | --: |
   | 目标人群匹配 | 25 |
   | 内容赛道匹配 | 20 |
   | 使用场景匹配 | 15 |
   | 表达风格匹配 | 15 |
   | 商单自然度 | 10 |
   | 拍摄可执行性 | 10 |
   | 合规风险 | 5 |

7. **输出候选名单**：AI 先输出 15 位，人工核查主页真实性、链接可达性、粉丝数据、代表内容、竞品合作、品牌适配后，保留最终 10 位。

### 输出数据结构

```json
{
  "creator_name": "",
  "profile_url": "",
  "user_id": "",
  "followers": 0,
  "bio": "",
  "content_categories": [],
  "audience_inference": {
    "gender": "",
    "age_range": "",
    "interests": [],
    "evidence": []
  },
  "representative_posts": [
    {
      "title": "",
      "url": "",
      "publish_time": "",
      "likes": 0,
      "collects": 0,
      "comments": 0,
      "content_structure": [],
      "brand_integration_style": ""
    }
  ],
  "scores": {
    "audience_fit": 0,
    "content_fit": 0,
    "scenario_fit": 0,
    "style_fit": 0,
    "commercial_naturalness": 0,
    "shootability": 0,
    "compliance": 0,
    "total": 0
  },
  "recommendation_reason": "",
  "risk_notes": [],
  "human_verified": false
}
```

## 必须保留人工门禁

不能设计为完全无人值守。`xiaohongshu-mcp` 需要登录，同一账号网页端多处登录可能导致当前会话退出；项目要求遵守平台规则。

主流程：`AI自动采集 → AI初步评分 → 人工确认链接和内容 → 才能进入达人风格拆解`。

AI 禁止自动执行：点赞、收藏、评论、私信、批量关注、高频无限抓取、绕过验证码、采集非公开个人信息。

## 候选组件登记决定

现阶段不安装（Stage 1 仍在做 Brief 结构化）。登记为 Stage 2 候选：

| 组件 | 准入状态 | 初评分 |
| -- | -- | --: |
| `xpzouying/xiaohongshu-mcp` | 待安全和许可证审查 | 95 |
| `jackwener/xhs-cli` | 备选 | 92 |
| `ibreez3/xiaohongshu-skill` | 方法参考 | 89 |
| Browser MCP（`BrowserMCP/mcp`） | 兜底工具 | 86 |

其中 `ibreez3/xiaohongshu-skill` 已封装搜索、笔记详情和用户主页等功能，但整体偏向内容发布自动化，可借鉴其 Skill 组织方式，不建议直接作为本项目核心业务 Skill。

**最终选型：`xiaohongshu-mcp` 作为采集工具，自研 `xhs-benchmark-finder` 作为业务 Skill。综合评分 95 分。**

## 来源链接

- https://github.com/xpzouying/xiaohongshu-mcp
- https://github.com/jackwener/xhs-cli/blob/main/SKILL.md
- https://github.com/BrowserMCP/mcp
- https://github.com/ibreez3/xiaohongshu-skill
