"""Read-only queries for foundation business tables."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.database_schema import initialize_foundation_schema


BUSINESS_TABLES = (
    "run_events",
    "raw_notes",
    "collection_candidates",
    "raw_comments",
    "analysis_reports",
    "drafts",
    "creator_assets",
    "creator_notes",
    "performance_records",
    "audit_events",
)

TABLE_ORDERING = {
    "run_events": "created_at ASC, event_type ASC",
    "raw_notes": "collected_at ASC, title ASC",
    "collection_candidates": "rank ASC, candidate_id ASC",
    "raw_comments": "collected_at ASC, comment_row_id ASC",
    "analysis_reports": "created_at ASC",
    "drafts": "created_at ASC",
    "creator_assets": "bound_order ASC, asset_id ASC",
    "creator_notes": "created_at ASC",
    "performance_records": "recorded_at ASC, performance_id ASC",
    "audit_events": "created_at ASC, action ASC",
}

TABLE_COLUMNS = {
    "run_events": (
        "event_id",
        "event_type",
        "node_name",
        "status",
        "message",
        "error",
        "started_at",
        "finished_at",
        "duration_ms",
        "payload_json",
        "created_at",
    ),
    "raw_notes": (
        "note_row_id",
        "source_note_id",
        "title",
        "note_url",
        "note_type",
        "likes",
        "collects",
        "comments",
        "shares",
        "collected_at",
    ),
    "collection_candidates": (
        "candidate_id",
        "note_row_id",
        "rank",
        "selected",
        "score",
        "title",
        "note_url",
        "reasons_json",
        "penalties_json",
        "score_breakdown_json",
        "created_at",
    ),
    "raw_comments": (
        "comment_row_id",
        "note_row_id",
        "source_note_title",
        "content",
        "like_count",
        "kept",
        "noise_reason",
        "collected_at",
    ),
    "analysis_reports": (
        "report_id",
        "candidate_count",
        "selected_count",
        "raw_comments_count",
        "evidence_count",
        "comment_quality_level",
        "pain_point_confidence_level",
        "pain_point_confidence_score",
        "recommended_type",
        "risks_json",
        "summary",
        "created_at",
        "updated_at",
    ),
    "drafts": (
        "draft_id",
        "operation_record_id",
        "topic",
        "content_format",
        "content_type",
        "title",
        "titles_json",
        "body",
        "tags_json",
        "comment_call",
        "markdown_path",
        "status",
        "created_at",
        "updated_at",
    ),
    "creator_assets": (
        "asset_id",
        "draft_id",
        "source",
        "provider",
        "model",
        "file_path",
        "file_name",
        "mime_type",
        "file_size",
        "prompt",
        "bound_order",
        "status",
        "created_at",
        "updated_at",
    ),
    "creator_notes": (
        "creator_note_id",
        "operation_record_id",
        "draft_id",
        "title",
        "publish_mode",
        "publish_status",
        "visibility_label",
        "permission_code",
        "tab_status",
        "platform_type",
        "metrics_snapshot_json",
        "last_sync_status",
        "last_synced_at",
        "created_at",
        "updated_at",
    ),
    "performance_records": (
        "performance_id",
        "operation_record_id",
        "creator_note_id",
        "views",
        "likes",
        "collects",
        "comments",
        "follows",
        "performance_score",
        "source",
        "notes",
        "recorded_at",
        "created_at",
    ),
    "audit_events": (
        "audit_id",
        "operation_record_id",
        "actor",
        "action",
        "target_type",
        "target_id",
        "result",
        "message",
        "payload_json",
        "created_at",
    ),
}

JSON_FIELDS = {
    "reasons_json",
    "penalties_json",
    "score_breakdown_json",
    "risks_json",
    "titles_json",
    "tags_json",
    "metrics_snapshot_json",
    "payload_json",
}


def get_business_run_snapshot(db_path: str | Path, run_id: str) -> dict[str, Any]:
    """Return a compact read-only snapshot from foundation business tables."""

    clean_run_id = str(run_id or "").strip()
    if not clean_run_id:
        raise ValueError("run_id is required")

    path = initialize_foundation_schema(db_path)
    snapshot: dict[str, Any] = {
        "run_id": clean_run_id,
        "db_path": str(path),
        "counts": {},
    }

    with sqlite3.connect(path, timeout=30) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        for table in BUSINESS_TABLES:
            rows = _query_table(connection, table, clean_run_id)
            snapshot[table] = rows
            snapshot["counts"][table] = len(rows)

    return snapshot


def _query_table(connection: sqlite3.Connection, table: str, run_id: str) -> list[dict[str, Any]]:
    columns = TABLE_COLUMNS[table]
    if table == "run_events":
        sql = f"SELECT rowid AS _rowid, {', '.join(columns)} FROM {table} WHERE run_id = ? ORDER BY rowid ASC"
        rows = connection.execute(sql, (run_id,)).fetchall()
        items = [_row_to_dict(row) for row in rows]
        items.sort(key=_run_event_sort_key)
        for item in items:
            item.pop("_rowid", None)
        return items

    order_by = TABLE_ORDERING[table]
    sql = f"SELECT {', '.join(columns)} FROM {table} WHERE run_id = ? ORDER BY {order_by}"
    rows = connection.execute(sql, (run_id,)).fetchall()
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    for key, value in list(item.items()):
        if key in JSON_FIELDS:
            item[key[:-5] if key.endswith("_json") else key] = _json_loads(value)
            del item[key]
        elif key in {"selected", "kept"}:
            item[key] = bool(value)
    return item


def _json_loads(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return [] if value == "[]" else {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _run_event_sort_key(item: dict[str, Any]) -> tuple[datetime, int, str]:
    return (
        _local_second(item.get("created_at")),
        int(item.get("_rowid") or 0),
        str(item.get("event_type") or ""),
    )


def _local_second(value: Any) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.max
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed.replace(microsecond=0)
