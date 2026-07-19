"""Agent 节点包：每个节点一个模块，模块级 docstring 即输入输出契约。

节点分为两类：
- 可运行演示（基于本地真实数据/策略文件，无 LLM、无网络）：
  brief_analyzer、creator_style_distiller、fact_regression、compliance_reviewer、
  human_approval；
- stub（raise NotImplementedError，正式实现依赖 LLM / Skill / 外部凭据）：
  script_generator、humanizer、storyboard_generator、feishu_publisher。

所有节点函数签名统一为 ``run(state: AgentState) -> dict | None``，
返回值由图引擎合并进状态；节点不得写入流程控制字段
（retry_count/status/history/errors/last_failure）。
"""
