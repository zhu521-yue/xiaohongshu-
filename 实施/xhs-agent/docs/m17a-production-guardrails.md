# M17a Production Guardrails

M17a adds optional API token auth, redacted file logs, and runtime configuration checks. It does not add Docker, Nginx, systemd, HTTPS, user accounts, or Redis.

## Local Development

Authentication is disabled when `XHS_AGENT_API_TOKEN` is empty.

cmd:

```bat
set COLLECTOR_MODE=mock
set LLM_MODEL_NAME=mock
set XHS_AGENT_RUN_QUEUE=local
set XHS_AGENT_API_TOKEN=
python .\scripts\run_api.py --host 127.0.0.1 --port 8010
```

PowerShell:

```powershell
$env:COLLECTOR_MODE='mock'
$env:LLM_MODEL_NAME='mock'
$env:XHS_AGENT_RUN_QUEUE='local'
$env:XHS_AGENT_API_TOKEN=''
python .\scripts\run_api.py --host 127.0.0.1 --port 8010
```

## Guarded API Mode

Set `XHS_AGENT_API_TOKEN` before starting the API.

cmd:

```bat
set XHS_AGENT_API_TOKEN=replace-with-local-secret
set COLLECTOR_MODE=mock
set LLM_MODEL_NAME=mock
python .\scripts\run_api.py --host 127.0.0.1 --port 8010
```

PowerShell:

```powershell
$env:XHS_AGENT_API_TOKEN='replace-with-local-secret'
$env:COLLECTOR_MODE='mock'
$env:LLM_MODEL_NAME='mock'
python .\scripts\run_api.py --host 127.0.0.1 --port 8010
```

Unauthenticated protected API calls return `401`.

Authenticated smoke check:

```powershell
python .\scripts\check_api_run.py --base-url http://127.0.0.1:8010 --api-token replace-with-local-secret --engine langgraph --collect-limit 3 --timeout 180
```

## Runtime Config Checks

Local profile:

```powershell
python .\scripts\check_runtime_config.py --profile local
```

SQLite split-process profile:

```powershell
python .\scripts\check_runtime_config.py --profile sqlite-worker
```

Guarded server-facing profile:

```powershell
python .\scripts\check_runtime_config.py --profile production-lite
```

`production-lite` fails if `XHS_AGENT_API_TOKEN` is empty.

## Logs

Default files:

```text
data/logs/api.log
data/logs/worker.log
```

Sensitive keys such as token, cookie, secret, password, authorization, and API key are redacted by logging helpers.
