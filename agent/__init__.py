"""小红书 MCN 商单脚本 Agent 编排包（轻醒案例）。

包含：工作流状态（state）、节点契约（schemas）、最小可运行图（graph）、
节点实现（nodes/，规则类为可运行演示、LLM/外部系统类为 stub）、
策略文件（policies/）。不依赖 langgraph、不含任何模型调用与真实凭据。

打包与迁移说明见 ``reports/agent_packaging_guide.md``。
"""

__version__ = "0.1.0"
