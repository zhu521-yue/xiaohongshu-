# M17a Minimal Production Guardrails Design

## Goal

M17a adds the smallest useful set of production guardrails around the existing API and worker:

- optional API token authentication
- file-based logging with sensitive value redaction
- a runtime configuration self-check script
- updated startup instructions for local, SQLite split-process, and guarded modes

This is not a full server deployment. It intentionally stays inside the current Python standard-library HTTP service and SQLite/local-file architecture.

## Current State

The project already has:

- `scripts/run_api.py` to start the HTTP API.
- `scripts/run_worker.py` to run SQLite queue workers.
- `app.api.XHSAgentAPIHandler`, implemented with the Python standard library.
- `XHS_AGENT_RUN_STORE`, `XHS_AGENT_RUN_QUEUE`, and `XHS_AGENT_MEMORY_STORE` settings.
- `docs/m16b-api-worker-startup.md`, which explains local mode and SQLite split-process mode.

The gap is that a server-facing process still has weak operational boundaries:

- no request authentication
- logs mostly go to stdout
- no consistent sensitive value redaction
- no single command to check whether a local or production-lite environment is configured safely

## Chosen Approach

Add "production-lite" guardrails without adding Docker, Nginx, systemd, Redis, Celery, or a web framework.

The default developer experience remains unchanged. Local development still works without authentication, without external services, and with the existing default queue.

Guardrails are enabled through environment variables:

```env
XHS_AGENT_API_TOKEN=
XHS_AGENT_LOG_DIR=data/logs
XHS_AGENT_LOG_LEVEL=INFO
XHS_AGENT_LOG_MAX_BYTES=1048576
XHS_AGENT_LOG_BACKUP_COUNT=5
```

If `XHS_AGENT_API_TOKEN` is empty, API authentication is disabled. If it is set, protected endpoints require the token.

## API Authentication

### Token Rules

The API accepts either of these headers:

```http
Authorization: Bearer <token>
X-XHS-Agent-Token: <token>
```

The configured token comes from `XHS_AGENT_API_TOKEN`.

Rules:

- empty token means authentication disabled
- non-empty token means protected API endpoints require authentication
- token comparison uses constant-time comparison from the standard library
- token values are never logged

### Protected Endpoints

When auth is enabled, protect:

- `GET /runs`
- `GET /runs/{run_id}`
- `GET /queue`
- `POST /runs`
- `POST /runs/{run_id}/approve`
- `POST /runs/{run_id}/reject`

Keep public:

- `GET /health`
- static frontend assets

Keeping static assets public lets the page load, but API calls still fail until the caller supplies a token. Frontend token input can be added later if needed; M17a focuses on API-level protection and script-level verification.

### Error Response

Unauthenticated protected requests return:

```json
{
  "ok": false,
  "error": "Unauthorized"
}
```

Status code: `401`.

## Logging

Add `app/logging_config.py` with:

- `configure_logging(service_name: str) -> logging.Logger`
- `redact_sensitive(value: Any) -> Any`
- `safe_log_dict(payload: dict[str, Any]) -> dict[str, Any]`

Use the Python standard library:

- `logging`
- `logging.handlers.RotatingFileHandler`

Default log files:

```text
data/logs/api.log
data/logs/worker.log
```

The log directory is created if missing.

### Redaction

Redact values whose keys include:

- `token`
- `api_key`
- `key`
- `secret`
- `cookie`
- `authorization`
- `password`

Replace sensitive values with:

```text
<redacted>
```

The logger should not write full request bodies. It should write small operational events:

- API startup settings summary
- request method/path/status
- run submitted
- run approved/rejected
- worker startup
- worker claimed run
- worker run succeeded/failed
- runtime configuration check result

## Runtime Configuration Check

Add `scripts/check_runtime_config.py`.

The script loads the same settings as the app and checks the current environment.

Supported profiles:

```powershell
python .\scripts\check_runtime_config.py --profile local
python .\scripts\check_runtime_config.py --profile sqlite-worker
python .\scripts\check_runtime_config.py --profile production-lite
```

