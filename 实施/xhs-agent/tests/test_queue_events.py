from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.queue_events import record_queue_event


def _rows(db_path: Path, run_id: str) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            "SELECT * FROM run_events WHERE run_id = ? ORDER BY created_at, event_type",
            (run_id,),
        ).fetchall()


def test_record_queue_event_writes_worker_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"

    record_queue_event(
        db_path,
        run_id="run_queue_event_001",
        event_type="queue_claimed",
        worker_id="worker-a",
        attempts=2,
        max_attempts=3,
        message="queue job claimed",
        created_at="2026-06-12T16:00:00",
    )

    row = _rows(db_path, "run_queue_event_001")[0]
    payload = json.loads(row["payload_json"])
    assert row["event_type"] == "queue_claimed"
    assert row["status"] == "running"
    assert row["message"] == "queue job claimed"
    assert payload["worker_id"] == "worker-a"
    assert payload["attempts"] == 2
    assert payload["max_attempts"] == 3
