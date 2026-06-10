# SQLite RunStore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a SQLite-backed run store behind the existing `RunStore` boundary while keeping JSON storage as the default fallback.

**Architecture:** Keep `app/api.py` calling `_save_run()`, `_load_run()`, and `_list_runs()` exactly as it does now. Add `SQLiteRunStore` in `app/run_store.py` with the same public methods as `LocalRunStore`, and select the backend from environment-backed settings.

**Tech Stack:** Python standard library `sqlite3`, existing `python-dotenv` settings loader, `pytest` for tests.

---

## Environment Note

This workspace currently has no `.git` directory. `git status` fails with `fatal: not a git repository`. The checkpoint steps below record what would be committed in a normal repository, but do not require `git commit` in this workspace.

## File Structure

- Create: `tests/test_run_store.py`
  - Behavior tests for `SQLiteRunStore` and a small regression test for `LocalRunStore`.
- Create: `tests/test_api_run_store_selection.py`
  - Behavior test for selecting SQLite or JSON run store from environment variables.
- Modify: `app/run_store.py`
  - Add JSON field helpers, metadata preservation, SQLite schema initialization, `SQLiteRunStore`.
- Modify: `app/config.py`
  - Add `run_store_backend` and `run_db_path` settings.
- Modify: `app/api.py`
  - Import `SQLiteRunStore` and `load_settings()`, select backend in `_run_store()`.
- Modify: `.env.example`
  - Document `XHS_AGENT_RUN_STORE` and `XHS_AGENT_RUN_DB_PATH`.

## Task 1: Add RunStore Behavior Tests

**Files:**
- Create: `tests/test_run_store.py`
- Modify: none
- Test: `tests/test_run_store.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_run_store.py` with this content:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from app.run_store import LocalRunStore, SQLiteRunStore


def sample_record(run_id: str, created_at: str, status: str = "queued") -> dict:
    return {
        "run_id": run_id,
        "status": status,
        "created_at": created_at,
        "updated_at": created_at,
        "started_at": None,
        "finished_at": None,
        "request": {
            "topic": f"topic-{run_id}",
            "target_user": "内容创作新手",
            "format": "image_text",
            "engine": "langgraph",
        },
        "summary": {
            "content_format": "image_text",
            "content_type": "step_tutorial",
            "pain_points_count": 1,
        },
        "content": {
            "titles": ["标题A", "标题B"],
            "body": "正文",
            "tags": ["小红书", "选题"],
        },
        "insights": {
            "pain_points": [{"pain": "不知道怎么开始", "priority": 1}],
            "comment_fetch_errors": [],
        },
        "state": {
            "user_topic": "小红书新手选题方法",
            "human_approved": False,
        },
        "paths": {
            "post_id": None,
            "collection_path": None,
            "operation_memory_path": None,
        },
        "error": None,
        "approved_at": "2026-06-10T12:00:00",
        "reviewed_at": "2026-06-10T12:01:00",
        "review_action": "approved",
    }


def test_sqlite_run_store_saves_and_loads_complex_record(tmp_path: Path) -> None:
    store = SQLiteRunStore(tmp_path / "runs.sqlite3")
    record = sample_record("run_001", "2026-06-10T10:00:00", status="success")

    store.save(record)

    loaded = store.load("run_001")
    assert loaded == record


def test_sqlite_run_store_overwrites_existing_run(tmp_path: Path) -> None:
    store = SQLiteRunStore(tmp_path / "runs.sqlite3")
    first = sample_record("run_001", "2026-06-10T10:00:00", status="queued")
    second = sample_record("run_001", "2026-06-10T10:00:00", status="success")
    second["summary"]["operation_memory_written"] = True

    store.save(first)
    store.save(second)

    loaded = store.load("run_001")
    assert loaded == second


def test_sqlite_run_store_lists_recent_runs_by_created_at_desc(tmp_path: Path) -> None:
    store = SQLiteRunStore(tmp_path / "runs.sqlite3")
    store.save(sample_record("run_old", "2026-06-10T09:00:00"))
    store.save(sample_record("run_new", "2026-06-10T11:00:00"))
    store.save(sample_record("run_mid", "2026-06-10T10:00:00"))

    records = store.list(limit=2)

    assert [record["run_id"] for record in records] == ["run_new", "run_mid"]


def test_sqlite_run_store_missing_run_returns_none(tmp_path: Path) -> None:
    store = SQLiteRunStore(tmp_path / "runs.sqlite3")

    assert store.load("run_missing") is None