### Local Profile

Checks:

- Python can import core modules.
- log directory can be created and written.
- default local queue/store settings are allowed.
- empty `XHS_AGENT_API_TOKEN` is allowed.

### SQLite Worker Profile

Checks:

- `XHS_AGENT_RUN_STORE=sqlite`
- `XHS_AGENT_RUN_QUEUE=sqlite`
- `XHS_AGENT_MEMORY_STORE=sqlite`
- run DB path and queue DB path match or both point to valid explicit paths
- parent directories for SQLite DB paths are writable
- log directory is writable

### Production-Lite Profile

Checks:

- `XHS_AGENT_API_TOKEN` is set
- log directory is writable
- if using SQLite split-process mode, run store, queue, and memory DB paths are coherent
- `LLM_API_KEY` is reported only as set/unset, never printed
- `XHS_COOKIES_PC` is reported only as set/unset, never printed

Output should be human-readable by default:

```text
PASS log_dir writable: data/logs
WARN api token empty: auth disabled
PASS run queue backend: sqlite
FAIL production-lite requires XHS_AGENT_API_TOKEN
```

Exit code:

- `0` when there are no failures
- `1` when one or more failures exist

Warnings do not fail the command.

## Startup Documentation

Update `docs/m16b-api-worker-startup.md` or add `docs/m17a-production-guardrails.md` with:

- local mode without auth
- SQLite split-process mode without auth
- guarded mode with `XHS_AGENT_API_TOKEN`
- how to pass tokens to `curl`
- how to pass tokens to `scripts/check_api_run.py`
- how to run `scripts/check_runtime_config.py`

`scripts/check_api_run.py` should accept:

```powershell
--api-token <token>
```

and send `Authorization: Bearer <token>` when provided.

## Implementation Boundaries

M17a can touch:

- `app/config.py`
- `app/api.py`
- `scripts/run_api.py`
- `scripts/run_worker.py`
- `scripts/check_api_run.py`
- `scripts/check_runtime_config.py`
- `.env.example`
- docs
- focused tests

M17a should not change:

- graph business logic
- content generation prompts
- collector behavior
- SQLite queue semantics
- run store schema
- operation memory schema

## Testing Scope

Add focused tests for:

- auth disabled by default
- auth enabled rejects missing token
- auth enabled accepts bearer token
- auth enabled accepts `X-XHS-Agent-Token`
- `/health` remains public
- sensitive values are redacted from log-safe dictionaries
- runtime config check passes for local profile
- runtime config check fails production-lite profile when token is missing
- `check_api_run.py` includes auth header when token is provided

Final verification:

```powershell
python -m pytest -q
python -m compileall app nodes routers platforms memory scripts llm
python .\scripts\check_runtime_config.py --profile local
```

Add one guarded API smoke check:

1. Start API with `XHS_AGENT_API_TOKEN=test-token`, mock collector, mock LLM.
2. Confirm unauthenticated `POST /runs` returns `401`.
3. Confirm authenticated `check_api_run.py --api-token test-token` succeeds.

## Out Of Scope

M17a does not include:

- Docker Compose
- systemd
- Nginx
- HTTPS certificates
- user accounts
- role-based permissions
- frontend login UI
- cookie encryption at rest
- Redis/RQ/Celery
- external monitoring or alerting
- automatic deployment scripts

These are valid later tasks, but they are intentionally not part of this small guardrail step.

## Rollback

Rollback is configuration-based:

- unset `XHS_AGENT_API_TOKEN` to disable API auth
- delete or ignore `data/logs/*.log` if file logging is not needed
- keep using `XHS_AGENT_RUN_QUEUE=local` for local development

The changes should not alter existing run records, queue rows, operation memory, or generated outputs.

## Self-Review

- Placeholder scan: no unfinished placeholders remain.
- Internal consistency: auth is opt-in; logging and config checks do not alter business behavior.
- Scope check: limited to guardrails around existing API/worker startup.
- Ambiguity check: no new deployment stack is introduced; production-lite means current process model with auth, logs, and config checks.
