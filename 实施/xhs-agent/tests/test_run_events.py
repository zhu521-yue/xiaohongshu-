from __future__ import annotations

import sqlite3
from pathlib import Path

from app.run_events import record_run_event


def _rows(db_path: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute("SELECT * FROM run_events ORDER BY created_at, event_type").fetchall()


def test_record_run_event_writes_lifecycle_event_idempotently(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"

    record_run_event(
        db_path,
        run_id="run_events_001",
        event_type="queued",
        status="queued",
        message="run queued",
        created_at="2026-06-12T13:00:00",
    )
    record_run_event(
        db_path,
        run_id="run_events_001",
        event_type="queued",
        status="queued",
        message="run queued again",
        created_at="2026-06-12T13:00:00",
    )

    rows = _rows(db_path)
    assert len(rows) == 1
    assert rows[0]["run_id"] == "run_events_001"
    assert rows[0]["event_type"] == "queued"
    assert rows[0]["status"] == "queued"
    assert rows[0]["message"] == "run queued again"


def test_record_run_event_writes_node_duration_and_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"

    record_run_event(
        db_path,
        run_id="run_events_002",
        event_type="node_finished",
        node_name="load_user_input",
        status="success",
        started_at="2026-06-12T13:00:00",
        finished_at="2026-06-12T13:00:01",
        duration_ms=1000,
        payload={"updates": ["user_topic"]},
        created_at="2026-06-12T13:00:01",
    )

    row = _rows(db_path)[0]
    assert row["event_type"] == "node_finished"
    assert row["node_name"] == "load_user_input"
    assert row["duration_ms"] == 1000
    assert '"updates"' in row["payload_json"]
