from __future__ import annotations

from app import creator_performance_scheduler as scheduler


def test_schedule_runs_multiple_rounds_and_sleeps_between_rounds() -> None:
    calls: list[dict] = []
    sleeps: list[float] = []

    def fake_sync(**kwargs) -> dict:
        calls.append(kwargs)
        return {"total": 2, "succeeded": 2, "failed": 0, "results": []}

    result = scheduler.run_creator_performance_sync_schedule(
        targets=[{"creator_note_id": "note_a"}, {"run_id": "run_a"}],
        sync_runner=fake_sync,
        sleep=sleeps.append,
        schedule_interval_seconds=30,
        max_rounds=2,
        limit=20,
        wait=True,
        attempts=3,
        status_interval_seconds=0.5,
        notes="scheduled sync",
    )

    assert len(calls) == 2
    assert sleeps == [30]
    assert calls[0] == {
        "targets": [{"creator_note_id": "note_a"}, {"run_id": "run_a"}],
        "limit": 20,
        "wait": True,
        "attempts": 3,
        "interval_seconds": 0.5,
        "notes": "scheduled sync",
    }
    assert result["ok"] is True
    assert result["completed_rounds"] == 2
    assert result["total_succeeded"] == 4
    assert result["total_failed"] == 0
    assert result["stopped_reason"] == "max_rounds"


def test_schedule_stops_after_consecutive_failed_rounds() -> None:
    calls = 0

    def fake_sync(**kwargs) -> dict:
        nonlocal calls
        calls += 1
        return {"total": 1, "succeeded": 0, "failed": 1, "results": []}

    result = scheduler.run_creator_performance_sync_schedule(
        targets=[{"creator_note_id": "note_failed"}],
        sync_runner=fake_sync,
        sleep=lambda seconds: None,
        schedule_interval_seconds=0,
        max_rounds=5,
        max_consecutive_failed_rounds=2,
    )

    assert calls == 2
    assert result["ok"] is False
    assert result["completed_rounds"] == 2
    assert result["consecutive_failed_rounds"] == 2
    assert result["stopped_reason"] == "failure_limit"


def test_schedule_records_runner_exception_as_failed_round() -> None:
    def fake_sync(**kwargs) -> dict:
        raise RuntimeError("creator unavailable")

    result = scheduler.run_creator_performance_sync_schedule(
        targets=[{"creator_note_id": "note_exception"}],
        sync_runner=fake_sync,
        sleep=lambda seconds: None,
        schedule_interval_seconds=0,
        max_rounds=1,
    )

    assert result["ok"] is False
    assert result["rounds"][0]["ok"] is False
    assert result["rounds"][0]["failed"] == 1
    assert "creator unavailable" in result["rounds"][0]["error"]


def test_schedule_requires_targets() -> None:
    try:
        scheduler.run_creator_performance_sync_schedule(
            targets=[],
            sync_runner=lambda **kwargs: {},
            sleep=lambda seconds: None,
            max_rounds=1,
        )
    except ValueError as exc:
        assert "targets" in str(exc)
    else:
        raise AssertionError("expected ValueError")
