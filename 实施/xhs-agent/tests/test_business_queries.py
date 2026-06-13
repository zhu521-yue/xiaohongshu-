from __future__ import annotations

from pathlib import Path

from app.business_queries import get_business_run_snapshot
from app.business_store import sync_run_business_tables
from app.run_events import record_run_event
from app.run_store import SQLiteRunStore


def _save_run(db_path: Path, record: dict) -> None:
    SQLiteRunStore(db_path).save(record)


def _record(tmp_path: Path) -> dict:
    asset_path = tmp_path / "creator_assets" / "run_query_001" / "01_cover.png"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(b"\x89PNG\r\n\x1a\nquery-image")
    return {
        "run_id": "run_query_001",
        "status": "success",
        "created_at": "2026-06-12T12:00:00",
        "updated_at": "2026-06-12T12:05:00",
        "finished_at": "2026-06-12T12:05:00",
        "review_action": "approved",
        "request": {"topic": "小红书新手选题方法"},
        "summary": {},
        "content": {
            "titles": ["查询测试标题"],
            "body": "查询测试正文",
            "tags": ["小红书运营"],
            "image_prompts": ["查询测试图片"],
        },
        "insights": {},
        "paths": {"post_id": "output/query.md"},
        "error": None,
        "state": {
            "user_topic": "小红书新手选题方法",
            "content_format": "image_text",
            "content_type": "step_tutorial",
            "titles": ["查询测试标题"],
            "body": "查询测试正文",
            "tags": ["小红书运营"],
            "image_prompts": ["查询测试图片"],
            "post_id": "output/query.md",
            "publish_status": "success",
            "human_approved": True,
            "operation_record_id": "op_query_001",
            "operation_memory_written": True,
            "creator_image_files": [str(asset_path)],
            "creator_publish_requested": True,
            "creator_publish_status": "success",
            "creator_publish_mode": "mock",
            "creator_note_id": "mock_query_note_001",
            "creator_publish_result": {
                "ok": True,
                "mode": "mock",
                "platform": "xhs_creator",
                "visibility": "private",
                "note_id": "mock_query_note_001",
            },
            "raw_notes": [{"id": "note_query_001", "title": "查询测试笔记", "likes": 7}],
            "collection_candidates": [
                {
                    "rank": 1,
                    "selected": True,
                    "original_index": 0,
                    "title": "查询测试笔记",
                    "score": 88,
                }
            ],
            "raw_comments": [{"source_note_title": "查询测试笔记", "content": "怎么查询？"}],
            "analysis_report": {
                "sample_selection": {"candidate_count": 1, "selected_count": 1},
                "comment_quality": {"raw_comments_count": 1, "quality_level": "low"},
                "pain_point_confidence": {"level": "low", "score": 20},
                "summary": "查询测试报告",
            },
        },
    }


def test_get_business_run_snapshot_returns_foundation_table_summary(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    record = _record(tmp_path)
    _save_run(db_path, record)
    sync_run_business_tables(db_path, record)
    record_run_event(
        db_path,
        run_id="run_query_001",
        event_type="queued",
        status="queued",
        message="run queued",
        created_at="2026-06-12T12:00:00",
    )

    snapshot = get_business_run_snapshot(db_path, "run_query_001")

    assert snapshot["run_id"] == "run_query_001"
    assert snapshot["counts"] == {
        "raw_notes": 1,
        "collection_candidates": 1,
        "raw_comments": 1,
        "analysis_reports": 1,
        "drafts": 1,
        "creator_assets": 1,
        "creator_notes": 1,
        "performance_records": 0,
        "audit_events": 3,
        "run_events": 1,
    }
    assert snapshot["raw_notes"][0]["title"] == "查询测试笔记"
    assert snapshot["collection_candidates"][0]["score"] == 88
    assert snapshot["analysis_reports"][0]["summary"] == "查询测试报告"
    assert snapshot["drafts"][0]["title"] == "查询测试标题"
    assert snapshot["creator_assets"][0]["file_name"] == "01_cover.png"
    assert snapshot["creator_notes"][0]["creator_note_id"] == "mock_query_note_001"
    assert {event["action"] for event in snapshot["audit_events"]} == {
        "human_review",
        "creator_publish",
        "operation_memory_write",
    }
    assert snapshot["run_events"][0]["event_type"] == "queued"
    assert snapshot["run_events"][0]["message"] == "run queued"


def test_get_business_run_snapshot_returns_empty_lists_for_unknown_run(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    snapshot = get_business_run_snapshot(db_path, "run_missing")

    assert snapshot["run_id"] == "run_missing"
    assert all(count == 0 for count in snapshot["counts"].values())
    assert snapshot["drafts"] == []


def test_get_business_run_snapshot_sorts_mixed_timezone_run_events_by_timeline_order(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    events = [
        ("queued", "2026-06-12T23:19:48"),
        ("queue_enqueued", "2026-06-12T15:19:48.230212+00:00"),
        ("queue_claimed", "2026-06-12T15:19:48.866333+00:00"),
        ("running", "2026-06-12T23:19:48"),
        ("success", "2026-06-12T23:19:48"),
        ("queue_succeeded", "2026-06-12T15:19:49.046011+00:00"),
    ]
    for event_type, created_at in events:
        record_run_event(
            db_path,
            run_id="run_mixed_timeline",
            event_type=event_type,
            status=event_type,
            message=event_type,
            created_at=created_at,
        )

    snapshot = get_business_run_snapshot(db_path, "run_mixed_timeline")

    assert [event["event_type"] for event in snapshot["run_events"]] == [
        "queued",
        "queue_enqueued",
        "queue_claimed",
        "running",
        "success",
        "queue_succeeded",
    ]
