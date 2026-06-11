# M16b API / Worker 启动与自测说明

本文档说明当前 xhs-agent 如何在本地启动 API，以及如何用 SQLite 队列把 API 进程和 worker 进程拆开运行。

当前有两种运行模式：

- 默认本地模式：`XHS_AGENT_RUN_QUEUE=local`，API 进程内置 worker，适合快速开发。
- SQLite 分进程模式：`XHS_AGENT_RUN_QUEUE=sqlite`，API 只负责任务入队，独立 worker 负责执行任务。

## 1. 进入项目目录

cmd：

```bat
cd /d D:\codex\project\小红书内容分享\实施\xhs-agent
```

PowerShell：

```powershell
Set-Location "D:\codex\project\小红书内容分享\实施\xhs-agent"
```

确认 Python 环境：

```bat
where python
python -c "import sys; print(sys.executable); from langgraph.graph import StateGraph; print('langgraph ok')"
```

期望 Python 指向你的 `ContentShare` 环境，并输出 `langgraph ok`。

## 2. 默认本地模式

默认模式不需要单独启动 worker。API 收到任务后会在同一进程内排队执行。

cmd：

```bat
set COLLECTOR_MODE=mock
set LLM_MODEL_NAME=mock
set XHS_AGENT_RUN_QUEUE=local
python .\scripts\run_api.py --host 127.0.0.1 --port 8010
```

PowerShell：

```powershell
$env:COLLECTOR_MODE='mock'
$env:LLM_MODEL_NAME='mock'
$env:XHS_AGENT_RUN_QUEUE='local'
python .\scripts\run_api.py --host 127.0.0.1 --port 8010
```

打开浏览器：

```text
http://127.0.0.1:8010
```

另开一个终端验证 API 任务：

```bat
python .\scripts\check_api_run.py --base-url http://127.0.0.1:8010 --engine langgraph --collect-limit 3 --timeout 180
```

## 3. SQLite 分进程模式

SQLite 分进程模式需要两个终端：一个启动 API，一个启动 worker。两个进程必须使用同一组 SQLite 路径。

推荐本地开发配置：

```text
XHS_AGENT_RUN_STORE=sqlite
XHS_AGENT_RUN_DB_PATH=data/xhs_agent.sqlite3
XHS_AGENT_RUN_QUEUE=sqlite
XHS_AGENT_QUEUE_DB_PATH=data/xhs_agent.sqlite3
XHS_AGENT_MEMORY_STORE=sqlite
XHS_AGENT_MEMORY_DB_PATH=data/xhs_agent.sqlite3
COLLECTOR_MODE=mock
LLM_MODEL_NAME=mock
```

### 3.1 终端 A：启动 API

cmd：

```bat
set XHS_AGENT_RUN_STORE=sqlite
set XHS_AGENT_RUN_DB_PATH=data/xhs_agent.sqlite3
set XHS_AGENT_RUN_QUEUE=sqlite
set XHS_AGENT_QUEUE_DB_PATH=data/xhs_agent.sqlite3
set XHS_AGENT_MEMORY_STORE=sqlite
set XHS_AGENT_MEMORY_DB_PATH=data/xhs_agent.sqlite3
set COLLECTOR_MODE=mock
set LLM_MODEL_NAME=mock
python .\scripts\run_api.py --host 127.0.0.1 --port 8010
```

PowerShell：

```powershell
$env:XHS_AGENT_RUN_STORE='sqlite'
$env:XHS_AGENT_RUN_DB_PATH='data/xhs_agent.sqlite3'
$env:XHS_AGENT_RUN_QUEUE='sqlite'
$env:XHS_AGENT_QUEUE_DB_PATH='data/xhs_agent.sqlite3'
$env:XHS_AGENT_MEMORY_STORE='sqlite'
$env:XHS_AGENT_MEMORY_DB_PATH='data/xhs_agent.sqlite3'
$env:COLLECTOR_MODE='mock'
$env:LLM_MODEL_NAME='mock'
python .\scripts\run_api.py --host 127.0.0.1 --port 8010
```

### 3.2 终端 B：启动 worker

cmd：