def test_sqlite_run_store_rejects_missing_run_id(tmp_path: Path) -> None:
    store = SQLiteRunStore(tmp_path / "runs.sqlite3")
    record = sample_record("run_001", "2026-06-10T10:00:00")
    record["run_id"] = ""

    with pytest.raises(ValueError, match="run record missing run_id"):
        store.save(record)


def test_local_run_store_still_saves_loads_and_overwrites(tmp_path: Path) -> None:
    store = LocalRunStore(tmp_path / "api_runs")
    first = sample_record("run_001", "2026-06-10T10:00:00", status="queued")
    second = sample_record("run_001", "2026-06-10T10:00:00", status="success")

    store.save(first)
    store.save(second)

    assert store.load("run_001") == second
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_run_store.py -q
```

Expected: FAIL during import with `ImportError` or `AttributeError` because `SQLiteRunStore` does not exist yet.

- [ ] **Step 3: Checkpoint**

Record checkpoint:

```text
Checkpoint: run store tests written. Git commit skipped because workspace has no .git directory.
```

## Task 2: Implement SQLiteRunStore

**Files:**
- Modify: `app/run_store.py`
- Test: `tests/test_run_store.py`

- [ ] **Step 1: Replace `app/run_store.py` with the implementation**

Use this complete file content:

```python
"""Run record storage boundaries.

The default implementation stores run records as local JSON files. SQLite is
available as a first database-backed store while the public API stays the same.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable

from app.json_store import read_json_file, write_json_atomic


RUN_FIXED_KEYS = {
    "run_id",
    "status",
    "created_at",
    "updated_at",
    "started_at",
    "finished_at",
    "request",
    "summary",
    "content",
    "insights",
    "state",
    "paths",
    "error",
}


def _json_dumps(value: Any, default: Callable[[Any], str] | None = None) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, default=default)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _metadata_from_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in RUN_FIXED_KEYS
    }


class LocalRunStore:
    def __init__(
        self,
        runs_dir: str | Path,
        json_default: Callable[[Any], str] | None = None,
    ) -> None:
        self.runs_dir = Path(runs_dir)
        self.json_default = json_default
        self._lock = threading.RLock()

    def run_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.json"

    def save(self, record: dict[str, Any]) -> None:
        run_id = str(record.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("run record missing run_id")

        with self._lock:
            write_json_atomic(self.run_path(run_id), record, default=self.json_default)

    def load(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            path = self.run_path(run_id)
            if not path.exists():
                return None
            data = read_json_file(path, default=None, expected_type=dict)
            return data if isinstance(data, dict) else None

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            if not self.runs_dir.exists():
                return []

            records = []
            for path in self.runs_dir.glob("*.json"):
                data = read_json_file(path, default=None, expected_type=dict)
                if isinstance(data, dict):
                    records.append(data)

        records.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return records[:limit]


class SQLiteRunStore:
    def __init__(
        self,
        db_path: str | Path,
        runs_dir: str | Path | None = None,
        json_default: Callable[[Any], str] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.runs_dir = Path(runs_dir) if runs_dir is not None else self.db_path.parent / "api_runs"
        self.json_default = json_default
        self._lock = threading.RLock()
        self._init_db()

    def run_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.json"

    def save(self, record: dict[str, Any]) -> None:
        run_id = str(record.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("run record missing run_id")

        row = {
            "run_id": run_id,
            "status": str(record.get("status") or ""),
            "created_at": str(record.get("created_at") or ""),
            "updated_at": str(record.get("updated_at") or record.get("created_at") or ""),
            "started_at": record.get("started_at"),
            "finished_at": record.get("finished_at"),
            "request_json": _json_dumps(record.get("request") or {}, self.json_default),
            "summary_json": _json_dumps(record.get("summary") or {}, self.json_default),
            "content_json": _json_dumps(record.get("content") or {}, self.json_default),
            "insights_json": _json_dumps(record.get("insights") or {}, self.json_default),
            "state_json": _json_dumps(record.get("state") or {}, self.json_default),
            "paths_json": _json_dumps(record.get("paths") or {}, self.json_default),
            "metadata_json": _json_dumps(_metadata_from_record(record), self.json_default),
            "error": record.get("error"),
        }

        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs (
                    run_id, status, created_at, updated_at, started_at, finished_at,
                    request_json, summary_json, content_json, insights_json,
                    state_json, paths_json, metadata_json, error
                )
                VALUES (
                    :run_id, :status, :created_at, :updated_at, :started_at, :finished_at,
                    :request_json, :summary_json, :content_json, :insights_json,
                    :state_json, :paths_json, :metadata_json, :error
                )
                ON CONFLICT(run_id) DO UPDATE SET
                    status = excluded.status,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at,
                    request_json = excluded.request_json,
                    summary_json = excluded.summary_json,
                    content_json = excluded.content_json,
                    insights_json = excluded.insights_json,
                    state_json = excluded.state_json,
                    paths_json = excluded.paths_json,
                    metadata_json = excluded.metadata_json,
                    error = excluded.error
                """,
                row,
            )

    def load(self, run_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return self._record_from_row(row) if row is not None else None

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        if limit <= 0:
            return []

        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    request_json TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    insights_json TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    paths_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    error TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)"
            )

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> dict[str, Any]:
        metadata = _json_loads(row["metadata_json"], {})
        record = {
            "run_id": row["run_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "request": _json_loads(row["request_json"], {}),
            "summary": _json_loads(row["summary_json"], {}),
            "content": _json_loads(row["content_json"], {}),
            "insights": _json_loads(row["insights_json"], {}),
            "state": _json_loads(row["state_json"], {}),
            "paths": _json_loads(row["paths_json"], {}),
            "error": row["error"],
        }
        if isinstance(metadata, dict):
            record.update(metadata)
        return record
```

- [ ] **Step 2: Run the focused tests**

Run:

```powershell
python -m pytest tests/test_run_store.py -q
```

Expected: PASS.

- [ ] **Step 3: Checkpoint**

Record checkpoint:

```text
Checkpoint: SQLiteRunStore implemented and run store tests pass. Git commit skipped because workspace has no .git directory.
```

## Task 3: Add API Backend Selection Tests

**Files:**
- Create: `tests/test_api_run_store_selection.py`
- Modify: none
- Test: `tests/test_api_run_store_selection.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api_run_store_selection.py` with this content:

```python
from __future__ import annotations

from pathlib import Path

from app import api
from app.run_store import LocalRunStore, SQLiteRunStore


def reset_api_store() -> None:
    api.RUN_STORE = None


def test_api_uses_local_run_store_by_default(monkeypatch) -> None:
    monkeypatch.delenv("XHS_AGENT_RUN_STORE", raising=False)
    monkeypatch.delenv("XHS_AGENT_RUN_DB_PATH", raising=False)
    reset_api_store()

    store = api._run_store()

    assert isinstance(store, LocalRunStore)
    reset_api_store()


def test_api_uses_sqlite_run_store_when_configured(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "runs.sqlite3"
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    reset_api_store()

    store = api._run_store()

    assert isinstance(store, SQLiteRunStore)
    record = {
        "run_id": "run_from_api_selection",
        "status": "queued",
        "created_at": "2026-06-10T10:00:00",
        "updated_at": "2026-06-10T10:00:00",
        "started_at": None,
        "finished_at": None,
        "request": {"topic": "小红书新手选题方法"},
        "summary": {},
        "content": {},
        "insights": {},
        "state": {},
        "paths": {},
        "error": None,
    }
    store.save(record)
    assert db_path.exists()
    assert store.load("run_from_api_selection") == record
    reset_api_store()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_api_run_store_selection.py -q
```

Expected: FAIL because `app.config.Settings` does not expose run store settings and `app.api._run_store()` always returns `LocalRunStore`.

- [ ] **Step 3: Checkpoint**

Record checkpoint:

```text
Checkpoint: API run store selection tests written. Git commit skipped because workspace has no .git directory.
```

## Task 4: Wire Settings and API Store Selection

**Files:**
- Modify: `app/config.py`
- Modify: `app/api.py`
- Test: `tests/test_api_run_store_selection.py`

- [ ] **Step 1: Update `app/config.py`**

Modify the `Settings` dataclass and `load_settings()` so the file contains these added fields:

```python
@dataclass(frozen=True)
class Settings:
    llm_api_key: str | None
    llm_base_url: str | None
    llm_model_name: str
    llm_timeout_seconds: float
    llm_image_text_max_tokens: int
    llm_video_max_tokens: int
    llm_review_max_tokens: int
    account_stage: str
    run_store_backend: str
    run_db_path: str
```

Add these values to `load_settings()`:

```python
        run_store_backend=os.getenv("XHS_AGENT_RUN_STORE", "json").strip().lower() or "json",
        run_db_path=os.getenv("XHS_AGENT_RUN_DB_PATH", "data/xhs_agent.sqlite3"),
```

- [ ] **Step 2: Update `app/api.py` imports**

Change:

```python
from app.run_queue import LocalRunQueue
from app.run_store import LocalRunStore
```

to:

```python
from app.config import load_settings
from app.run_queue import LocalRunQueue
from app.run_store import LocalRunStore, SQLiteRunStore
```

- [ ] **Step 3: Update `_run_store()`**

Replace `_run_store()` in `app/api.py` with:

```python
def _resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _run_store() -> LocalRunStore | SQLiteRunStore:
    global RUN_STORE
    if RUN_STORE is None:
        settings = load_settings()
        if settings.run_store_backend == "sqlite":
            RUN_STORE = SQLiteRunStore(
                _resolve_project_path(settings.run_db_path),
                runs_dir=RUNS_DIR,
                json_default=_json_default,
            )
        else:
            RUN_STORE = LocalRunStore(RUNS_DIR, json_default=_json_default)
    return RUN_STORE
```

Keep the existing `_run_path()`, `_save_run()`, `_load_run()`, and `_list_runs()` functions unchanged.

- [ ] **Step 4: Run the API selection tests**

Run:

```powershell
python -m pytest tests/test_api_run_store_selection.py -q
```

Expected: PASS.

- [ ] **Step 5: Run all run store tests**

Run:

```powershell
python -m pytest tests/test_run_store.py tests/test_api_run_store_selection.py -q
```

Expected: PASS.

- [ ] **Step 6: Checkpoint**

Record checkpoint:

```text
Checkpoint: API can select JSON or SQLite run store. Git commit skipped because workspace has no .git directory.
```

## Task 5: Document Environment Configuration

**Files:**
- Modify: `.env.example`
- Test: none

- [ ] **Step 1: Update `.env.example`**

Add this section after `ACCOUNT_STAGE=cold_start`:

```env
# Run storage backend.
# json keeps the existing data/api_runs/*.json behavior.
# sqlite stores run records in one local SQLite database.
XHS_AGENT_RUN_STORE=json
XHS_AGENT_RUN_DB_PATH=data/xhs_agent.sqlite3
```

- [ ] **Step 2: Verify the example contains the new keys**

Run:

```powershell
rg -n "XHS_AGENT_RUN_STORE|XHS_AGENT_RUN_DB_PATH" .env.example
```

Expected:

```text
.env.example:<line>:XHS_AGENT_RUN_STORE=json
.env.example:<line>:XHS_AGENT_RUN_DB_PATH=data/xhs_agent.sqlite3
```

- [ ] **Step 3: Checkpoint**

Record checkpoint:

```text
Checkpoint: run store environment settings documented. Git commit skipped because workspace has no .git directory.
```

## Task 6: Final Verification

**Files:**
- Test: all touched modules

- [ ] **Step 1: Run all pytest tests**

Run:

```powershell
python -m pytest -q
```

Expected: PASS for all tests.

- [ ] **Step 2: Run compile verification**

Run:

```powershell
python -m compileall app nodes routers platforms memory scripts llm
```

Expected: all files compile successfully.

- [ ] **Step 3: Run a SQLite backend smoke check**

Run:

```powershell
$env:XHS_AGENT_RUN_STORE='sqlite'
$env:XHS_AGENT_RUN_DB_PATH='data/tmp_sqlite_run_store_check.sqlite3'
$env:COLLECTOR_MODE='mock'
$env:LLM_MODEL_NAME='mock'
python -c "from app import api; api.RUN_STORE=None; r=api.create_run({'topic':'小红书新手选题方法','target_user':'内容创作新手','format':'image_text','engine':'langgraph','approve':False,'collect_limit':3}); print(r['status'], r['run_id']); print(api._load_run(r['run_id'])['status']); print(len(api._list_runs(limit=5)))"
```

Expected output includes:

```text
success run_
success
```

- [ ] **Step 4: Remove temporary smoke database**

Run:

```powershell
$workspace=(Resolve-Path '.').Path
$target=Join-Path $workspace 'data\tmp_sqlite_run_store_check.sqlite3'
if (Test-Path -LiteralPath $target) {
  $resolved=(Resolve-Path -LiteralPath $target).Path
  if ($resolved.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) {
    Remove-Item -LiteralPath $resolved -Force
  } else {
    throw "Refusing to remove outside workspace: $resolved"
  }
}
```

Expected: command completes with no output.

- [ ] **Step 5: Final checkpoint**

Record checkpoint:

```text
Checkpoint: SQLite RunStore implementation verified. Git commit skipped because workspace has no .git directory.
```

## Self-Review

- Spec coverage: The plan covers SQLite store implementation, JSON fallback, API env selection, `.env.example`, pytest coverage, and verification.
- Completion marker scan: No unfinished markers remain.
- Type consistency: `SQLiteRunStore` exposes the same public methods as `LocalRunStore`; `app.api._run_store()` returns either store type; tests import those exact names.
- Scope check: The plan does not migrate `operation_history.json`, does not introduce Redis/RQ/Celery, and does not split API/worker.
