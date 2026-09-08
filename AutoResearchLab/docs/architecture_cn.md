# MAARS 架构

[English](architecture.md) | **中文版**

MAARS 是一个四阶段自动化科研管道：从模糊想法到论文草稿，由四个 AI Agent 接力完成。

```
用户想法 -> [Idea Agent] -> [Plan Agent] -> [Task Agent] -> [Paper Agent] -> 论文草稿
```

## 后端

### 分层结构

```
main.py                         FastAPI + Socket.IO 入口

api/                            接口层
  routes/                       13 个路由模块（idea、plan、execution、paper、research、session、events 等）
  state.py                      全局会话状态管理
  session_auth.py               HMAC 签名会话认证
  realtime_emitter.py           Socket.IO -> SSE 桥接

idea_agent/                     Idea Agent — 文献收集 + 想法提炼
  agent.py + adk_runner.py      ADK Agent 模式
  llm/executor.py               LLM 单轮模式
  literature.py + arxiv.py      文献检索（OpenAlex / arXiv）
  __init__.py                   编排（关键词 -> 检索 -> 提炼）

plan_agent/                     Plan Agent — 任务分解
  agent.py + adk_runner.py      ADK Agent 模式
  llm/executor.py               LLM 单轮模式
  index.py                      编排（原子性检查 -> 递归分解 -> 格式化）
  execution_builder.py          执行图构建

task_agent/                     Task Agent — 并行执行 + 验证
  runner.py                     ExecutionRunner 核心类（零继承，~40 个代理方法）
  runner_deps.py                依赖注入容器（RunnerDeps dataclass）
  runner_retry.py               重试/attempt 纯函数
  runner_memory.py              执行记忆纯函数
  runner_scheduling.py          调度/状态/回滚函数
  runner_orchestration.py       全局编排循环
  runner_phases.py              单任务生命周期阶段
  agent.py + adk_runner.py      Docker ADK Agent 模式
  llm/executor.py               LLM 单轮模式
  llm/validation.py             三步验证（格式门控 -> 合同审查 -> 原始合同）
  pools.py                      Worker 并发池
  docker_runtime.py             Docker 容器生命周期
  artifact_resolver.py          任务间输入解析

paper_agent/                    Paper Agent — 论文草稿生成
  runner.py                     单文件（Mock / LLM 单轮 / Agent MVP 管道）

validate_agent/                 Step-B 合同审查（Task Agent 子组件）
  executor.py                   验证标准调整决策

shared/                         公共基础设施
  llm_client.py                 统一 LLM 客户端
  constants.py                  全局常量
  adk_runtime.py                Google ADK 运行时
  reflection.py                 自我反思 + 技能学习

db/                             SQLite 持久化层
visualization/                  分解树 / 执行图布局计算
```

### 每个 Agent 的三模式

所有 Agent 统一支持三种执行模式，通过 `api_config` 切换：

| 模式 | 适用场景 | 行为 |
|---|---|---|
| **Mock** | 开发/测试 | 读取 `test/mock-ai/*.json`，模拟流式输出 |
| **LLM** | 快速执行 | 单轮 LLM 调用（`shared/llm_client.py`） |
| **Agent** | 完整能力 | Google ADK 多轮 tool-use agent |

### Task Agent 内部架构

Task Agent 是最复杂的组件。`ExecutionRunner` 是一个零继承的普通类，通过薄代理方法将所有行为委托给 5 个函数模块：

```
ExecutionRunner
  |-- runner_retry.py          纯函数，接收显式状态字典
  |-- runner_memory.py         纯函数，接收状态字典 + dep 回调
  |-- runner_scheduling.py     纯函数 + runner 实例函数
  |-- runner_orchestration.py  runner 实例函数
  |-- runner_phases.py         runner 实例函数
```

**单个任务的生命周期：**

```
Phase 1: 获取 Worker Slot
  |
Phase 2: 执行（Docker ADK Agent 或 LLM 单轮）
  |
Phase 3: 三步验证
  Step A: 结构格式门控（输出是否可解析？）
  Step B: 合同审查（验证标准是否需要调整？）
  Step C: 原始合同验证（LLM 判断输出质量）
  |
Phase 4: 反思（可选，生成可复用技能）
  |
Phase 5: 完成（释放 Worker，调度下游任务）
  |  （验证失败时）
  +-> retry_or_fail -> 回到 Phase 1（最多 5 次）
```

**依赖注入：** `RunnerDeps` 是一个包含 25+ 个可注入 callable 的 dataclass。生产环境使用 `build_default_deps()`；测试直接传 `RunnerDeps(xxx=fake)`。

## 前端

原生 JavaScript + HTML + CSS，零外部依赖（仅通过 CDN 加载 highlight.js）。

```
js/
  core/           基础设施（配置、状态、工具函数）
  api/            API 客户端（基于 fetch，会话感知）
  ws/             SSE 连接 + maars:* 事件分发
  flows/          业务流程控制器（idea、plan、task、paper、research）
  regions/        内容渲染区域（输出、thinking 流、任务树 SVG）
  ui/             UI 组件（设置弹窗、侧边栏、toast、主题）

css/
  core/           设计 token、reset、主题调色板（浅色/深色/纯黑）
  layout/         页面结构
  components/     通用组件（按钮、弹窗、toast、markdown）
  regions/        内容区域样式
  ui/             UI 组件样式
```

**数据流：**

```
用户操作 -> js/flows/ -> js/api/ -> HTTP POST -> 后端
后端处理 -> SSE 推送 -> js/ws/websocket.js -> document.dispatchEvent('maars:*')
js/flows/ 监听 maars:* -> 更新状态 -> js/regions/ 渲染 UI
```

## 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 后端框架 | FastAPI + asyncio | 异步 I/O 适合并行任务执行 |
| 实时通信 | SSE（替代 Socket.IO） | 单向推送够用，更轻量 |
| Agent 框架 | Google ADK | 原生 tool-use，多轮对话 |
| 前端框架 | 无（vanilla JS） | 零依赖，直接服务静态文件 |
| 样式方案 | 模块化 CSS + CSS Variables | 无构建步骤，支持多主题 |
| 依赖注入 | RunnerDeps dataclass | 测试直接注入 fake，无 monkeypatch |
| 持久化 | SQLite | 本地优先，零配置 |
| 认证 | HMAC 签名 session + HttpOnly cookie | SSE 不支持 header，cookie 自动携带 |
