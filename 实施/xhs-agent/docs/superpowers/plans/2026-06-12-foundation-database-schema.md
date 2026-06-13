# Foundation Database Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an idempotent SQLite foundation schema initializer for the first batch of business tables without changing current run, queue, memory, API, or migration behavior.

**Architecture:** Create a focused `app/database_schema.py` module containing table/index definitions and `initialize_foundation_schema(db_path)` / inspection helpers. Tests verify tables, indexes, idempotency, and coexistence with existing `runs`, `run_queue_jobs`, and `operation_records`; `.env.example` documents opt-in foundation schema configuration.

**Tech Stack:** Python 3 standard library `sqlite3`, pytest, existing SQLite store/queue/memory modules.

---

### Task 1: Schema Initialization Contract

**Files:**
- Create: `tests/test_foundation_database_schema.py`
- Create: `app/database_schema.py`

- [ ] **Step 1: Write failing schema tests**

Add `tests/test_foundation_database_schema.py`:

```python
import sqlite3
from pathlib import Path

from app.database_schema import (
    FOUNDATION_INDEXES,
    FOUNDATION_TABLES,
    initialize_foundation_schema,
)
from app.run_queue import SQLiteRunQueue
from app.run_store import SQLiteRunStore
from memory.operation_store import SQLiteOperationMemoryBackend


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    return {row[0] for row in rows}


def _index_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        ).fetchall()
    return {row[0] for row in rows}


def test_initialize_foundation_schema_creates_expected_tables_and_indexes(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"

    initialize_foundation_schema(db_path)

    assert set(FOUNDATION_TABLES).issubset(_table_names(db_path))
    assert set(FOUNDATION_INDEXES).issubset(_index_names(db_path))


def test_initialize_foundation_schema_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"

    initialize_foundation_schema(db_path)
    initialize_foundation_schema(db_path)

    assert set(FOUNDATION_TABLES).issubset(_table_names(db_path))


def test_foundation_schema_coexists_with_existing_sqlite_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    SQLiteRunStore(db_path).save(
        {
            "run_id": "run_schema",
            "status": "queued",
            "created_at": "2026-06-12T10:00:00",
            "updated_at": "2026-06-12T10:00:00",
            "request": {},
            "summary": {},
            "content": {},
            "insights": {},
            "state": {},
            "paths": {},
            "error": None,
        }
    )
    SQLiteRunQueue(db_path=db_path, list_runs=lambda: [{"run_id": "run_schema", "status": "queued"}]).enqueue(
        "run_schema"
    )
    SQLiteOperationMemoryBackend(db_path).save_history(
        {
            "version": 1,
            "updated_at": "2026-06-12T10:00:00",
            "records": [
                {
                    "record_id": "op_schema",
                    "post_id": "post_schema",
                    "topic": "小红书新手选题方法",
                    "created_at": "2026-06-12T10:00:00",
                    "updated_at": "2026-06-12T10:00:00",
                }
            ],
        }
    )

    initialize_foundation_schema(db_path)

    names = _table_names(db_path)
    assert {"runs", "run_queue_jobs", "operation_records"}.issubset(names)
    assert set(FOUNDATION_TABLES).issubset(names)
    assert SQLiteRunStore(db_path).load("run_schema")["status"] == "queued"
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_foundation_database_schema.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.database_schema'`.

- [ ] **Step 3: Implement schema initializer**

Create `app/database_schema.py` with:
- `FOUNDATION_TABLES`: tuple of table names.
- `FOUNDATION_INDEXES`: tuple of index names.
- `initialize_foundation_schema(db_path: str | Path) -> Path`.
- SQL `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` statements for the first-round tables from the approved spec.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_foundation_database_schema.py -q
```

Expected: PASS.

### Task 2: Configuration Documentation

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add configuration comments**

Add these opt-in config examples near the existing SQLite run store / queue / memory settings:

```env
# Foundation business tables. First stage initializes schema only; business
# table writes remain opt-in for later migration steps.
XHS_AGENT_DB_SCHEMA=foundation
XHS_AGENT_BUSINESS_TABLES_ENABLED=false
```

- [ ] **Step 2: Verify no duplicate config blocks**

Run:

```powershell
Select-String -Path .env.example -Pattern "XHS_AGENT_DB_SCHEMA|XHS_AGENT_BUSINESS_TABLES_ENABLED"
```

Expected: exactly two config lines, plus comments if present.

### Task 3: Regression And Memory Update

**Files:**
- Modify: `memory/current_progress.md`
- Modify: `memory/project_status_and_roadmap.md`

- [ ] **Step 1: Run focused SQLite compatibility regression**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_foundation_database_schema.py tests\test_run_store.py tests\test_sqlite_run_queue.py tests\test_operation_store_sqlite.py -q
```

Expected: PASS.

- [ ] **Step 2: Run compile check**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app\database_schema.py
```

Expected: exit code 0.

- [ ] **Step 3: Run full test suite**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

Expected: PASS.

- [ ] **Step 4: Update memory**

Append completion notes to `memory/current_progress.md` and update `memory/project_status_and_roadmap.md`:
- Foundation schema initializer complete.
- First round creates tables/indexes only.
- Existing run store, queue, and operation memory behavior unchanged.
- Next step is optional business table snapshot writer for `raw_notes`, `collection_candidates`, `raw_comments`, and `analysis_reports`.

- [ ] **Step 5: Final hygiene**

Run:

```powershell
git diff --check
git status --short
```

Expected: `git diff --check` exits 0; status shows intended changes plus pre-existing workspace changes.
