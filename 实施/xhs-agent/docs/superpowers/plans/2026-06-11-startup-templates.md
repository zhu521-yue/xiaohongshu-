# M17b Startup Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Windows-friendly startup templates and a production-lite checklist for the existing API/worker runtime.

**Architecture:** Keep `scripts/run_api.py` and `scripts/run_worker.py` as the actual runtime entry points. Add thin PowerShell wrappers that set environment variables consistently, choose the correct Python interpreter, and optionally run runtime preflight checks.

**Tech Stack:** Python standard library, pytest, PowerShell, existing xhs-agent scripts.

---

## File Structure

- Create: `scripts/start_local_api.ps1`
  - Sets local in-process queue environment and starts the API.
- Create: `scripts/start_sqlite_api.ps1`
  - Sets SQLite run store, queue, and memory environment and starts the API.
- Create: `scripts/start_sqlite_worker.ps1`
  - Sets SQLite run store, queue, and memory environment and starts the worker.
- Create: `docs/m17b-startup-templates.md`
  - User-facing startup and verification guide.
- Create: `tests/test_startup_templates.py`
  - Static checks for script existence and critical safeguards.
- Modify: `memory/current_progress.md`
  - Record M17b progress after verification.

### Task 1: Add Startup Template Tests

**Files:**
- Create: `tests/test_startup_templates.py`

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_script(name: str) -> str:
    return (ROOT / "scripts" / name).read_text(encoding="utf-8")


def test_startup_templates_exist() -> None:
    for name in ("start_local_api.ps1", "start_sqlite_api.ps1", "start_sqlite_worker.ps1"):
        assert (ROOT / "scripts" / name).exists()


def test_templates_support_check_only_and_content_share_python() -> None:
    for name in ("start_local_api.ps1", "start_sqlite_api.ps1", "start_sqlite_worker.ps1"):
        script = read_script(name)
        assert "CheckOnly" in script
        assert "XHS_AGENT_PYTHON" in script
        assert "ContentShare" in script
        assert "check_runtime_config.py" in script


def test_sqlite_templates_share_one_db_path() -> None:
    for name in ("start_sqlite_api.ps1", "start_sqlite_worker.ps1"):
        script = read_script(name)
        assert "XHS_AGENT_RUN_STORE" in script
        assert "XHS_AGENT_RUN_QUEUE" in script
        assert "XHS_AGENT_MEMORY_STORE" in script
        assert "XHS_AGENT_RUN_DB_PATH" in script
        assert "XHS_AGENT_QUEUE_DB_PATH" in script
        assert "XHS_AGENT_MEMORY_DB_PATH" in script
        assert "sqlite-worker" in script
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_startup_templates.py -q
```

Expected: failures because the PowerShell templates do not exist yet.

### Task 2: Add PowerShell Templates

**Files:**
- Create: `scripts/start_local_api.ps1`
- Create: `scripts/start_sqlite_api.ps1`
- Create: `scripts/start_sqlite_worker.ps1`

- [ ] **Step 1: Implement scripts**

Each script must:
- Accept a `-Python` parameter.
- Resolve Python through `-Python`, `XHS_AGENT_PYTHON`, `D:\Anaconda\envs\ContentShare\python.exe`, then `python`.
- Print the selected Python path.
- Support `-CheckOnly`.
- Use existing Python entry points rather than duplicating runtime logic.

- [ ] **Step 2: Run focused tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_startup_templates.py -q
```

Expected: all startup template tests pass.

### Task 3: Add User-Facing Guide

**Files:**
- Create: `docs/m17b-startup-templates.md`

- [ ] **Step 1: Write guide**

Cover:
- Local API template.
- SQLite split-process API and worker templates.
- Guarded API token mode.
- `CheckOnly` preflight.
- Smoke test with `scripts/check_api_run.py --api-token`.
- Production-lite limitations.

- [ ] **Step 2: Verify documentation references real files**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_startup_templates.py -q
```

Expected: tests still pass.

### Task 4: Verify Runtime Checks

**Files:**
- No code changes expected.

- [ ] **Step 1: Run CheckOnly scripts**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_local_api.ps1 -CheckOnly -Python D:\Anaconda\envs\ContentShare\python.exe
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_sqlite_api.ps1 -CheckOnly -Python D:\Anaconda\envs\ContentShare\python.exe
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_sqlite_worker.ps1 -CheckOnly -Python D:\Anaconda\envs\ContentShare\python.exe
```

Expected: local and sqlite preflight checks exit 0.

### Task 5: Final Verification And Progress

**Files:**
- Modify: `memory/current_progress.md`

- [ ] **Step 1: Run full verification**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
```

Expected: tests pass and compileall exits 0.

- [ ] **Step 2: Record M17b progress**

Add a new top section to `memory/current_progress.md` summarizing:
- Startup templates added.
- Documentation added.
- Verification commands and results.
- Reminder that this is still not full public production deployment.
