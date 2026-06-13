from __future__ import annotations

import json

from scripts import run_creator_performance_scheduler as script


def test_main_parses_targets_and_runs_scheduler(monkeypatch, capsys) -> None:
    captured: dict = {}

    def fake_schedule(**kwargs) -> dict:
        captured.update(kwargs)
        return {
            "ok": True,
            "completed_rounds": 1,
            "total_succeeded": 2,
            "total_failed": 0,
            "stopped_reason": "max_rounds",
            "rounds": [],
        }

    monkeypatch.setattr(script.scheduler, "run_creator_performance_sync_schedule", fake_schedule, raising=False)
    monkeypatch.setattr(script.time, "sleep", lambda seconds: None, raising=False)

    exit_code = script.main(
        [
            "--creator-note-id",
            "note_a",
            "--run-id",
            "run_a",
            "--mode",
            "mock",
            "--schedule-interval-seconds",
            "10",
            "--max-rounds",
            "1",
            "--max-consecutive-failed-rounds",
            "2",
            "--limit",
            "25",
            "--wait",
            "--attempts",
            "4",
            "--status-interval-seconds",
            "0.2",
            "--notes",
            "scheduler note",
        ]
    )
    data = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert data["ok"] is True
    assert script.os.environ["CREATOR_MODE"] == "mock"
    assert captured["targets"] == [{"creator_note_id": "note_a"}, {"run_id": "run_a"}]
    assert captured["sync_runner"] is script.api.sync_creator_note_performance_batch
    assert captured["sleep"] is script.time.sleep
    assert captured["schedule_interval_seconds"] == 10
    assert captured["max_rounds"] == 1
    assert captured["max_consecutive_failed_rounds"] == 2
    assert captured["limit"] == 25
    assert captured["wait"] is True
    assert captured["attempts"] == 4
    assert captured["status_interval_seconds"] == 0.2
    assert captured["notes"] == "scheduler note"


def test_main_returns_non_zero_when_scheduler_reports_failure(monkeypatch, capsys) -> None:
    def fake_schedule(**kwargs) -> dict:
        return {
            "ok": False,
            "completed_rounds": 2,
            "total_succeeded": 0,
            "total_failed": 2,
            "stopped_reason": "failure_limit",
            "rounds": [],
        }

    monkeypatch.setattr(script.scheduler, "run_creator_performance_sync_schedule", fake_schedule, raising=False)

    exit_code = script.main(["--creator-note-id", "note_failed", "--max-rounds", "1"])
    data = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert data["ok"] is False
    assert data["stopped_reason"] == "failure_limit"
