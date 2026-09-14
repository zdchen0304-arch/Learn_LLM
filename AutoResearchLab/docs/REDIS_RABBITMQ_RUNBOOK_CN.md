# Redis + RabbitMQ 异步研究运行手册

本手册用于启动 AutoResearchLab 的异步运行环境：FastAPI、Redis 和
RabbitMQ。Redis 保存短期上下文和幂等键，RabbitMQ 负责耗时任务投递，
SQLite 与 `artifacts` 仍保存最终研究状态和产物。

## 0. 前置检查

1. 打开 Docker Desktop，确认左下角 Engine 正常运行。
2. 打开 PowerShell，进入项目根目录：

```powershell
cd C:\Users\CHEN\Documents\ChatGPT\Github\Learn_LLM\AutoResearchLab
```

3. 如 `docker ps` 提示 Windows named pipe 权限不足，请用“管理员身份”打开
   PowerShell 后重试。

```powershell
docker version
```

看到 `Server` 版本信息即表示 Docker CLI 已连上 Docker Engine。

## 1. 启动服务

首次运行会下载 Redis 和 RabbitMQ 镜像，并构建 API 镜像：

```powershell
docker compose -f compose.yaml -f compose.async.yaml up --build -d
```

之后代码未变更时使用更快的启动命令：

```powershell
docker compose -f compose.yaml -f compose.async.yaml up -d
```

检查全部服务：

```powershell
docker compose -f compose.yaml -f compose.async.yaml ps
```

预期看到以下三个服务均为 `healthy`：

| 服务 | 默认端口 | 职责 |
|---|---:|---|
| `maars-api` | 3001 | Web API 与研究流程 |
| `redis` | 6379 | 上下文快照、幂等键 |
| `rabbitmq` | 5672 | 异步任务消息队列 |

RabbitMQ 管理后台地址为 <http://localhost:15672>。本地默认账号密码为
`maars` / `change-me-locally`；仅用于本机开发，部署前必须改为自己的强密码。

## 2. 确认异步能力已连通

浏览器打开 <http://localhost:3001>，或使用 PowerShell 调用健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:3001/healthz
```

应返回：

```json
{"status":"ok"}
```

应用接口需要会话凭证。下面命令会创建会话并检查 Redis/RabbitMQ：

```powershell
$session = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:3001/api/session/init"
$headers = @{
  "X-MAARS-SESSION-ID" = $session.sessionId
  "X-MAARS-SESSION-TOKEN" = $session.sessionToken
}
Invoke-RestMethod "http://127.0.0.1:3001/api/async-runtime/status" -Headers $headers
```

预期结果：

```json
{
  "ready": true,
  "context": {"backend": "redis", "ready": true},
  "broker": {"backend": "rabbitmq", "ready": true}
}
```

## 3. 创建研究并投递异步任务

先创建一条研究记录：

```powershell
$research = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:3001/api/research" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body '{"prompt":"比较 RAG 与 Agentic RAG 的可复现实验设计"}'

$researchId = $research.researchId
$researchId
```

投递一个阶段任务。可用阶段为：`refine`、`plan`、`execute`、`paper`、`review`。

```powershell
$body = @{
  stage = "refine"
  idempotencyKey = "${researchId}:refine:v1"
  maxAttempts = 3
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:3001/api/research/$researchId/async-tasks" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

成功时返回 `202` 和 `task.contextRef`。消息中只有上下文引用与产物引用，完整
研究上下文保存在 Redis，不会被塞进 RabbitMQ。

查看任务状态：

```powershell
Invoke-RestMethod `
  "http://127.0.0.1:3001/api/research/$researchId/async-tasks" `
  -Headers $headers
```

## 4. 启动 Worker

另开一个 PowerShell 窗口，仍在项目根目录执行。下面命令启动 Refine Worker：

```powershell
docker compose -f compose.yaml -f compose.async.yaml exec maars-api sh -lc `
  'MAARS_ASYNC_HANDLER=async_runtime.worker_adapters:refine python -m async_runtime.worker --stage refine'
```

其他阶段仅替换最后两处阶段名称：

```text
plan    -> async_runtime.worker_adapters:plan    / --stage plan
execute -> async_runtime.worker_adapters:execute / --stage execute
paper   -> async_runtime.worker_adapters:paper   / --stage paper
review  -> async_runtime.worker_adapters:review  / --stage review
```

Worker 会从 RabbitMQ 取得消息，再从 Redis 读取 `contextRef`，并从 SQLite/
artifacts 重新加载真实研究状态。按 `Ctrl+C` 可停止当前 Worker；消息和已完成
产物不会因此被删除。

> 推荐按阶段启动：先完成 `refine`，再投递/启动 `plan`，然后依次执行
> `execute`、`paper`、`review`。这样便于观察质量门和失败恢复。

## 5. 真实基础设施自检

此测试不会调用模型 API、不会运行 Docker 沙盒实验；它只验证 Redis 写入、
RabbitMQ 发布/消费、SQLite 状态更新和清理：

```powershell
docker compose -f compose.yaml -f compose.async.yaml exec -T maars-api `
  pytest tests/cross_agent/integration/test_real_async_runtime.py -q
```

预期：`1 passed`。

## 6. 常见问题

### Docker CLI 提示 `Access is denied`

使用“管理员身份”启动 PowerShell，再运行 `docker version`。Docker Desktop 已启动
但当前 Windows 用户无 Docker named pipe 权限时会出现此问题。

### `/api/async-runtime/status` 返回 `ready: false`

先运行：

```powershell
docker compose -f compose.yaml -f compose.async.yaml ps
```

确认 `redis` 与 `rabbitmq` 都是 `healthy`。随后查看日志：

```powershell
docker compose -f compose.yaml -f compose.async.yaml logs --tail 100 redis rabbitmq maars-api
```

### 任务状态一直是 `queued`

说明消息已投递，但对应阶段 Worker 尚未启动。按第 4 节启动同名 `--stage` 的
Worker。

### 任务变为 `failed`

查看 API 任务列表中的 `error` 字段和 Worker 输出。系统最多按 `maxAttempts`
重试；达到上限后消息进入 RabbitMQ 死信队列 `maars.research.dead-letter`。

### 改了代码但容器没有更新

必须重新构建 API 镜像：

```powershell
docker compose -f compose.yaml -f compose.async.yaml up --build -d maars-api
```

## 7. 停止或清理

停止服务但保留 Redis/RabbitMQ 数据卷：

```powershell
docker compose -f compose.yaml -f compose.async.yaml stop
```

停止并删除容器，但仍保留数据卷：

```powershell
docker compose -f compose.yaml -f compose.async.yaml down
```

如需删除全部 Redis/RabbitMQ 本地数据，才执行：

```powershell
docker compose -f compose.yaml -f compose.async.yaml down -v
```

`down -v` 会删除本地队列与缓存数据，执行前请确认不需要恢复未完成任务。
