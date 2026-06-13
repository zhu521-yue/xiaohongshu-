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
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row[0] for row in rows}


def _index_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()
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
