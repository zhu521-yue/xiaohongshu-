"""Local task queue boundary.

This is still an in-process queue, but the API layer no longer owns the queue
implementation. A Redis/Celery backend can later implement the same public
methods and replace this class.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from queue import Queue
from typing import Any, Callable


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class LocalRunQueue:
    def __init__(
        self,
        execute_run: Callable[[str], None],
        list_runs: Callable[[int], list[dict[str, Any]]],
        worker_count: int = 1,
    ) -> None:
        self._execute_run = execute_run
        self._list_runs = list_runs
        self._worker_count = max(1, int(worker_count or 1))
        self._queue: Queue[str] = Queue()
        self._lock = threading.RLock()
        self._enqueued_run_ids: set[str] = set()
        self._started_workers = 0

    def enqueue(self, run_id: str) -> None:
        with self._lock:
            if run_id in self._enqueued_run_ids:
                return
            self._enqueued_run_ids.add(run_id)
            self._queue.put(run_id)
            self._ensure_workers_started()

    def recover_pending_runs(self) -> None:
        pending = [
            run
            for run in self._list_runs(10000)
            if run.get("status") in {"queued", "running"}
        ]
        pending.sort(key=lambda item: str(item.get("created_at") or ""))
        for run in pending:
            run_id = str(run.get("run_id") or "")
            if run_id:
                self.enqueue(run_id)

    def status(self) -> dict[str, Any]:
        runs = self._list_runs(10000)
        queued = [run for run in runs if run.get("status") == "queued"]
        running = [run for run in runs if run.get("status") == "running"]
        return {
            "queued_count": len(queued),
            "running_count": len(running),
            "queued_run_ids": [
                run.get("run_id")
                for run in sorted(queued, key=lambda item: str(item.get("created_at") or ""))
            ],
            "running_run_ids": [run.get("run_id") for run in running],
            "worker_backend": "local",
            "worker_count": self._worker_count,
        }

    def _ensure_workers_started(self) -> None:
        while self._started_workers < self._worker_count:
            index = self._started_workers + 1
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"xhs-agent-worker-{index}",
                daemon=True,
            )
            worker.start()
            self._started_workers += 1

    def _worker_loop(self) -> None:
        while True:
            run_id = self._queue.get()
            try:
                self._execute_run(run_id)
            finally:
                with self._lock:
                    self._enqueued_run_ids.discard(run_id)
                self._queue.task_done()


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
        pending = [
            run
            for run in self._list_runs(10000)
            if run.get("status") in {"queued", "running"}
        ]
        pending.sort(key=lambda item: str(item.get("created_at") or ""))
        for run in pending:
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
        stale_before = (now_dt - timedelta(seconds=self._lock_timeout_seconds)).isoformat(
            timespec="seconds"
        )
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
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
                    connection.commit()
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
                connection.commit()
                return str(run_id)
            except Exception:
                connection.rollback()
                raise

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
