# Learn_LLM · Multi-Agent Research Control Tower

一个面向科研场景的多智能体工作流项目。项目以
[AutoResearchLab](./AutoResearchLab) 为核心，将模糊研究主题推进为可审查的论文草稿，
并将“谁负责、何时推进、产物从何而来、失败如何恢复”显式呈现在控制台中。

> 当前重点：**控制面驱动的多 Agent 协作、可验证任务 DAG、证据可追溯与异步任务解耦。**

## 架构概览

```text
                         Research Director（控制面）
                                      │
用户主题 → Refine → Plan → Execute → Paper → Quality Review
             文献证据    任务 DAG    实验产物    论文草稿     修订决策
```

- **顺序阶段流**：`Refine → Plan → Execute → Paper`，避免在研究问题未澄清前直接生成论文。
- **阶段内 DAG**：Plan 将研究目标拆为原子任务；Execute 仅在依赖任务产物准备后运行。
- **Research Director**：只读控制面，基于持久化产物执行质量门和下一阶段委派，而非由单个 Agent 隐式决定流程。
- **Evidence Lineage**：文献、计划、任务输出、论文草稿与审查报告均可关联追溯。
- **故障恢复**：SQLite/文件产物是长期事实源；Redis 保存短期上下文与幂等键，RabbitMQ 承担耗时阶段任务的投递与重试。

## 核心能力

| 模块 | 职责 | 主要产物 |
| --- | --- | --- |
| Refine Agent | 提取关键词、检索和筛选文献、收敛研究问题 | `keywords`、`papers`、`refined_idea` |
| Plan Agent | 将研究问题分解为具备依赖关系和验收标准的原子任务 | 任务 DAG、输入/输出合同、验证条件 |
| Task Agent | 在隔离环境中执行任务、生成代码/分析/图表并验证结果 | Task artifact、日志、验证报告 |
| Paper Agent | 汇总已验证产物，生成 Markdown/LaTeX 论文草稿 | `paper_draft` |
| Paper Review Skill | 审查 claim、引用、方法与可复现性 | 结构化审查报告、blocker、修订建议 |

## 技术栈

`FastAPI` · `Socket.IO / SSE` · `Google ADK` · `Docker` · `SQLite` · `Redis` · `RabbitMQ` · `OpenAlex / arXiv` · `Python`

## 快速开始

```powershell
Set-Location AutoResearchLab
Copy-Item .env.example .env
docker compose up --build
```

打开 <http://localhost:3001>。

如需启动 Redis、RabbitMQ 与各阶段常驻 Worker 的异步模式：

```powershell
docker compose -f compose.yaml -f compose.async.yaml up -d --build
```

- 应用控制台：<http://localhost:3001>
- RabbitMQ 管理台：<http://localhost:15672>

API Key 只应填写在本地、已被 Git 忽略的 `.env` 中，不能提交到仓库。

## 面试演示路径

1. 创建一个研究主题，展示 `Refine → Plan → Execute → Paper` 的阶段推进。
2. 在 Research Detail 中展示 Control Tower：Agent Organization、Task Contracts、Quality Gates 与 Evidence Lineage。
3. 解释：大阶段顺序执行；DAG 只描述 Execute 内原子任务的依赖与可并行关系。
4. 展示预算策略、Token 消耗、失败快照，以及从失败阶段恢复而非全量重跑的能力。
5. 说明异步边界：RabbitMQ 传轻量命令，Redis 管短期上下文/幂等，SQLite 与产物文件保存长期事实。

## 文档

- [项目运行说明](./AutoResearchLab/README.md)
- [中文架构说明](./AutoResearchLab/docs/architecture_cn.md)
- [Redis + RabbitMQ 异步运行手册](./AutoResearchLab/docs/REDIS_RABBITMQ_RUNBOOK_CN.md)
- [Control Tower 演示说明](./AutoResearchLab/docs/CONTROL_TOWER_DEMO.md)
