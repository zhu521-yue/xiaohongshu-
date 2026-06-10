# SQLite Run Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in SQLite-backed run queue and a worker script so API submission and run execution can operate in separate processes.

**Architecture:** Keep `LocalRunQueue` as the default development backend. Add `SQLiteRunQueue` in `app/run_queue.py` with a persistent `run_queue_jobs` table, selected through `XHS_AGENT_RUN_QUEUE=sqlite`. Add `scripts/run_worker.py` to claim jobs, execute existing `app.api._execute_run(run_id)`, and update queue job status based on the run store result.

**Tech Stack:** Python standard library `sqlite3`, existing `app.config` settings loader, existing `app.api` run execution functions, `pytest`.

---

## File Structure

- Modify: `app/run_queue.py`
  - Add `SQLiteRunQueue` and small SQLite helpers next to `LocalRunQueue`.
- Modify: `app/config.py`
  - Add queue backend, queue DB path, poll interval, max attempts, and lock timeout settings.
- Modify: `app/api.py`
  - Select `LocalRunQueue` or `SQLiteRunQueue` from settings.
  - Keep existing queue wrapper functions stable.
- Create: `scripts/run_worker.py`
  - Add a command-line worker loop and a single-pass helper for tests and smoke checks.
- Modify: `.env.example`
  - Document queue backend environment variables.
- Modify: `memory/current_progress.md`
  - Add a short M16a progress summary after implementation.
- Create: `tests/test_sqlite_run_queue.py`
  - Cover SQLite queue enqueue, claim, status, completion, retries, and stale lock behavior.
- Create: `tests/test_api_run_queue_selection.py`
  - Cover API queue backend selection and SQLite queue non-threaded behavior.
- Create: `tests/test_run_worker.py`
  - Cover worker single-pass success and failure classification using test doubles.

## Task 1: Add SQLite Run Queue Behavior Tests

**Files:**
- Create: `tests/test_sqlite_run_queue.py`
- Test: `tests/test_sqlite_run_queue.py`

- [ ] **Step 1: Write failing queue tests**

Create `tests/test_sqlite_run_queue.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from app.run_queue import SQLiteRunQueue


def sample_runs(status_by_id: dict[str, str]):
    def _list_runs(limit: int) -> list[dict]:
        return [
            {
                "run_id": run_id,
                "status": status,
                "created_at": f"2026-06-10T10:00:0{index}",
            }
            for index, (run_id, status) in enumerate(status_by_id.items())
        ][:limit]

    return _list_runs


def test_sqlite_queue_enqueues_once_and_reports_status(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued"}),
    )

    queue.enqueue("run_1")
    queue.enqueue("run_1")

    status = queue.status()
    assert status["worker_backend"] == "sqlite"
    assert status["queued_count"] == 1
    assert status["queued_run_ids"] == ["run_1"]
    assert status["running_count"] == 0
    assert status["failed_count"] == 0


def test_sqlite_queue_claims_one_job_and_locks_it(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued", "run_2": "queued"}),
    )
    queue.enqueue("run_1")
    queue.enqueue("run_2")

    first = queue.claim_next("worker-a")
    second = queue.claim_next("worker-b")

    assert first == "run_1"
    assert second == "run_2"
    status = queue.status()
    assert status["queued_count"] == 0
    assert status["running_count"] == 2
    assert status["running_run_ids"] == ["run_1", "run_2"]


def test_sqlite_queue_locked_job_is_not_claimed_twice(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued"}),
    )
    queue.enqueue("run_1")

    assert queue.claim_next("worker-a") == "run_1"
    assert queue.claim_next("worker-b") is None


def test_sqlite_queue_mark_succeeded_removes_job_from_active_status(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued"}),
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    queue.mark_succeeded("run_1", "worker-a")

    status = queue.status()
    assert status["queued_count"] == 0
    assert status["running_count"] == 0
    assert status["failed_count"] == 0


def test_sqlite_queue_mark_failed_requeues_before_max_attempts(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued"}),
        max_attempts=2,
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    terminal = queue.mark_failed("run_1", "worker-a", "first failure")

    assert terminal is False
    status = queue.status()
    assert status["queued_run_ids"] == ["run_1"]
    assert status["failed_count"] == 0


def test_sqlite_queue_mark_failed_terminal_after_max_attempts(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued"}),
        max_attempts=1,
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    terminal = queue.mark_failed("run_1", "worker-a", "terminal failure")

    assert terminal is True
    status = queue.status()
    assert status["queued_count"] == 0
    assert status["running_count"] == 0
    assert status["failed_count"] == 1
    assert status["failed_run_ids"] == ["run_1"]


def test_sqlite_queue_stale_running_job_can_be_reclaimed(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "running"}),
        lock_timeout_seconds=1,
        max_attempts=3,
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    stale_locked_at = (datetime.now() - timedelta(seconds=5)).isoformat(timespec="seconds")
    with queue._connect() as connection:
        connection.execute(
            "UPDATE run_queue_jobs SET locked_at = ? WHERE run_id = ?",
            (stale_locked_at, "run_1"),
        )

    assert queue.claim_next("worker-b") == "run_1"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_sqlite_run_queue.py -q
```

