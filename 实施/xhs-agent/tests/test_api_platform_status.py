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
