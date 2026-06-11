# M17b Startup Templates Design

## Goal

M17b makes the current API/worker runtime easier to start and verify on Windows without adding Docker, Nginx, systemd, Redis, or a new service manager.

The scope is deliberately small:
- Add PowerShell startup templates for local API, SQLite API, and SQLite worker.
- Prefer the user's `ContentShare` Python interpreter when available, while allowing override through parameters or `XHS_AGENT_PYTHON`.
- Keep the existing Python entry points as the source of truth: `scripts/run_api.py`, `scripts/run_worker.py`, `scripts/check_runtime_config.py`, and `scripts/check_api_run.py`.
- Add documentation that explains local development, split API/worker mode, guarded token mode, and production-lite preflight checks.

## Current Context

M16a/M16b already added SQLite run queue support and an independent worker script. M17a already added optional API token auth, log files, redaction, runtime config checks, and token-aware smoke tests.

The missing piece is operational ergonomics: a user currently has to copy many environment variables into multiple terminals and remember which Python interpreter is correct. That caused confusion because the tool default `python` can resolve to `D:\Anaconda\python.exe`, while the project dependencies are installed in `D:\Anaconda\envs\ContentShare\python.exe`.

## Design

Add three PowerShell scripts under `scripts/`:

- `scripts/start_local_api.ps1`
  - Sets local in-process queue mode.
  - Defaults to mock collector and mock LLM for safe local verification.
  - Starts `scripts/run_api.py`.
  - Supports `-CheckOnly` to run `check_runtime_config.py --profile local` without starting a long-running server.

- `scripts/start_sqlite_api.ps1`
  - Sets SQLite run store, run queue, and operation memory to the same DB path by default.
  - Defaults to mock collector and mock LLM.
  - Starts `scripts/run_api.py`.
  - Supports `-CheckOnly` to run `check_runtime_config.py --profile sqlite-worker`.

- `scripts/start_sqlite_worker.ps1`
  - Uses the same SQLite environment as the API script.
  - Starts `scripts/run_worker.py`.
  - Supports `-Once` and `-CheckOnly`.

All scripts use this Python resolution order:
1. Explicit `-Python`.
2. `XHS_AGENT_PYTHON`.
3. `D:\Anaconda\envs\ContentShare\python.exe` if it exists.
4. `python` from the current shell.

This keeps the user's current environment first-class while avoiding a hard failure on other machines.

## Documentation

Add `docs/m17b-startup-templates.md` with:
- Recommended PowerShell usage.
- Local API start command.
- SQLite split-process start commands.
- Guarded API mode with `XHS_AGENT_API_TOKEN`.
- `CheckOnly` commands.
- Smoke test command using `--api-token`.
- Notes that these scripts do not make the app public-production-ready by themselves.

## Error Handling

The scripts should fail early if:
- The selected Python executable path does not exist.
- Runtime config preflight returns a non-zero exit code.
- The underlying Python script exits non-zero.

They should print the Python path they are using before running the Python entry point.

## Testing

Add Python tests that inspect the PowerShell templates for required safeguards and defaults:
- Each startup template exists.
- Each template supports `-CheckOnly`.
- Templates prefer `ContentShare` through `XHS_AGENT_PYTHON` / known env path fallback.
- SQLite API and worker templates set the same run, queue, and memory DB path.

Manual verification uses the `ContentShare` interpreter:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_local_api.ps1 -CheckOnly
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_sqlite_api.ps1 -CheckOnly
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_sqlite_worker.ps1 -CheckOnly
```