Expected: FAIL with an import error similar to `cannot import name 'SQLiteRunQueue'`.

## Task 2: Implement SQLiteRunQueue

**Files:**
- Modify: `app/run_queue.py`
- Test: `tests/test_sqlite_run_queue.py`

- [ ] **Step 1: Add imports and helper functions**

In `app/run_queue.py`, extend imports:

```python
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
```

Add helpers below imports:

```python
def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

- [ ] **Step 2: Add SQLiteRunQueue class**

Append this class to `app/run_queue.py`:

```python
class SQLiteRunQueue:
    def __init__(
        self,
        db_path: str | Path,
        list_runs: Callable[[int], list[dict[str, Any]]],
        max_attempts: int = 3,
        lock_timeout_seconds: int = 900,
    ) -> None:
        self.db_path = Path(db_path)
        self._list_runs = list_runs
        self._max_attempts = max(1, _safe_int(max_attempts, 3))
        self._lock_timeout_seconds = max(1, _safe_int(lock_timeout_seconds, 900))
        self._lock = threading.RLock()
        self._init_db()

    def enqueue(self, run_id: str) -> None:
        run_id = str(run_id or "").strip()
        if not run_id:
            return
        now = _now_iso()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO run_queue_jobs (
                    run_id, status, attempts, max_attempts, available_at,
                    locked_at, locked_by, last_error, created_at, updated_at, finished_at
                )
                VALUES (?, 'queued', 0, ?, ?, NULL, NULL, NULL, ?, ?, NULL)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = CASE
                        WHEN run_queue_jobs.status = 'failed' THEN 'queued'
                        ELSE run_queue_jobs.status
                    END,
                    available_at = CASE
                        WHEN run_queue_jobs.status = 'failed' THEN excluded.available_at
                        ELSE run_queue_jobs.available_at
                    END,
                    updated_at = CASE
                        WHEN run_queue_jobs.status = 'failed' THEN excluded.updated_at
                        ELSE run_queue_jobs.updated_at
                    END,
                    finished_at = CASE
                        WHEN run_queue_jobs.status = 'failed' THEN NULL
                        ELSE run_queue_jobs.finished_at
                    END
                """,
                (run_id, self._max_attempts, now, now, now),
            )

    def recover_pending_runs(self) -> None:
        for run in self._list_runs(10000):
            if run.get("status") in {"queued", "running"}:
                run_id = str(run.get("run_id") or "")
                if run_id:
                    self.enqueue(run_id)

    def status(self) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id, status, created_at
                FROM run_queue_jobs
                WHERE status IN ('queued', 'running', 'failed')
                ORDER BY created_at ASC
                """
            ).fetchall()
        queued = [row["run_id"] for row in rows if row["status"] == "queued"]
        running = [row["run_id"] for row in rows if row["status"] == "running"]
        failed = [row["run_id"] for row in rows if row["status"] == "failed"]
        return {
            "queued_count": len(queued),
            "running_count": len(running),
            "queued_run_ids": queued,
            "running_run_ids": running,
            "failed_count": len(failed),
            "failed_run_ids": failed,
            "worker_backend": "sqlite",
            "worker_count": 0,
        }

    def claim_next(self, worker_id: str) -> str | None:
        worker_id = str(worker_id or "").strip() or "worker"
        now_dt = datetime.now()
        now = now_dt.isoformat(timespec="seconds")
        stale_before = (now_dt - timedelta(seconds=self._lock_timeout_seconds)).isoformat(timespec="seconds")
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT run_id
                FROM run_queue_jobs
                WHERE
                    (status = 'queued' AND available_at <= ?)
                    OR (
                        status = 'running'
                        AND locked_at IS NOT NULL
                        AND locked_at < ?
                        AND attempts < max_attempts
                    )
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (now, stale_before),
            ).fetchone()
            if row is None:
                return None
            run_id = row["run_id"]
            connection.execute(
                """
                UPDATE run_queue_jobs
                SET status = 'running',
                    attempts = attempts + 1,
                    locked_at = ?,
                    locked_by = ?,
                    updated_at = ?,
                    finished_at = NULL
                WHERE run_id = ?
                """,
                (now, worker_id, now, run_id),
            )
            return str(run_id)

    def mark_succeeded(self, run_id: str, worker_id: str) -> None:
        now = _now_iso()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE run_queue_jobs
                SET status = 'succeeded',
                    locked_by = ?,
                    updated_at = ?,
                    finished_at = ?
                WHERE run_id = ?
                """,
                (worker_id, now, now, run_id),
            )

    def mark_failed(self, run_id: str, worker_id: str, error: str) -> bool:
        now = _now_iso()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT attempts, max_attempts FROM run_queue_jobs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                return True
            terminal = int(row["attempts"]) >= int(row["max_attempts"])
            if terminal:
                connection.execute(
                    """
                    UPDATE run_queue_jobs
                    SET status = 'failed',
                        locked_by = ?,
                        last_error = ?,
                        updated_at = ?,
                        finished_at = ?
                    WHERE run_id = ?
                    """,
                    (worker_id, error, now, now, run_id),
                )
                return True
            connection.execute(
                """
                UPDATE run_queue_jobs
                SET status = 'queued',
                    available_at = ?,
                    locked_at = NULL,
                    locked_by = NULL,
                    last_error = ?,
                    updated_at = ?,
                    finished_at = NULL
                WHERE run_id = ?
                """,
                (now, error, now, run_id),
            )
            return False

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS run_queue_jobs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    available_at TEXT NOT NULL,
                    locked_at TEXT,
                    locked_by TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_run_queue_jobs_status_available
                ON run_queue_jobs(status, available_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_run_queue_jobs_locked_at
                ON run_queue_jobs(locked_at)
                """
            )
