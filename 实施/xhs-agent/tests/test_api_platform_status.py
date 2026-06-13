from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import api


def _start_test_server(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(api, "RUNS_DIR", tmp_path / "runs")
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    server = ThreadingHTTPServer(("127.0.0.1", 0), api.XHSAgentAPIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        api.RUN_STORE = None
        api.RUN_QUEUE_SERVICE = None


def _read_json(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    request = Request(url, headers=headers or {})
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _post_json(
    url: str,
    payload: dict,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict]:
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_platform_status_returns_runtime_and_guardrail_state(monkeypatch) -> None:
    collector_runtime = {
        "ok": True,
        "mode": "mock",
        "platform": "mock_collector",
    }
    creator_runtime = {
        "ok": False,
        "mode": "spider_xhs",
        "platform": "xhs_creator",
        "error": "XHS_CREATOR_COOKIES is required",
    }
    creator_guardrail = {
        "allowed": False,
        "reason": "creator daily limit reached: 3/3",
        "date": "2026-06-12",
        "success_count": 3,
        "daily_limit": 3,
    }

    monkeypatch.setattr(api.collector_platform, "check_collector_runtime", lambda: collector_runtime)
    monkeypatch.setattr(api.creator_platform, "check_creator_runtime", lambda: creator_runtime)
    monkeypatch.setattr(api.platform_guardrails, "check_creator_publish_allowed", lambda: creator_guardrail)

    result = api.platform_status()

    assert result == {
        "collector_runtime": collector_runtime,
        "creator_runtime": creator_runtime,
        "creator_publish_guardrail": creator_guardrail,
    }


def test_http_platform_status_endpoint_returns_platform_status(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "json")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")
    expected = {
        "collector_runtime": {"ok": True, "mode": "mock", "platform": "mock_collector"},
        "creator_runtime": {"ok": True, "mode": "mock", "platform": "xhs_creator"},
        "creator_publish_guardrail": {"allowed": True, "reason": None},
    }
    monkeypatch.setattr(api, "platform_status", lambda: expected, raising=False)

    server_urls = _start_test_server(monkeypatch, tmp_path)
    base_url = next(server_urls)
    try:
        status, data = _read_json(
            f"{base_url}/platform/status",
            {"Authorization": "Bearer secret-token"},
        )
    finally:
        try:
            next(server_urls)
        except StopIteration:
            pass

    assert status == 200
    assert data == {"ok": True, "platform_status": expected}


def test_http_creator_note_status_endpoint_passes_wait_parameters(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "json")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")

    def fake_status(
        creator_note_id: str,
        limit: int = 50,
        wait: bool = False,
        attempts: int = 5,
        interval_seconds: float = 2.0,
    ) -> dict:
        assert creator_note_id == "note_wait_001"
        assert limit == 30
        assert wait is True
        assert attempts == 4
        assert interval_seconds == 0.5
        return {
            "creator_note_status": {
                "ok": True,
                "status": "synced",
                "creator_note_id": creator_note_id,
                "attempts": attempts,
                "waited_seconds": 0.5,
            }
        }

    monkeypatch.setattr(api, "get_creator_note_status", fake_status, raising=False)

    server_urls = _start_test_server(monkeypatch, tmp_path)
    base_url = next(server_urls)
    try:
        status, data = _read_json(
            (
                f"{base_url}/creator/notes/status"
                "?creator_note_id=note_wait_001&limit=30&wait=true"
                "&attempts=4&interval_seconds=0.5"
            ),
            {"Authorization": "Bearer secret-token"},
        )
    finally:
        try:
            next(server_urls)
        except StopIteration:
            pass

    assert status == 200
    assert data["ok"] is True
    assert data["creator_note_status"]["status"] == "synced"


def test_http_creator_note_performance_sync_endpoint_passes_parameters(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "json")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")

    def fake_sync(
        *,
        creator_note_id: str = "",
        run_id: str = "",
        limit: int = 50,
        wait: bool = False,
        attempts: int = 5,
        interval_seconds: float = 2.0,
        notes: str | None = None,
    ) -> dict:
        assert creator_note_id == "note_sync_http"
        assert run_id == "run_sync_http"
        assert limit == 25
        assert wait is True
        assert attempts == 3
        assert interval_seconds == 0.25
        assert notes == "manual platform sync"
        return {
            "synced": True,
            "resolved_target": {
                "creator_note_id": creator_note_id,
                "run_id": run_id,
                "source": "request",
            },
            "performance_payload": {"creator_note_id": creator_note_id, "views": 10},
            "performance_result": {"business_sync": {"status": "success"}},
        }

    monkeypatch.setattr(api, "sync_creator_note_performance", fake_sync, raising=False)

    server_urls = _start_test_server(monkeypatch, tmp_path)
    base_url = next(server_urls)
    try:
        status, data = _post_json(
            f"{base_url}/creator/notes/performance-sync",
            {
                "creator_note_id": "note_sync_http",
                "run_id": "run_sync_http",
                "limit": 25,
                "wait": True,
                "attempts": 3,
                "interval_seconds": 0.25,
                "notes": "manual platform sync",
            },
            {"Authorization": "Bearer secret-token"},
        )
    finally:
        try:
            next(server_urls)
        except StopIteration:
            pass

    assert status == 200
    assert data["ok"] is True
    assert data["synced"] is True
    assert data["performance_result"]["business_sync"]["status"] == "success"


def test_http_business_run_endpoint_returns_business_snapshot(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(tmp_path / "xhs_agent.sqlite3"))
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")
    expected = {
        "business_run": {
            "run_id": "run_business_http",
            "counts": {"raw_notes": 1},
            "raw_notes": [{"title": "HTTP 查询测试"}],
        }
    }
    monkeypatch.setattr(api, "get_business_run_snapshot", lambda run_id: expected, raising=False)

    server_urls = _start_test_server(monkeypatch, tmp_path)
    base_url = next(server_urls)
    try:
        status, data = _read_json(
            f"{base_url}/business/runs/run_business_http",
            {"Authorization": "Bearer secret-token"},
        )
    finally:
        try:
            next(server_urls)
        except StopIteration:
            pass

    assert status == 200
    assert data == {"ok": True, **expected}
