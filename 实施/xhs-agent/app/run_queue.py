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

from app.queue_events import record_queue_event_safely


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
        event_db_path: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.event_db_path = Path(event_db_path) if event_db_path is not None else None
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
        should_record_event = False
        event_payload: dict[str, Any] = {}
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                "SELECT status FROM run_queue_jobs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
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
            should_record_event = existing is None or existing["status"] == "failed"
            if existing is not None:
                event_payload["previous_status"] = existing["status"]
        if should_record_event:
            self._record_queue_event(
                run_id,
                "queue_enqueued",
                attempts=0,
                max_attempts=self._max_attempts,
                payload=event_payload,
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
                SELECT
                    run_id, status, attempts, max_attempts, locked_by,
                    heartbeat_at, last_error, created_at
                FROM run_queue_jobs
                WHERE status IN ('queued', 'running', 'failed', 'cancelled', 'timed_out')
                ORDER BY created_at ASC
                """
            ).fetchall()
        queued = [row["run_id"] for row in rows if row["status"] == "queued"]
        running = [row["run_id"] for row in rows if row["status"] == "running"]
        failed = [row["run_id"] for row in rows if row["status"] == "failed"]
        cancelled = [row["run_id"] for row in rows if row["status"] == "cancelled"]
        timed_out = [row["run_id"] for row in rows if row["status"] == "timed_out"]
        return {
            "queued_count": len(queued),
            "running_count": len(running),
            "queued_run_ids": queued,
            "running_run_ids": running,
            "failed_count": len(failed),
            "failed_run_ids": failed,
            "cancelled_count": len(cancelled),
            "cancelled_run_ids": cancelled,
            "timed_out_count": len(timed_out),
            "timed_out_run_ids": timed_out,
            "jobs": [
                {
                    "run_id": row["run_id"],
                    "status": row["status"],
                    "attempts": int(row["attempts"]),
                    "max_attempts": int(row["max_attempts"]),
                    "locked_by": row["locked_by"],
                    "heartbeat_at": row["heartbeat_at"],
                    "last_error": row["last_error"],
                }
                for row in rows
            ],
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
                    SELECT run_id, status, attempts, max_attempts, locked_at, locked_by
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
                event_type = "queue_reclaimed" if row["status"] == "running" else "queue_claimed"
                attempts = int(row["attempts"]) + 1
                max_attempts = int(row["max_attempts"])
                event_payload = {
                    "previous_status": row["status"],
                    "previous_locked_at": row["locked_at"],
                    "previous_locked_by": row["locked_by"],
                }
                connection.execute(
                    """
                    UPDATE run_queue_jobs
                    SET status = 'running',
                        attempts = attempts + 1,
                        locked_at = ?,
                        heartbeat_at = ?,
                        locked_by = ?,
                        updated_at = ?,
                        finished_at = NULL
                    WHERE run_id = ?
                    """,
                    (now, now, worker_id, now, run_id),
                )
                connection.commit()
                self._record_queue_event(
                    str(run_id),
                    event_type,
                    worker_id=worker_id,
                    attempts=attempts,
                    max_attempts=max_attempts,
                    payload=event_payload,
                )
                return str(run_id)
            except Exception:
                connection.rollback()
                raise

    def mark_succeeded(self, run_id: str, worker_id: str) -> None:
        now = _now_iso()
        attempts: int | None = None
        max_attempts: int | None = None
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT attempts, max_attempts FROM run_queue_jobs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row is not None:
                attempts = int(row["attempts"])
                max_attempts = int(row["max_attempts"])
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
        self._record_queue_event(
            run_id,
            "queue_succeeded",
            worker_id=worker_id,
            attempts=attempts,
            max_attempts=max_attempts,
        )

    def mark_failed(self, run_id: str, worker_id: str, error: str) -> bool:
        now = _now_iso()
        attempts: int | None = None
        max_attempts: int | None = None
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT attempts, max_attempts FROM run_queue_jobs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                self._record_queue_event(
                    run_id,
                    "queue_failed",
                    worker_id=worker_id,
                    error=error,
                    payload={"missing_queue_job": True},
                )
                return True
            attempts = int(row["attempts"])
            max_attempts = int(row["max_attempts"])
            terminal = attempts >= max_attempts
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
                event_type = "queue_failed"
            else:
                connection.execute(
                    """
                    UPDATE run_queue_jobs
                    SET status = 'queued',
                        available_at = ?,
                        locked_at = NULL,
                        heartbeat_at = NULL,
                        locked_by = NULL,
                        last_error = ?,
                        updated_at = ?,
                        finished_at = NULL
                    WHERE run_id = ?
                    """,
                    (now, error, now, run_id),
                )
                event_type = "queue_requeued"
        self._record_queue_event(
            run_id,
            event_type,
            worker_id=worker_id,
            attempts=attempts,
            max_attempts=max_attempts,
            error=error,
        )
        return terminal

    def heartbeat(self, run_id: str, worker_id: str) -> bool:
        clean_run_id = str(run_id or "").strip()
        clean_worker_id = str(worker_id or "").strip() or "worker"
        if not clean_run_id:
            return False

        now = _now_iso()
        attempts: int | None = None
        max_attempts: int | None = None
        previous_heartbeat_at: str | None = None
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT status, attempts, max_attempts, locked_by, heartbeat_at
                FROM run_queue_jobs
                WHERE run_id = ?
                """,
                (clean_run_id,),
            ).fetchone()
            if row is None:
                return False
            if row["status"] != "running" or row["locked_by"] != clean_worker_id:
                return False
            attempts = int(row["attempts"])
            max_attempts = int(row["max_attempts"])
            previous_heartbeat_at = row["heartbeat_at"]
            connection.execute(
                """
                UPDATE run_queue_jobs
                SET heartbeat_at = ?,
                    updated_at = ?
                WHERE run_id = ?
                """,
                (now, now, clean_run_id),
            )

        self._record_queue_event(
            clean_run_id,
            "queue_heartbeat",
            worker_id=clean_worker_id,
            attempts=attempts,
            max_attempts=max_attempts,
            payload={"previous_heartbeat_at": previous_heartbeat_at},
        )
        return True

    def mark_stale_running_as_timed_out(
        self,
        *,
        max_seconds: int,
        worker_id: str | None = "watchdog",
        reason: str | None = None,
        limit: int = 100,
    ) -> list[str]:
        timeout_seconds = max(1, _safe_int(max_seconds, 1))
        row_limit = max(1, _safe_int(limit, 100))
        threshold = (datetime.now() - timedelta(seconds=timeout_seconds)).isoformat(
            timespec="seconds"
        )
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id
                FROM run_queue_jobs
                WHERE status = 'running'
                  AND COALESCE(heartbeat_at, locked_at) IS NOT NULL
                  AND COALESCE(heartbeat_at, locked_at) < ?
                ORDER BY COALESCE(heartbeat_at, locked_at) ASC, created_at ASC
                LIMIT ?
                """,
                (threshold, row_limit),
            ).fetchall()

        timed_out: list[str] = []
        timeout_reason = reason or f"watchdog heartbeat timeout after {timeout_seconds} seconds"
        for row in rows:
            run_id = str(row["run_id"])
            if self.mark_timed_out(run_id, worker_id=worker_id, reason=timeout_reason):
                timed_out.append(run_id)
        return timed_out

    def cancel(self, run_id: str, worker_id: str | None = None, reason: str = "run cancelled") -> bool:
        return self._mark_terminal_control_state(
            run_id,
            status="cancelled",
            event_type="queue_cancelled",
            worker_id=worker_id,
            reason=reason,
        )

    def mark_timed_out(
        self,
        run_id: str,
        worker_id: str | None = None,
        reason: str = "run timed out",
    ) -> bool:
        return self._mark_terminal_control_state(
            run_id,
            status="timed_out",
            event_type="queue_timed_out",
            worker_id=worker_id,
            reason=reason,
        )

    def _mark_terminal_control_state(
        self,
        run_id: str,
        *,
        status: str,
        event_type: str,
        worker_id: str | None,
        reason: str,
    ) -> bool:
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id:
            return False
        operator = str(worker_id or "").strip() or None
        now = _now_iso()
        attempts: int | None = None
        max_attempts: int | None = None
        previous_status: str | None = None
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT status, attempts, max_attempts, locked_by
                FROM run_queue_jobs
                WHERE run_id = ?
                """,
                (clean_run_id,),
            ).fetchone()
            if row is None:
                return False
            previous_status = str(row["status"])
            if previous_status in {"succeeded", "failed", "cancelled", "timed_out"}:
                return False
            attempts = int(row["attempts"])
            max_attempts = int(row["max_attempts"])
            connection.execute(
                """
                UPDATE run_queue_jobs
                SET status = ?,
                    locked_by = COALESCE(?, locked_by),
                    last_error = ?,
                    updated_at = ?,
                    finished_at = ?
                WHERE run_id = ?
                """,
                (status, operator, reason, now, now, clean_run_id),
            )

        self._record_queue_event(
            clean_run_id,
            event_type,
            worker_id=operator,
            attempts=attempts,
            max_attempts=max_attempts,
            error=reason,
            payload={"previous_status": previous_status},
        )
        return True

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
                    heartbeat_at TEXT,
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
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(run_queue_jobs)").fetchall()
            }
            if "heartbeat_at" not in columns:
                connection.execute("ALTER TABLE run_queue_jobs ADD COLUMN heartbeat_at TEXT")
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_run_queue_jobs_heartbeat_at
                ON run_queue_jobs(heartbeat_at)
                """
            )

    def _record_queue_event(
        self,
        run_id: str,
        event_type: str,
        *,
        worker_id: str | None = None,
        attempts: int | None = None,
        max_attempts: int | None = None,
        error: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        record_queue_event_safely(
            self.event_db_path,
            run_id=run_id,
            event_type=event_type,
            worker_id=worker_id,
            attempts=attempts,
            max_attempts=max_attempts,
            error=error,
            payload=payload,
        )