```

- [ ] **Step 3: Run queue tests**

Run:

```powershell
python -m pytest tests/test_sqlite_run_queue.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit queue implementation**

Run:

```powershell
git add app/run_queue.py tests/test_sqlite_run_queue.py
git commit -m "feat: add sqlite run queue"
```

## Task 3: Add Queue Settings And API Selection

**Files:**
- Modify: `app/config.py`
- Modify: `app/api.py`
- Modify: `.env.example`
- Create: `tests/test_api_run_queue_selection.py`
- Test: `tests/test_api_run_queue_selection.py`

- [ ] **Step 1: Write failing API selection tests**

Create `tests/test_api_run_queue_selection.py`:

```python
from __future__ import annotations

from pathlib import Path

from app import api
from app.run_queue import LocalRunQueue, SQLiteRunQueue


def reset_api_queue() -> None:
    api.RUN_QUEUE_SERVICE = None


def test_api_uses_local_run_queue_by_default(monkeypatch) -> None:
    monkeypatch.delenv("XHS_AGENT_RUN_QUEUE", raising=False)
    monkeypatch.delenv("XHS_AGENT_QUEUE_DB_PATH", raising=False)
    reset_api_queue()

    queue = api._run_queue_service()

    assert isinstance(queue, LocalRunQueue)
    reset_api_queue()


def test_api_uses_sqlite_run_queue_when_configured(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "queue.sqlite3"
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_QUEUE_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_QUEUE_MAX_ATTEMPTS", "4")
    monkeypatch.setenv("XHS_AGENT_QUEUE_LOCK_TIMEOUT_SECONDS", "7")
    reset_api_queue()

    queue = api._run_queue_service()

    assert isinstance(queue, SQLiteRunQueue)
    queue.enqueue("run_api_queue_selection")
    assert db_path.exists()
    assert queue.status()["queued_run_ids"] == ["run_api_queue_selection"]
    reset_api_queue()
```