```bat
set XHS_AGENT_RUN_STORE=sqlite
set XHS_AGENT_RUN_DB_PATH=data/xhs_agent.sqlite3
set XHS_AGENT_RUN_QUEUE=sqlite
set XHS_AGENT_QUEUE_DB_PATH=data/xhs_agent.sqlite3
set XHS_AGENT_MEMORY_STORE=sqlite
set XHS_AGENT_MEMORY_DB_PATH=data/xhs_agent.sqlite3
set COLLECTOR_MODE=mock
set LLM_MODEL_NAME=mock
python .\scripts\run_worker.py --worker-id local-worker-1
```

PowerShell：

```powershell
$env:XHS_AGENT_RUN_STORE='sqlite'
$env:XHS_AGENT_RUN_DB_PATH='data/xhs_agent.sqlite3'
$env:XHS_AGENT_RUN_QUEUE='sqlite'
$env:XHS_AGENT_QUEUE_DB_PATH='data/xhs_agent.sqlite3'
$env:XHS_AGENT_MEMORY_STORE='sqlite'
$env:XHS_AGENT_MEMORY_DB_PATH='data/xhs_agent.sqlite3'
$env:COLLECTOR_MODE='mock'
$env:LLM_MODEL_NAME='mock'
python .\scripts\run_worker.py --worker-id local-worker-1
```

## 4. SQLite 分进程模式自测

API 和 worker 都启动后，在第三个终端运行：

```bat
python .\scripts\check_api_run.py --base-url http://127.0.0.1:8010 --engine langgraph --collect-limit 3 --timeout 180
```

期望：

- `submit_status: 202`
- `initial_status: queued`
- 轮询最终出现 `success`
- 输出的 run JSON 中 `status` 为 `success`

检查队列状态：

```bat
python -c "import json, urllib.request; print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:8010/queue')), ensure_ascii=False, indent=2))"
```

期望：

- `worker_backend` 为 `sqlite`
- `queued_count` 为 `0`
- `running_count` 为 `0`

## 5. 单步 worker 自测

`--once` 只处理一个任务。没有任务时会返回非零退出码，这是预期行为。

```bat
python .\scripts\run_worker.py --once --worker-id once-worker
```

适合配合 API 提交任务后手动处理一次：

1. 启动 SQLite 模式 API。
2. 提交一个 run。
3. 运行 `python .\scripts\run_worker.py --once --worker-id once-worker`。
4. 查询 `/runs/{run_id}` 确认状态。

## 6. 常见问题

### cmd 里不能使用 `$env:...`

`$env:NAME='value'` 是 PowerShell 语法。cmd 要使用：

```bat
set NAME=value
```

### SQLite 模式下任务一直 queued

通常是 worker 没启动，或 API 和 worker 使用了不同的 DB 路径。确认两边这些变量一致：

```text
XHS_AGENT_RUN_DB_PATH
XHS_AGENT_QUEUE_DB_PATH
XHS_AGENT_MEMORY_DB_PATH
```

### worker 报错要求 SQLite 队列

`scripts/run_worker.py` 只支持 SQLite 队列。必须设置：

```text
XHS_AGENT_RUN_QUEUE=sqlite
```

### 使用真实采集

把 `COLLECTOR_MODE` 改成 `spider_xhs`，并在 `.env` 里配置有效的 `XHS_COOKIES_PC`。

真实采集会受 Cookie、平台风控和网络波动影响。调试工程链路时优先使用：

```text
COLLECTOR_MODE=mock
LLM_MODEL_NAME=mock
```

### pytest 提示 `data\pytest_tmp` 权限拒绝

这是 Windows 临时目录残留问题，不是业务测试失败。关闭正在运行的测试进程后，清理项目内测试临时目录：

PowerShell：

```powershell
$workspace=(Resolve-Path '.').Path
$target=Join-Path $workspace 'data\pytest_tmp'
if (Test-Path -LiteralPath $target) {
  $resolved=(Resolve-Path -LiteralPath $target).Path
  if ($resolved.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) {
    Remove-Item -LiteralPath $resolved -Recurse -Force
  }
}
```

然后重新运行：

```bat
python -m pytest -q
```

## 7. 开发验证命令

每次改动后建议运行：

```bat
python -m pytest -q
python -m compileall app nodes routers platforms memory scripts llm
```

重点验证 SQLite queue + worker + LangGraph：

```bat
python -m pytest tests/test_sqlite_queue_worker_integration.py -q
```
