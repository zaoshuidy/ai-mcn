# 组件准入审查报告：CAND-017 langgraph（参考组件）

- 核实日期：**2026-07-19**（证据为当日经 GitHub REST API 实时抓取，见 `evidence/` 内 `fetched_at` / `reverify_at` 时间戳）
- 评审结论：**reference_only（编排框架方法论参考，非 approved 执行组件；是否作为运行时依赖引入须另行评审）**
- 证据目录：`reports/component_reviews/evidence/`

---

## 1. 基本信息（来源核验）

| 项目 | 值 | 证据 |
| --- | --- | --- |
| 仓库 | https://github.com/langchain-ai/langgraph | evidence/langchain-ai__langgraph__meta.json |
| Owner | langchain-ai（GitHub Organization，LangChain, Inc.） | 同上；evidence/langchain-ai__langgraph__reverify.json |
| 默认分支 | `main` | 同上 |
| 固定 commit | `49ae27c2ae983cfb92091b0dea9f7bc37a716479`（main 最新提交，commit date 2026-07-15T07:55:09Z） | 同上（latest_commit_sha，经 /commits?per_page=1 核验；2026-07-19 复核一致） |
| Star | 37596 | 同上（2026-07-19 复核仍为 37596） |
| 最近推送 | 2026-07-19T00:50:04Z（pushed_at；当日仍有推送，维护极活跃） | 同上 |

## 2. 用途定位

- 申请用途：Agent 状态编排、失败回退、Human-in-the-loop 机制参考（orchestration_framework）
- 本项目仅参考其有向图状态机、节点/边、断点续跑、人工介入等编排范式，用于设计 MCN 商单脚本 Agent 的多阶段流水线（Stage 1 需求解析 → Stage 2 采集 → Stage 3 评分 → 脚本生成）。
- **当前不引入其代码，也未加入 requirements.txt；如未来作为 pip 运行时依赖引入，须另行发起执行组件准入评审。**

## 3. License 结论

- **MIT（已核实）**：GitHub API `license.spdx_id = "MIT"`（meta.json）；
- `/license` 端点 200，LICENSE 文件存在（2026-07-19 复核 reverify.json：`license_endpoint_http = 200`、`license_file_spdx = "MIT"`）。
- 声称 MIT 与核验结果一致。

## 4. 安全结论

- 作为纯参考组件当前不执行、不安装，无直接攻击面。
- 风险点：若日后引入为运行时依赖，将带入 langchain 生态较重的依赖树，供应链面随之扩大；框架迭代快，API 稳定性需关注。
- 缓解：当前仅登记为方法论/API 思路参考；引入运行时依赖前必须重新评审（含依赖树与供应链审查）。

## 5. 使用限制

1. 当前仅方法论与 API 思路参考，禁止复制其源码进本仓库；
2. 任何 pip 依赖引入（含间接引入）须另行完成执行组件准入评审；
3. 自研编排实现时仅借鉴范式（状态图、节点、断点、人工介入），不照搬其内部实现。

## 6. 替代方案

- 自研轻量状态机：本项目 Stage 流水线为线性为主、分支有限的场景，自研成本低；
- 其他编排范式参考：Airflow DAG、Prefect 等工作流概念（均为公共方法论）。

## 7. 准入定位

**reference_only。** 登记于 registry/component_candidates.csv 与 registry/THIRD_PARTY_NOTICES.md；不进入 approved_components.yaml，不进入 requirements.txt。

## 8. 证据链接

- GitHub 仓库：https://github.com/langchain-ai/langgraph
- 本地证据：evidence/langchain-ai__langgraph__meta.json（2026-07-19 首次抓取）、evidence/langchain-ai__langgraph__reverify.json（2026-07-19 复核：MIT、commit SHA 一致、pushed_at 当日）