- [ ] **Step 2: Run selection tests to verify failure**

Run:

```powershell
python -m pytest tests/test_api_run_queue_selection.py -q
```

Expected: FAIL because `SQLiteRunQueue` is not imported or selected by `app.api`.

- [ ] **Step 3: Add settings fields**

In `app/config.py`, add fields to `Settings`:

```python
    run_queue_backend: str
    queue_db_path: str
    queue_poll_seconds: float
    queue_max_attempts: int
    queue_lock_timeout_seconds: int
```

Add values in `load_settings()`:

```python
        run_queue_backend=os.getenv("XHS_AGENT_RUN_QUEUE", "local").strip().lower() or "local",
        queue_db_path=os.getenv("XHS_AGENT_QUEUE_DB_PATH", "data/xhs_agent.sqlite3"),
        queue_poll_seconds=_env_float("XHS_AGENT_QUEUE_POLL_SECONDS", 1.0),
        queue_max_attempts=_env_int("XHS_AGENT_QUEUE_MAX_ATTEMPTS", 3),
        queue_lock_timeout_seconds=_env_int("XHS_AGENT_QUEUE_LOCK_TIMEOUT_SECONDS", 900),
```

- [ ] **Step 4: Select SQLiteRunQueue in API**

In `app/api.py`, change import:

```python
from app.run_queue import LocalRunQueue, SQLiteRunQueue
```

Change queue type global:

```python
RUN_QUEUE_SERVICE: LocalRunQueue | SQLiteRunQueue | None = None
```

Change `_run_queue_service()`:

```python
def _run_queue_service() -> LocalRunQueue | SQLiteRunQueue:
    global RUN_QUEUE_SERVICE
    if RUN_QUEUE_SERVICE is None:
        settings = load_settings()
        if settings.run_queue_backend == "sqlite":
            RUN_QUEUE_SERVICE = SQLiteRunQueue(
                db_path=_resolve_project_path(settings.queue_db_path),
                list_runs=_list_runs,
                max_attempts=settings.queue_max_attempts,
                lock_timeout_seconds=settings.queue_lock_timeout_seconds,
            )
        else:
            RUN_QUEUE_SERVICE = LocalRunQueue(
                execute_run=_execute_run,
                list_runs=_list_runs,
                worker_count=_local_worker_count(),
            )
    return RUN_QUEUE_SERVICE
```

- [ ] **Step 5: Document queue env vars**

In `.env.example`, add after run store settings:

```env
# Run queue backend.
# local keeps the current in-process worker behavior.
# sqlite persists queue jobs and requires scripts/run_worker.py to execute them.
XHS_AGENT_RUN_QUEUE=local
XHS_AGENT_QUEUE_DB_PATH=data/xhs_agent.sqlite3
XHS_AGENT_WORKER_ID=
XHS_AGENT_QUEUE_POLL_SECONDS=1
XHS_AGENT_QUEUE_MAX_ATTEMPTS=3
XHS_AGENT_QUEUE_LOCK_TIMEOUT_SECONDS=900
```

- [ ] **Step 6: Run selection tests**

Run:

```powershell
python -m pytest tests/test_api_run_queue_selection.py -q
```

Expected: PASS.

- [ ] **Step 7: Run queue and API selection tests together**

Run:

```powershell
python -m pytest tests/test_sqlite_run_queue.py tests/test_api_run_queue_selection.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit API queue selection**

Run:

```powershell
git add app/config.py app/api.py .env.example tests/test_api_run_queue_selection.py
git commit -m "feat: select sqlite run queue backend"
```

## Task 4: Add Worker Script

**Files:**
- Create: `scripts/run_worker.py`
- Create: `tests/test_run_worker.py`
- Test: `tests/test_run_worker.py`

- [ ] **Step 1: Write failing worker tests**

Create `tests/test_run_worker.py`:

```python
from __future__ import annotations

from scripts import run_worker


