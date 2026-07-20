# 五个Skill使用说明

正确顺序：creator-style-distiller → xhs-commercial-script → xhs-script-humanizer → Fact Regression → xhs-food-ad-compliance → xhs-storyboard-generator。Humanizer 不是最终节点。

| Skill | 目录 | 作用与边界 |
| --- | --- | --- |
| creator-style-distiller | `skills/creator-style-distiller/` | 解决对应阶段的结构化输入、生成或审核问题；保留人工审批边界 |
| xhs-commercial-script | `skills/xhs-commercial-script/` | 解决对应阶段的结构化输入、生成或审核问题；保留人工审批边界 |
| xhs-script-humanizer | `skills/xhs-script-humanizer/` | 解决对应阶段的结构化输入、生成或审核问题；保留人工审批边界 |
| xhs-storyboard-generator | `skills/xhs-storyboard-generator/` | 解决对应阶段的结构化输入、生成或审核问题；保留人工审批边界 |
| xhs-food-ad-compliance | `skills/xhs-food-ad-compliance/` | 解决对应阶段的结构化输入、生成或审核问题；保留人工审批边界 |

每个 Skill 均以结构化输入输出、校验器和示例/eval 为边界：风格 Skill 只提取高层规则；脚本 Skill 不虚构品牌事实；Humanizer 后回归事实；合规 Skill 拦截食品广告风险；分镜 Skill 只消费已审核脚本。具体触发、输入、输出和 eval 以各目录 `SKILL.md` 与现有测试为准。
