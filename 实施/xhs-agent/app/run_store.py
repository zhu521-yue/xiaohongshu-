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