class FakeQueue:
    def __init__(self, run_id: str | None) -> None:
        self.run_id = run_id
        self.succeeded: list[tuple[str, str]] = []
        self.failed: list[tuple[str, str, str]] = []

    def claim_next(self, worker_id: str) -> str | None:
        run_id = self.run_id
        self.run_id = None
        return run_id

    def mark_succeeded(self, run_id: str, worker_id: str) -> None:
        self.succeeded.append((run_id, worker_id))

    def mark_failed(self, run_id: str, worker_id: str, error: str) -> bool:
        self.failed.append((run_id, worker_id, error))
        return True


def test_run_worker_once_marks_success(monkeypatch) -> None:
    queue = FakeQueue("run_1")
    records = {"run_1": {"status": "success", "error": None}}

    def execute_run(run_id: str) -> None:
        records[run_id]["executed"] = True

    def load_run(run_id: str) -> dict:
        return records[run_id]

    did_work = run_worker.run_once(
        queue=queue,
        worker_id="worker-a",
        execute_run=execute_run,
        load_run=load_run,
    )

    assert did_work is True
    assert records["run_1"]["executed"] is True
    assert queue.succeeded == [("run_1", "worker-a")]
    assert queue.failed == []


def test_run_worker_once_marks_failed_run_status(monkeypatch) -> None:
    queue = FakeQueue("run_1")
    records = {"run_1": {"status": "failed", "error": "graph failed"}}

    did_work = run_worker.run_once(
        queue=queue,
        worker_id="worker-a",
        execute_run=lambda run_id: None,
        load_run=lambda run_id: records[run_id],
    )

    assert did_work is True
    assert queue.succeeded == []
    assert queue.failed == [("run_1", "worker-a", "graph failed")]


def test_run_worker_once_returns_false_when_no_job() -> None:
    queue = FakeQueue(None)

    did_work = run_worker.run_once(
        queue=queue,
        worker_id="worker-a",
        execute_run=lambda run_id: None,
        load_run=lambda run_id: {},
    )

    assert did_work is False
    assert queue.succeeded == []
    assert queue.failed == []
```

- [ ] **Step 2: Run worker tests to verify failure**

Run:

```powershell
python -m pytest tests/test_run_worker.py -q
```

Expected: FAIL because `scripts/run_worker.py` does not exist.

- [ ] **Step 3: Create worker script**

Create `scripts/run_worker.py`:

```python
from __future__ import annotations

import argparse
import socket
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import api  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.run_queue import SQLiteRunQueue  # noqa: E402


def build_worker_id(configured_worker_id: str | None = None) -> str:
    configured = str(configured_worker_id or "").strip()
    if configured:
        return configured
    return f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


def run_once(
    queue: SQLiteRunQueue,
    worker_id: str,
    execute_run: Callable[[str], None] = api._execute_run,
    load_run: Callable[[str], dict[str, Any] | None] = api._load_run,
) -> bool:
    run_id = queue.claim_next(worker_id)
    if not run_id:
        return False

    try:
        execute_run(run_id)
        record = load_run(run_id) or {}
        status = record.get("status")
        if status == "success":
            queue.mark_succeeded(run_id, worker_id)
        elif status == "failed":
            queue.mark_failed(run_id, worker_id, str(record.get("error") or "run failed"))
        else:
            queue.mark_failed(run_id, worker_id, f"run ended with unexpected status: {status}")
    except Exception as exc:
        queue.mark_failed(run_id, worker_id, str(exc))
    return True


