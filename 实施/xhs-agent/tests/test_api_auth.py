from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Iterator
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import api


def test_auth_disabled_when_token_is_empty(monkeypatch) -> None:
    monkeypatch.delenv("XHS_AGENT_API_TOKEN", raising=False)

    assert api._request_is_authorized("GET", "/runs", {}) is True


def test_health_is_public_when_auth_enabled(monkeypatch) -> None:
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")

    assert api._request_is_authorized("GET", "/health", {}) is True


def test_static_assets_are_public_when_auth_enabled(monkeypatch) -> None:
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")

    assert api._request_is_authorized("GET", "/", {}) is True
    assert api._request_is_authorized("GET", "/static/app.js", {}) is True


def test_static_path_rejects_sibling_directory_traversal(monkeypatch, tmp_path: Path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    static_evil_dir = tmp_path / "static_evil"
    static_evil_dir.mkdir()
    (static_evil_dir / "file.txt").write_text("not public", encoding="utf-8")
    monkeypatch.setattr(api, "STATIC_DIR", static_dir)
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")

    assert api._static_path("/static/../static_evil/file.txt") is None
    assert api._request_is_authorized("GET", "/static/../static_evil/file.txt", {}) is False


def test_protected_endpoint_rejects_missing_token(monkeypatch) -> None:
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")

    assert api._request_is_authorized("GET", "/runs", {}) is False
    assert api._request_is_authorized("POST", "/runs", {}) is False


def test_protected_endpoint_accepts_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")

    assert api._request_is_authorized(
        "POST",
        "/runs",
        {"Authorization": "Bearer secret-token"},
    ) is True


def test_protected_endpoint_accepts_xhs_agent_token(monkeypatch) -> None:
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")

    assert api._request_is_authorized(
        "GET",
        "/queue",
        {"X-XHS-Agent-Token": "secret-token"},
    ) is True


def test_protected_endpoint_rejects_wrong_token(monkeypatch) -> None:
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")

    assert api._request_is_authorized(
        "GET",
        "/queue",
        {"Authorization": "Bearer wrong-token"},
    ) is False


def _start_test_server(monkeypatch, tmp_path: Path) -> Iterator[str]:
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


def _post_raw_json(
    url: str,
    body: bytes,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict]:
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_http_health_public_but_runs_protected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "json")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")

    server_urls = _start_test_server(monkeypatch, tmp_path)
    base_url = next(server_urls)
    try:
        health_status, health_data = _read_json(f"{base_url}/health")
        runs_status, runs_data = _read_json(f"{base_url}/runs")
        authed_status, authed_data = _read_json(
            f"{base_url}/runs",
            {"Authorization": "Bearer secret-token"},
        )
    finally:
        try:
            next(server_urls)
        except StopIteration:
            pass

    assert health_status == 200
    assert health_data["ok"] is True
    assert runs_status == 401
    assert runs_data == {"ok": False, "error": "Unauthorized"}
    assert authed_status == 200
    assert authed_data["ok"] is True
    assert authed_data["runs"] == []


def test_http_unauthorized_post_with_malformed_json_returns_401(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "json")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")

    server_urls = _start_test_server(monkeypatch, tmp_path)
    base_url = next(server_urls)
    try:
        status, data = _post_raw_json(f"{base_url}/runs", b"{not-json")
    finally:
        try:
            next(server_urls)
        except StopIteration:
            pass

    assert status == 401
    assert data == {"ok": False, "error": "Unauthorized"}
