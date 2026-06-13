from __future__ import annotations

import pytest

from app import creator_performance_sync as service


def test_sync_creator_note_performance_records_metrics_snapshot() -> None:
    captured_payloads: list[dict] = []

    def fake_status_reader(
        creator_note_id: str,
        limit: int = 50,
        wait: bool = False,
        attempts: int = 5,
        interval_seconds: float = 2.0,
    ) -> dict:
        assert creator_note_id == "note_sync_001"
        assert limit == 30
        assert wait is True
        assert attempts == 4
        assert interval_seconds == 0.5
        return {
            "creator_note_status": {
                "ok": True,
                "status": "synced",
                "creator_note_id": creator_note_id,
                "metrics_snapshot": {
                    "views": "123",
                    "likes": "9",
                    "collects": "4",
                    "comments": "2",
                },
            }
        }

    def fake_recorder(payload: dict) -> dict:
        captured_payloads.append(payload)
        return {
            "updated_record": {
                "creator_note_id": payload["creator_note_id"],
                "performance_data": {
                    key: payload[key]
                    for key in ("views", "likes", "collects", "comments", "follows")
                },
            },
            "business_sync": {"status": "success", "run_id": "run_sync_001"},
        }

    result = service.sync_creator_note_performance(
        creator_note_id="note_sync_001",
        limit=30,
        wait=True,
        attempts=4,
        interval_seconds=0.5,
        notes="platform auto sync",
        status_reader=fake_status_reader,
        performance_recorder=fake_recorder,
    )

    assert result["synced"] is True
    assert result["resolved_target"] == {
        "creator_note_id": "note_sync_001",
        "run_id": "",
        "source": "request",
    }
    assert captured_payloads == [
        {
            "creator_note_id": "note_sync_001",
            "views": 123,
            "likes": 9,
            "collects": 4,
            "comments": 2,
            "follows": 0,
            "notes": "platform auto sync",
        }
    ]
    assert result["performance_result"]["business_sync"]["status"] == "success"


def test_sync_creator_note_performance_resolves_note_from_run_state() -> None:
    def fake_run_loader(run_id: str) -> dict:
        assert run_id == "run_sync_002"
        return {
            "state": {"creator_note_id": "note_from_state"},
            "summary": {"creator_note_id": "note_from_summary"},
        }

    def fake_status_reader(**kwargs) -> dict:
        return {
            "creator_note_status": {
                "ok": True,
                "status": "synced",
                "creator_note_id": kwargs["creator_note_id"],
                "metrics_snapshot": {"views": 1},
            }
        }

    result = service.sync_creator_note_performance(
        run_id="run_sync_002",
        run_loader=fake_run_loader,
        status_reader=fake_status_reader,
        performance_recorder=lambda payload: {"updated_record": payload},
    )

    assert result["resolved_target"] == {
        "creator_note_id": "note_from_state",
        "run_id": "run_sync_002",
        "source": "run_state",
    }
    assert result["performance_payload"]["creator_note_id"] == "note_from_state"


def test_sync_creator_note_performance_rejects_unsynced_status_without_recording() -> None:
    recorded = False

    def fake_status_reader(**kwargs) -> dict:
        return {
            "creator_note_status": {
                "ok": False,
                "status": "not_found",
                "creator_note_id": kwargs["creator_note_id"],
                "error": "not found",
            }
        }

    def fake_recorder(payload: dict) -> dict:
        nonlocal recorded
        recorded = True
        return {}

    with pytest.raises(ValueError, match="creator note is not synced"):
        service.sync_creator_note_performance(
            creator_note_id="missing_note",
            status_reader=fake_status_reader,
            performance_recorder=fake_recorder,
        )

    assert recorded is False


def test_resolve_creator_note_id_requires_note_or_run() -> None:
    with pytest.raises(ValueError, match="creator_note_id or run_id"):
        service.resolve_creator_note_id()


def test_batch_sync_continues_after_single_target_failure() -> None:
    recorded_payloads: list[dict] = []

    def fake_run_loader(run_id: str) -> dict | None:
        if run_id == "run_batch_001":
            return {"state": {"creator_note_id": "note_from_run"}}
        return None

    def fake_status_reader(**kwargs) -> dict:
        note_id = kwargs["creator_note_id"]
        if note_id == "note_missing":
            return {
                "creator_note_status": {
                    "ok": False,
                    "status": "not_found",
                    "creator_note_id": note_id,
                }
            }
        return {
            "creator_note_status": {
                "ok": True,
                "status": "synced",
                "creator_note_id": note_id,
                "metrics_snapshot": {"views": 10 if note_id == "note_direct" else 20},
            }
        }

    def fake_recorder(payload: dict) -> dict:
        recorded_payloads.append(payload)
        return {"updated_record": {"creator_note_id": payload["creator_note_id"]}}

    result = service.sync_creator_note_performance_batch(
        targets=[
            {"creator_note_id": "note_direct"},
            {"run_id": "run_batch_001"},
            {"creator_note_id": "note_missing"},
        ],
        limit=15,
        wait=True,
        attempts=2,
        interval_seconds=0.1,
        notes="batch sync",
        run_loader=fake_run_loader,
        status_reader=fake_status_reader,
        performance_recorder=fake_recorder,
    )

    assert result["total"] == 3
    assert result["succeeded"] == 2
    assert result["failed"] == 1
    assert [item["ok"] for item in result["results"]] == [True, True, False]
    assert [payload["creator_note_id"] for payload in recorded_payloads] == [
        "note_direct",
        "note_from_run",
    ]
    assert recorded_payloads[0]["notes"] == "batch sync"


def test_summarize_performance_trends_uses_recent_performance_records() -> None:
    records = [
        {
            "record_id": "op_low",
            "title": "low",
            "creator_note_id": "note_low",
            "status": "performance_recorded",
            "updated_at": "2026-06-13T10:00:00",
            "performance_data": {
                "views": 100,
                "likes": 2,
                "collects": 1,
                "comments": 0,
                "follows": 0,
            },
            "performance_score": 5,
        },
        {
            "record_id": "op_high",
            "title": "high",
            "creator_note_id": "note_high",
            "status": "performance_recorded",
            "updated_at": "2026-06-13T11:00:00",
            "performance_data": {
                "views": 300,
                "likes": 10,
                "collects": 8,
                "comments": 4,
                "follows": 1,
            },
            "performance_score": 30,
        },
        {
            "record_id": "op_draft",
            "status": "draft_saved",
            "performance_data": {},
            "performance_score": 0,
        },
    ]

    summary = service.summarize_performance_trends(records, limit=5)

    assert summary["record_count"] == 2
    assert summary["totals"] == {
        "views": 400,
        "likes": 12,
        "collects": 9,
        "comments": 4,
        "follows": 1,
    }
    assert summary["averages"]["views"] == 200
    assert summary["top_records"][0]["record_id"] == "op_high"
    assert summary["recent_records"][0]["record_id"] == "op_high"
    assert summary["score"] == {"min": 5, "max": 30, "average": 17.5}
