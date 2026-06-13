# M17b Startup Templates

This guide explains the PowerShell startup templates added in M17b. They wrap the existing Python entry points and do not add Docker, Nginx, systemd, Redis, or a new process manager.

## Python Selection

Each template chooses Python in this order:

1. `-Python`
2. `XHS_AGENT_PYTHON`
3. `D:\Anaconda\envs\ContentShare\python.exe` if it exists
4. `python` from the current shell

Recommended explicit form:

```powershell
$python = 'D:\Anaconda\envs\ContentShare\python.exe'
```

## Local API Mode

Use this for normal local development. The API uses the in-process local queue, so no separate worker terminal is needed.

Check the runtime configuration without starting the server:

```powershell
.\scripts\start_local_api.ps1 -CheckOnly -Python $python
```

Start the local API:

```powershell
.\scripts\start_local_api.ps1 -Python $python -HostName 127.0.0.1 -Port 8010
```

Open:

```text
http://127.0.0.1:8010
```

## SQLite Split-Process Mode

Use this when you want API and worker to run as separate processes. Open two terminals.

Terminal A, API:

```powershell
.\scripts\start_sqlite_api.ps1 -Python $python -DbPath data/xhs_agent.sqlite3 -HostName 127.0.0.1 -Port 8010
```

Terminal B, worker:

```powershell
.\scripts\start_sqlite_worker.ps1 -Python $python -DbPath data/xhs_agent.sqlite3 -WorkerId local-worker-1
```

Check each side without starting long-running processes:

```powershell
.\scripts\start_sqlite_api.ps1 -CheckOnly -Python $python -DbPath data/xhs_agent.sqlite3
.\scripts\start_sqlite_worker.ps1 -CheckOnly -Python $python -DbPath data/xhs_agent.sqlite3
```

Both API and worker must use the same DB path for:

```text
XHS_AGENT_RUN_DB_PATH
XHS_AGENT_QUEUE_DB_PATH
XHS_AGENT_MEMORY_DB_PATH
```

The templates set all three to the same `-DbPath`.

## SQLite Stack Mode

Use this when you want one command to launch the local API, SQLite worker, and watchdog loop with the same DB path. The script starts child processes with hidden windows and prints their PIDs.

Check the shared configuration without starting long-running processes:

```powershell
.\scripts\start_sqlite_stack.ps1 -CheckOnly -Python $python -DbPath data/xhs_agent.sqlite3
```

Start API, worker, and watchdog:

```powershell
.\scripts\start_sqlite_stack.ps1 -Python $python -DbPath data/xhs_agent.sqlite3 -HostName 127.0.0.1 -Port 8010
```

Start only selected pieces:

```powershell
.\scripts\start_sqlite_stack.ps1 -Python $python -NoApi
.\scripts\start_sqlite_stack.ps1 -Python $python -NoWorker -NoWatchdog
```

Start the read-only creator performance scheduler as part of the stack:

```powershell
.\scripts\start_sqlite_stack.ps1 `
  -Python $python `
  -DbPath data/xhs_agent.sqlite3 `
  -StartScheduler `
  -RunId run_877b49f35f98 `
  -SchedulerIntervalSeconds 1800 `
  -SchedulerMaxConsecutiveFailedRounds 3
```

The scheduler still only reads creator note status and metrics snapshots through the existing performance sync path. It does not trigger public publishing, editing, deletion, or platform scheduled publishing.

Check a running stack:

```powershell
.\scripts\check_sqlite_stack_health.ps1 -Python $python -BaseUrl http://127.0.0.1:8010
```

Use `-ConfigOnly` to run only configuration checks, or `-SkipApi` to skip HTTP checks when the API is intentionally not running.

View recent logs:

```powershell
.\scripts\tail_sqlite_stack_logs.ps1 -Tail 80
```

Stop matching stack processes. The default is a dry run:

```powershell
.\scripts\stop_sqlite_stack.ps1
.\scripts\stop_sqlite_stack.ps1 -Apply
```

The stop script only targets processes whose command line includes the known stack entry points: `run_api.py`, `run_worker.py`, or `run_creator_performance_scheduler.py`.

## Guarded API Mode

Set a token when you want protected API endpoints to reject unauthenticated calls.

```powershell
$token = 'replace-with-local-secret'
.\scripts\start_sqlite_api.ps1 -Python $python -ApiToken $token -HostName 127.0.0.1 -Port 8010
```

Smoke test with the same token:

```powershell
& $python .\scripts\check_api_run.py --base-url http://127.0.0.1:8010 --api-token $token --engine langgraph --collect-limit 3 --timeout 180
```

If you call protected endpoints without the token, the API should return `401`.

## One-Shot Worker

Use `-Once` to process at most one queued job and exit:

```powershell
.\scripts\start_sqlite_worker.ps1 -Python $python -DbPath data/xhs_agent.sqlite3 -WorkerId once-worker -Once
```

If no job is queued, the worker exits non-zero. That is expected behavior from `scripts/run_worker.py --once`.

## Production-Lite Preflight

Before any server-facing run, check configuration directly:

```powershell
$env:XHS_AGENT_API_TOKEN = 'replace-with-local-secret'
$env:XHS_AGENT_RUN_STORE = 'sqlite'
$env:XHS_AGENT_RUN_DB_PATH = 'data/xhs_agent.sqlite3'
$env:XHS_AGENT_RUN_QUEUE = 'sqlite'
$env:XHS_AGENT_QUEUE_DB_PATH = 'data/xhs_agent.sqlite3'
$env:XHS_AGENT_MEMORY_STORE = 'sqlite'
$env:XHS_AGENT_MEMORY_DB_PATH = 'data/xhs_agent.sqlite3'
& $python .\scripts\check_runtime_config.py --profile production-lite
```

`production-lite` fails if `XHS_AGENT_API_TOKEN` is empty. It warns when real LLM keys or Spider_XHS cookies are missing.

## Production-Lite Deploy Checklist

Run the deployment-focused preflight before a server-facing single-machine deployment:

```powershell
& $python .\scripts\check_production_lite_deploy.py --backup-dir data/backups
```

This check fails when API token, SQLite store/queue/memory, foundation schema, business table writes, log directory, DB directory, or backup directory are not ready. Missing real LLM key or Spider_XHS cookie is reported as a warning. The script checks whether sensitive settings are present, but it does not print their values.

Back up the SQLite database:

```powershell
& $python .\scripts\backup_sqlite_db.py --db-path data/xhs_agent.sqlite3 --backup-dir data/backups
```

Dry-run restore:

```powershell
& $python .\scripts\restore_sqlite_db.py --target-db-path data/xhs_agent.sqlite3 --backup-path data/backups/<backup-file>.sqlite3
```

Apply restore:

```powershell
& $python .\scripts\restore_sqlite_db.py --target-db-path data/xhs_agent.sqlite3 --backup-path data/backups/<backup-file>.sqlite3 --apply
```

Restore creates a pre-restore backup before replacing the target database when the target file exists.

## Logs

Default log files:

```text
data/logs/api.log
data/logs/worker.log
```

Sensitive keys such as token, cookie, secret, password, authorization, and API key are redacted by the logging helpers.

## Current Limits

These templates make startup repeatable, but they do not make the system fully public-production-ready. Before public exposure, the project still needs HTTPS, reverse proxy, process supervision, backup strategy, stronger secret handling, and user/permission management.
