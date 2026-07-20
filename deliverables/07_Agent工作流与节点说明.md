# Agent工作流与节点说明

流程：Brief Analyzer → Creator Style Distiller → Script Generator → Humanizer → Fact Regression → Compliance Reviewer → Storyboard Generator → Human Approval → Feishu Publisher。

| 节点 | 输入/输出 | 失败与回退 | 人工位置 |
| --- | --- | --- | --- |
| Brief Analyzer | 品牌 Brief → 结构化证据 | 证据缺失则阻断卖点断言 | 品牌资料确认 |
| Style Distiller | 真实视频证据 → 风格规则 | 无证据不生成模仿性结论 | 风格边界审核 |
| Script/Humanizer | 规则与草稿 → 口播稿 | Humanizer 后必须事实回归 | 文案确认 |
| Compliance | 脚本/字幕/CTA → 风险报告 | 违规退回脚本 | 品牌/法务审批 |
| Storyboard | 通过的脚本 → 分镜 | 时长或合规不一致退回 | 拍摄审核 |
| Feishu Publisher | 已批准内容 → 发布接口 | 未获人工批准不得发布 | 最终人工门禁 |

当前为纯 Python 最小可运行原型；LangGraph 仅为高星框架参考。未发现真实自动写入记录，因此不得声称已完成飞书自动发布。
