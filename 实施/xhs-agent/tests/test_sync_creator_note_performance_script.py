from __future__ import annotations

import json

from scripts import sync_creator_note_performance as script


def test_main_accepts_creator_note_id_and_prints_sync_result(monkeypatch, capsys) -> None:
    def fake_sync(**kwargs) -> dict:
        assert kwargs == {
            "creator_note_id": "note_script_001",
            "run_id": "",
            "limit": 40,
            "wait": True,
            "attempts": 6,
            "interval_seconds": 0.2,
            "notes": "script sync",
        }
        return {
            "synced": True,
            "performance_result": {"business_sync": {"status": "success"}},
        }

    monkeypatch.setattr(script.api, "sync_creator_note_performance", fake_sync, raising=False)

    exit_code = script.main(
        [
            "--creator-note-id",
            "note_script_001",
            "--limit",
            "40",
            "--wait",
            "--attempts",
            "6",
            "--interval-seconds",
            "0.2",
            "--notes",
            "script sync",
        ]
    )
    data = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert data["ok"] is True
    assert data["synced"] is True


def test_main_accepts_run_id_and_mode(monkeypatch, capsys) -> None:
    captured_env: dict[str, str | None] = {}

    def fake_sync(**kwargs) -> dict:
        captured_env["CREATOR_MODE"] = script.os.environ.get("CREATOR_MODE")
        assert kwargs["run_id"] == "run_script_001"
        assert kwargs["creator_note_id"] == ""
        return {
            "synced": True,
            "performance_result": {"business_sync": {"status": "success"}},
        }

    monkeypatch.setattr(script.api, "sync_creator_note_performance", fake_sync, raising=False)

    exit_code = script.main(["--run-id", "run_script_001", "--mode", "spider_xhs"])
    data = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert data["ok"] is True
    assert captured_env["CREATOR_MODE"] == "spider_xhs"


def test_main_returns_error_when_sync_fails(monkeypatch, capsys) -> None:
    def fake_sync(**kwargs) -> dict:
        raise ValueError("creator note is not synced")

    monkeypatch.setattr(script.api, "sync_creator_note_performance", fake_sync, raising=False)

    exit_code = script.main(["--creator-note-id", "missing_note"])
    data = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert data["ok"] is False
    assert "creator note is not synced" in data["error"]
