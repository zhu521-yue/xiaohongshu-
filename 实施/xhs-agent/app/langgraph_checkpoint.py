from __future__ import annotations

import pickle
import sqlite3
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver


class SQLiteSnapshotSaver(InMemorySaver):
    """SQLite-backed snapshot wrapper for LangGraph checkpoint state."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._snapshot_lock = threading.RLock()
        super().__init__()
        self._init_db()
        self._load_snapshot()

    def put(self, config, checkpoint, metadata, new_versions):
        result = super().put(config, checkpoint, metadata, new_versions)
        self._persist_snapshot()
        return result

    def put_writes(self, config, writes, task_id: str, task_path: str = "") -> None:
        super().put_writes(config, writes, task_id, task_path)
        self._persist_snapshot()

    def delete_thread(self, thread_id: str) -> None:
        super().delete_thread(thread_id)
        self._persist_snapshot()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path, timeout=30) as connection:
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS langgraph_checkpoint_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    payload BLOB NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _load_snapshot(self) -> None:
        with self._snapshot_lock, sqlite3.connect(self.db_path, timeout=30) as connection:
            row = connection.execute(
                "SELECT payload FROM langgraph_checkpoint_snapshots WHERE snapshot_id = 'default'"
            ).fetchone()
        if row is None:
            return

        payload = pickle.loads(row[0])
        self.storage = defaultdict(lambda: defaultdict(dict))
        for thread_id, namespaces in payload.get("storage", {}).items():
            self.storage[thread_id] = defaultdict(dict, namespaces)
        self.writes = defaultdict(dict, payload.get("writes", {}))
        self.blobs = payload.get("blobs", {})

    def _persist_snapshot(self) -> None:
        payload: dict[str, Any] = {
            "storage": {thread_id: dict(namespaces) for thread_id, namespaces in self.storage.items()},
            "writes": dict(self.writes),
            "blobs": dict(self.blobs),
        }
        encoded = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        with self._snapshot_lock, sqlite3.connect(self.db_path, timeout=30) as connection:
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute(
                """
                INSERT INTO langgraph_checkpoint_snapshots (snapshot_id, payload, updated_at)
                VALUES ('default', ?, ?)
                ON CONFLICT(snapshot_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (encoded, now),
            )