def run_loop(worker_id: str, poll_seconds: float) -> None:
    queue = api._run_queue_service()
    if not isinstance(queue, SQLiteRunQueue):
        raise RuntimeError("scripts/run_worker.py requires XHS_AGENT_RUN_QUEUE=sqlite")

    while True:
        did_work = run_once(queue=queue, worker_id=worker_id)
        if not did_work:
            time.sleep(max(0.1, poll_seconds))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SQLite queue worker for xhs-agent.")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job and exit.")
    parser.add_argument("--worker-id", default=None, help="Stable worker id for queue locks.")
    args = parser.parse_args(argv)

    settings = load_settings()
    worker_id = build_worker_id(args.worker_id or settings.worker_id)
    queue = api._run_queue_service()
    if not isinstance(queue, SQLiteRunQueue):
        raise RuntimeError("scripts/run_worker.py requires XHS_AGENT_RUN_QUEUE=sqlite")

    if args.once:
        return 0 if run_once(queue=queue, worker_id=worker_id) else 1

    run_loop(worker_id=worker_id, poll_seconds=settings.queue_poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add `worker_id` setting used by worker script**

In `app/config.py`, add field:

```python
    worker_id: str | None
```

Add value in `load_settings()`:

```python
        worker_id=os.getenv("XHS_AGENT_WORKER_ID"),
```

- [ ] **Step 5: Run worker tests**

Run:

```powershell
python -m pytest tests/test_run_worker.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit worker script**

Run:

```powershell
git add scripts/run_worker.py tests/test_run_worker.py app/config.py
git commit -m "feat: add sqlite queue worker"
```

## Task 5: Add Integration Smoke Test

**Files:**
- Create: `tests/test_sqlite_queue_worker_integration.py`
- Test: `tests/test_sqlite_queue_worker_integration.py`

- [ ] **Step 1: Write failing integration test**

Create `tests/test_sqlite_queue_worker_integration.py`:

```python
from __future__ import annotations

from pathlib import Path

from app import api
from scripts import run_worker


def reset_api_services() -> None:
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None


def test_sqlite_queue_worker_processes_submitted_mock_run(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_QUEUE_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(db_path))
    monkeypatch.setenv("COLLECTOR_MODE", "mock")
    monkeypatch.setenv("LLM_MODEL_NAME", "mock")
    reset_api_services()

    submitted = api.submit_run(
        {
            "topic": "小红书新手选题方法",
            "target_user": "内容创作新手",
            "format": "image_text",
            "engine": "langgraph",
            "approve": False,
            "collect_limit": 3,
        }
    )

    assert submitted["status"] == "queued"
    assert api.queue_status()["queued_run_ids"] == [submitted["run_id"]]

    did_work = run_worker.run_once(
        queue=api._run_queue_service(),
        worker_id="test-worker",
    )

    loaded = api._load_run(submitted["run_id"])
    assert did_work is True
    assert loaded is not None
    assert loaded["status"] == "success"
    assert api.queue_status()["queued_count"] == 0
    assert api.queue_status()["running_count"] == 0
    reset_api_services()
```

- [ ] **Step 2: Run integration test to verify current behavior**

Run:

```powershell
python -m pytest tests/test_sqlite_queue_worker_integration.py -q
```

Expected: PASS if Tasks 2-4 are complete. If it fails because global operation memory backend state was cached, reset `memory.operation_store.MEMORY_BACKEND = None` inside `reset_api_services()`.

- [ ] **Step 3: Commit integration test**

Run:

```powershell
git add tests/test_sqlite_queue_worker_integration.py
git commit -m "test: cover sqlite queue worker integration"
```

## Task 6: Update Progress Memory And Run Final Verification

**Files:**
- Modify: `memory/current_progress.md`
- Test: all touched files.

- [ ] **Step 1: Add progress entry**

Prepend this section under `# 当前工程进度` in `memory/current_progress.md`:

```markdown
## 2026-06-10 M16a SQLite 持久化队列与 worker 入口

本轮目标是在不引入 Redis/RQ/Celery 的前提下，把运行队列从 API 进程内存迁移到 SQLite，并新增独立 worker 脚本，为后续 API/worker 进程拆分铺路。

已完成：
- 新增 `SQLiteRunQueue`，通过 `run_queue_jobs` 表持久化队列任务。
- 保留 `LocalRunQueue` 默认行为，只有设置 `XHS_AGENT_RUN_QUEUE=sqlite` 时启用 SQLite 队列。
- API 提交流程仍创建 `queued` run，再写入队列；SQLite 队列模式下 API 不启动后台 worker 线程。
- 新增 `scripts/run_worker.py`，支持 worker 从 SQLite 队列领取任务并调用现有 `_execute_run(run_id)`。
- 队列支持入队去重、领取锁、成功完成、失败重试、终态失败和过期锁重新领取。
- `.env.example` 新增 SQLite 队列相关配置。

已验证：
- SQLite 队列单元测试通过。
- API 队列后端选择测试通过。
- worker 单步执行测试通过。
- SQLite 队列 + SQLite run store + mock LangGraph 集成测试通过。
- `python -m pytest -q` 通过。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。

当前阶段判断：
- API 和 worker 已具备分进程运行基础。
- SQLite 队列适合当前本地和轻量部署阶段。
- Redis/RQ/Celery、部署守护、鉴权、取消任务和前端队列管理仍不在本轮范围内。

建议下一步：
1. M16b：补启动说明和自测命令，明确 API 进程与 worker 进程如何分别启动。
2. M17：进入生产部署准备，补日志、进程守护和基础鉴权。
3. M18：在需要更高并发时再替换为 Redis/RQ 或 Celery。
```

- [ ] **Step 2: Run all tests**

Run:

```powershell
python -m pytest -q
```

Expected: PASS with all tests passing. A Windows pytest temp directory cleanup warning may appear after the pass summary; record it if it appears.

- [ ] **Step 3: Compile project modules**

Run:

```powershell
python -m compileall app nodes routers platforms memory scripts llm
```

Expected: PASS with directory listings and no syntax errors.

- [ ] **Step 4: Run smoke check with temporary DB**

Run:

```powershell
$env:XHS_AGENT_RUN_STORE='sqlite'
$env:XHS_AGENT_RUN_DB_PATH='data/tmp_queue_worker_check.sqlite3'
$env:XHS_AGENT_RUN_QUEUE='sqlite'
$env:XHS_AGENT_QUEUE_DB_PATH='data/tmp_queue_worker_check.sqlite3'
$env:XHS_AGENT_MEMORY_STORE='sqlite'
$env:XHS_AGENT_MEMORY_DB_PATH='data/tmp_queue_worker_check.sqlite3'
$env:COLLECTOR_MODE='mock'
$env:LLM_MODEL_NAME='mock'
python -c "from app import api; from scripts import run_worker; api.RUN_STORE=None; api.RUN_QUEUE_SERVICE=None; r=api.submit_run({'topic':'小红书新手选题方法','target_user':'内容创作新手','format':'image_text','engine':'langgraph','approve':False,'collect_limit':3}); print(r['status'], r['run_id']); print(api.queue_status()['queued_count']); did=run_worker.run_once(api._run_queue_service(), 'smoke-worker'); loaded=api._load_run(r['run_id']); print(did, loaded['status']); print(api.queue_status()['queued_count'], api.queue_status()['running_count'])"
```

Expected output:

```text
queued run_...
1
True success
0 0
```

- [ ] **Step 5: Remove temporary smoke DB files**

Run:

```powershell
$workspace=(Resolve-Path '.').Path
$targets=@(
  'data\tmp_queue_worker_check.sqlite3',
  'data\tmp_queue_worker_check.sqlite3-wal',
  'data\tmp_queue_worker_check.sqlite3-shm',
  'data\tmp_queue_worker_check.sqlite3-journal'
)
foreach ($relative in $targets) {
  $target=Join-Path $workspace $relative
  if (Test-Path -LiteralPath $target) {
    $resolved=(Resolve-Path -LiteralPath $target).Path
    if ($resolved.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) {
      Remove-Item -LiteralPath $resolved -Force
    } else {
      throw "Refusing to remove outside workspace: $resolved"
    }
  }
}
```

Expected: temp DB files are removed.

- [ ] **Step 6: Check git diff**

Run:

```powershell
git diff --check
git status --short --untracked-files=all
```

Expected: `git diff --check` has no whitespace errors. `git status` only shows intended M16a files before the final commit.

- [ ] **Step 7: Commit final docs and any remaining changes**

Run:

```powershell
git add memory/current_progress.md
git commit -m "docs: record sqlite run queue progress"
```

If all M16a changes are already committed by prior tasks and this is the only remaining file, this commit should include only `memory/current_progress.md`.

## Self-Review

- Spec coverage: Tasks cover `SQLiteRunQueue`, queue table, API backend selection, worker entry point, retry/failure rules, recovery, tests, env documentation, smoke check, and progress memory.
- Placeholder scan: no unfinished placeholders remain.
- Type consistency: `SQLiteRunQueue.claim_next(worker_id)`, `mark_succeeded(run_id, worker_id)`, and `mark_failed(run_id, worker_id, error)` names match the spec and test code.
- Scope check: no Redis/RQ/Celery, deployment, authentication, cancellation, priority, or frontend queue UI work is included.
