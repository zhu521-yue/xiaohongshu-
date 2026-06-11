# Minimal Production Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in API token authentication, redacted file logging, runtime configuration checks, and startup documentation without changing the existing local developer flow.

**Architecture:** Keep the current standard-library HTTP API and scripts. Add small guardrail helpers around the existing boundaries: config values in `app/config.py`, auth helpers in `app/api.py`, reusable logging helpers in `app/logging_config.py`, and an environment self-check script in `scripts/check_runtime_config.py`.

**Tech Stack:** Python standard library HTTP server, `logging.handlers.RotatingFileHandler`, existing `requests` dependency for smoke scripts, pytest.

---

## File Structure

- Modify `app/config.py`
  - Add settings for `XHS_AGENT_API_TOKEN`, log directory, log level, max log size, and backup count.
- Modify `app/api.py`
  - Add request authorization helpers.
  - Protect API endpoints when `XHS_AGENT_API_TOKEN` is set.
  - Use logger for request and lifecycle messages.
- Create `app/logging_config.py`
  - Own all logging setup and redaction logic.
  - Keep this file independent from business logic.
- Modify `scripts/run_api.py`
  - Configure API logging before starting the server.
- Modify `scripts/run_worker.py`
  - Configure worker logging and log claimed/succeeded/failed jobs.
- Modify `scripts/check_api_run.py`
  - Add `--api-token` and send auth headers when provided.
- Create `scripts/check_runtime_config.py`
  - Provide `local`, `sqlite-worker`, and `production-lite` profile checks.
- Modify `.env.example`
  - Document auth and logging settings.
- Create `docs/m17a-production-guardrails.md`
  - Document startup and verification commands.
- Modify `memory/current_progress.md`
  - Record M17a completion and verification evidence after implementation.
- Create tests:
  - `tests/test_api_auth.py`
  - `tests/test_logging_config.py`
  - `tests/test_runtime_config_check.py`
  - `tests/test_check_api_run_auth.py`

---

### Task 1: Config Settings For Auth And Logging

**Files:**
- Modify: `app/config.py`
- Test: `tests/test_m17a_config.py`

- [ ] **Step 1: Write failing config tests**

Create `tests/test_m17a_config.py`:

```python
from __future__ import annotations

from app.config import load_settings


def test_guardrail_settings_default_to_development_safe_values(monkeypatch) -> None:
    monkeypatch.delenv("XHS_AGENT_API_TOKEN", raising=False)
    monkeypatch.delenv("XHS_AGENT_LOG_DIR", raising=False)
    monkeypatch.delenv("XHS_AGENT_LOG_LEVEL", raising=False)
    monkeypatch.delenv("XHS_AGENT_LOG_MAX_BYTES", raising=False)
    monkeypatch.delenv("XHS_AGENT_LOG_BACKUP_COUNT", raising=False)

    settings = load_settings()

    assert settings.api_token is None
    assert settings.log_dir == "data/logs"
    assert settings.log_level == "INFO"
    assert settings.log_max_bytes == 1048576
    assert settings.log_backup_count == 5


def test_guardrail_settings_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", "tmp/logs")
    monkeypatch.setenv("XHS_AGENT_LOG_LEVEL", "debug")
    monkeypatch.setenv("XHS_AGENT_LOG_MAX_BYTES", "2048")
    monkeypatch.setenv("XHS_AGENT_LOG_BACKUP_COUNT", "2")

    settings = load_settings()

    assert settings.api_token == "secret-token"
    assert settings.log_dir == "tmp/logs"
    assert settings.log_level == "DEBUG"
    assert settings.log_max_bytes == 2048
    assert settings.log_backup_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_m17a_config.py -q
```

Expected: fail with `AttributeError` for missing `Settings.api_token` or related log settings.

- [ ] **Step 3: Add settings fields**

Modify `app/config.py`:

```python
@dataclass(frozen=True)
class Settings:
    llm_api_key: str | None
    llm_base_url:str | None
    llm_model_name: str
    llm_timeout_seconds: float
    llm_image_text_max_tokens: int
    llm_video_max_tokens: int
    llm_review_max_tokens: int
    account_stage:str
    api_token: str | None
    log_dir: str
    log_level: str
    log_max_bytes: int
    log_backup_count: int
    run_store_backend: str
    run_db_path: str
    run_queue_backend: str
    queue_db_path: str
    queue_poll_seconds: float
    queue_max_attempts: int
    queue_lock_timeout_seconds: int
    worker_id: str | None
    memory_store_backend: str
    memory_db_path: str
```

Add a helper near `_env_int()`:

```python
def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
```

Add fields inside `load_settings()`:

```python
api_token=_optional_env("XHS_AGENT_API_TOKEN"),
log_dir=os.getenv("XHS_AGENT_LOG_DIR", "data/logs"),
log_level=os.getenv("XHS_AGENT_LOG_LEVEL", "INFO").strip().upper() or "INFO",
log_max_bytes=_env_int("XHS_AGENT_LOG_MAX_BYTES", 1048576),
log_backup_count=_env_int("XHS_AGENT_LOG_BACKUP_COUNT", 5),
```

- [ ] **Step 4: Run config tests**

Run:

```powershell
python -m pytest tests/test_m17a_config.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

Run:

```powershell
git add app/config.py tests/test_m17a_config.py
git commit -m "feat: add guardrail runtime settings"
```

---

### Task 2: Redacted Logging Helpers

**Files:**
- Create: `app/logging_config.py`
- Test: `tests/test_logging_config.py`

- [ ] **Step 1: Write failing logging tests**

Create `tests/test_logging_config.py`:

```python
from __future__ import annotations

import logging
from pathlib import Path

from app.logging_config import configure_logging, redact_sensitive, safe_log_dict


def test_redact_sensitive_masks_nested_secret_values() -> None:
    payload = {
        "api_key": "key-value",
        "nested": {
            "cookie": "cookie-value",
            "normal": "visible",
        },
        "items": [
            {"authorization": "Bearer abc"},
            {"topic": "小红书新手选题方法"},
        ],
    }

    redacted = redact_sensitive(payload)

    assert redacted["api_key"] == "<redacted>"
    assert redacted["nested"]["cookie"] == "<redacted>"
    assert redacted["nested"]["normal"] == "visible"
    assert redacted["items"][0]["authorization"] == "<redacted>"
    assert redacted["items"][1]["topic"] == "小红书新手选题方法"


def test_safe_log_dict_keeps_non_sensitive_values() -> None:
    result = safe_log_dict({"run_id": "run_1", "token": "secret"})

    assert result == {"run_id": "run_1", "token": "<redacted>"}


def test_configure_logging_writes_to_service_log(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path))
    monkeypatch.setenv("XHS_AGENT_LOG_LEVEL", "INFO")
    monkeypatch.setenv("XHS_AGENT_LOG_MAX_BYTES", "4096")
    monkeypatch.setenv("XHS_AGENT_LOG_BACKUP_COUNT", "1")

    logger = configure_logging("api")
    logger.info("guardrail log check")

    log_path = tmp_path / "api.log"
    assert log_path.exists()
    assert "guardrail log check" in log_path.read_text(encoding="utf-8")
    assert logger.level == logging.INFO
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_logging_config.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'app.logging_config'`.

- [ ] **Step 3: Add logging helper implementation**

Create `app/logging_config.py`:

```python
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, load_settings


SENSITIVE_KEY_PARTS = (
    "token",
    "api_key",
    "key",
    "secret",
    "cookie",
    "authorization",
    "password",
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "<redacted>" if _is_sensitive_key(str(key)) else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    return value


def safe_log_dict(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_sensitive(payload)
    return redacted if isinstance(redacted, dict) else {}


def _resolve_log_dir(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def configure_logging(service_name: str) -> logging.Logger:
    settings = load_settings()
    log_dir = _resolve_log_dir(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"xhs_agent.{service_name}")
    logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    logger.propagate = False

    log_path = log_dir / f"{service_name}.log"
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    if not any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", None) == str(log_path)
        for handler in logger.handlers
    ):
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max(1024, settings.log_max_bytes),
            backupCount=max(0, settings.log_backup_count),
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger
```

- [ ] **Step 4: Run logging tests**

Run:

```powershell
python -m pytest tests/test_logging_config.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

Run:

```powershell
git add app/logging_config.py tests/test_logging_config.py
git commit -m "feat: add redacted file logging"
```

---

### Task 3: API Token Auth Helpers And Endpoint Protection

**Files:**
- Modify: `app/api.py`
- Test: `tests/test_api_auth.py`

- [ ] **Step 1: Write failing auth helper tests**

Create `tests/test_api_auth.py`:

```python
from __future__ import annotations

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
```

- [ ] **Step 2: Run helper test to verify it fails**

Run:

```powershell
python -m pytest tests/test_api_auth.py -q
```

Expected: fail with `AttributeError: module 'app.api' has no attribute '_request_is_authorized'`.

- [ ] **Step 3: Add auth helpers**

Modify imports in `app/api.py`:

```python
import hmac
import logging
from collections.abc import Mapping
```

Add near globals:

```python
LOGGER = logging.getLogger("xhs_agent.api")
```

Add helper functions before `class XHSAgentAPIHandler`:

```python
def _configured_api_token() -> str | None:
    return load_settings().api_token


def _extract_request_token(headers: Mapping[str, str]) -> str | None:
    auth_header = str(headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            return token

    direct_token = str(headers.get("X-XHS-Agent-Token") or "").strip()
    return direct_token or None


def _is_public_endpoint(method: str, path: str) -> bool:
    normalized_method = method.upper()
    normalized_path = path.rstrip("/") or "/"
    if normalized_method == "OPTIONS":
        return True
    if normalized_method == "GET" and normalized_path == "/health":
        return True
    if normalized_method == "GET" and _static_path(normalized_path):
        return True
    return False


def _request_is_authorized(method: str, path: str, headers: Mapping[str, str]) -> bool:
    expected_token = _configured_api_token()
    if not expected_token:
        return True
    if _is_public_endpoint(method, path):
        return True
    request_token = _extract_request_token(headers)
    if not request_token:
        return False
    return hmac.compare_digest(request_token, expected_token)
```

- [ ] **Step 4: Run helper tests**

Run:

```powershell
python -m pytest tests/test_api_auth.py -q
```

Expected: `7 passed`.

- [ ] **Step 5: Add HTTP handler enforcement**

Modify `XHSAgentAPIHandler`:

```python
    def _send_json(self, status: int, payload: Any) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-XHS-Agent-Token")
        self.end_headers()
        self.wfile.write(body)

    def _ensure_authorized(self, method: str, path: str) -> bool:
        if _request_is_authorized(method, path, self.headers):
            return True
        self._send_error(401, "Unauthorized")
        LOGGER.warning("unauthorized_request method=%s path=%s", method, path)
        return False
```

Call it in `do_GET()` after path parsing and before static/health handling:

```python
        if not self._ensure_authorized("GET", path):
            return
```

Call it in `do_POST()` after path parsing and before reading the JSON body:

```python
        if not self._ensure_authorized("POST", path):
            return
```

Do not add auth enforcement to `do_OPTIONS()` because CORS preflight remains public.

- [ ] **Step 6: Add HTTP-level smoke tests**

Append to `tests/test_api_auth.py`:

```python
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Iterator
from urllib.request import Request, urlopen
from urllib.error import HTTPError


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
```

- [ ] **Step 7: Run auth tests**

Run:

```powershell
python -m pytest tests/test_api_auth.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

Run:

```powershell
git add app/api.py tests/test_api_auth.py
git commit -m "feat: add optional api token auth"
```

---

### Task 4: Integrate Logging Into API And Worker

**Files:**
- Modify: `app/api.py`
- Modify: `scripts/run_api.py`
- Modify: `scripts/run_worker.py`
- Test: `tests/test_run_worker.py`

- [ ] **Step 1: Add worker logging test**

Append to `tests/test_run_worker.py`:

```python
class FakeLogger:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def info(self, message: str, *args) -> None:
        self.messages.append(("info", message % args if args else message))

    def warning(self, message: str, *args) -> None:
        self.messages.append(("warning", message % args if args else message))


def test_run_worker_once_logs_claim_and_success() -> None:
    queue = FakeQueue("run_1")
    logger = FakeLogger()
    records = {"run_1": {"status": "success", "error": None}}

    did_work = run_worker.run_once(
        queue=queue,
        worker_id="worker-a",
        execute_run=lambda run_id: None,
        load_run=lambda run_id: records[run_id],
        logger=logger,
    )

    assert did_work is True
    assert ("info", "worker_claimed run_id=run_1 worker_id=worker-a") in logger.messages
    assert ("info", "worker_succeeded run_id=run_1 worker_id=worker-a") in logger.messages


def test_run_worker_once_logs_failure() -> None:
    queue = FakeQueue("run_1")
    logger = FakeLogger()
    records = {"run_1": {"status": "failed", "error": "graph failed"}}

    did_work = run_worker.run_once(
        queue=queue,
        worker_id="worker-a",
        execute_run=lambda run_id: None,
        load_run=lambda run_id: records[run_id],
        logger=logger,
    )

    assert did_work is True
    assert ("warning", "worker_failed run_id=run_1 worker_id=worker-a error=graph failed") in logger.messages
```

- [ ] **Step 2: Run worker tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_run_worker.py -q
```

Expected: fail with `TypeError` because `run_once()` does not accept `logger`.

- [ ] **Step 3: Modify worker logging**

Modify `scripts/run_worker.py` imports:

```python
import logging
from app.logging_config import configure_logging  # noqa: E402
```

Change `run_once()` signature:

```python
def run_once(
    queue: SQLiteRunQueue,
    worker_id: str,
    execute_run: Callable[[str], None] = api._execute_run,
    load_run: Callable[[str], dict[str, Any] | None] = api._load_run,
    logger: logging.Logger | None = None,
) -> bool:
```

Add inside `run_once()`:

```python
    logger = logger or logging.getLogger("xhs_agent.worker")
    run_id = queue.claim_next(worker_id)
    if not run_id:
        return False

    logger.info("worker_claimed run_id=%s worker_id=%s", run_id, worker_id)
```

Log success:

```python
        if status == "success":
            queue.mark_succeeded(run_id, worker_id)
            logger.info("worker_succeeded run_id=%s worker_id=%s", run_id, worker_id)
```

Log failure from run status:

```python
        elif status == "failed":
            error = str(record.get("error") or "run failed")
            queue.mark_failed(run_id, worker_id, error)
            logger.warning("worker_failed run_id=%s worker_id=%s error=%s", run_id, worker_id, error)
```

Log unexpected status:

```python
        else:
            error = f"run ended with unexpected status: {status}"
            queue.mark_failed(run_id, worker_id, error)
            logger.warning("worker_failed run_id=%s worker_id=%s error=%s", run_id, worker_id, error)
```

Log exception:

```python
    except Exception as exc:
        queue.mark_failed(run_id, worker_id, str(exc))
        logger.exception("worker_exception run_id=%s worker_id=%s", run_id, worker_id)
```

Configure logging in `main()`:

```python
    logger = configure_logging("worker")
    logger.info("worker_starting worker_id=%s once=%s", worker_id, args.once)
```

Pass `logger=logger` to `run_once()` in `main()`. In `run_loop()`, create a logger with `logging.getLogger("xhs_agent.worker")` and pass it into `run_once()`.

- [ ] **Step 4: Modify API script logging**

Modify `scripts/run_api.py`:

```python
from app.logging_config import configure_logging  # noqa: E402
```

In `main()`:

```python
    logger = configure_logging("api")
    logger.info("api_starting host=%s port=%s", args.host, args.port)
    run_server(host=args.host, port=args.port)
```

- [ ] **Step 5: Modify API request logging**

Modify `app/api.py` `log_message()`:

```python
    def log_message(self, format: str, *args: Any) -> None:
        LOGGER.info(
            "http_request client=%s message=%s",
            self.address_string(),
            format % args,
        )
```

Modify `run_server()`:

```python
def run_server(host: str = "127.0.0.1", port: int = 8010) -> None:
    _recover_pending_runs()
    server = ThreadingHTTPServer((host, port), XHSAgentAPIHandler)
    LOGGER.info("api_listening url=http://%s:%s", host, port)
    print(f"XHS Agent API listening on http://{host}:{port}")
    server.serve_forever()
```

Add run submission and review logs:

```python
def submit_run(payload: dict[str, Any]) -> dict[str, Any]:
    request_payload = _build_run_request(payload)
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    record = _run_record(run_id, request_payload, status="queued")
    _save_run(record)
    _enqueue_run(run_id)
    LOGGER.info(
        "run_submitted run_id=%s engine=%s format=%s",
        run_id,
        request_payload["engine"],
        request_payload["format"],
    )
    return record
```

In `approve_run()` after `_save_reviewed_run()`:

```python
    reviewed = _save_reviewed_run(record, state, review_action="approved")
    LOGGER.info("run_approved run_id=%s", run_id)
    return reviewed
```

In `reject_run()` after `_save_reviewed_run()`:

```python
    reviewed = _save_reviewed_run(record, state, review_action="rejected")
    LOGGER.info("run_rejected run_id=%s", run_id)
    return reviewed
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
python -m pytest tests/test_logging_config.py tests/test_run_worker.py tests/test_api_auth.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add app/api.py scripts/run_api.py scripts/run_worker.py tests/test_run_worker.py
git commit -m "feat: log api and worker operations"
```

---

### Task 5: Runtime Configuration Check Script

**Files:**
- Create: `scripts/check_runtime_config.py`
- Test: `tests/test_runtime_config_check.py`

- [ ] **Step 1: Write failing runtime config tests**

Create `tests/test_runtime_config_check.py`:

```python
from __future__ import annotations

from pathlib import Path

from scripts.check_runtime_config import check_profile


def test_local_profile_passes_with_default_development_settings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("XHS_AGENT_API_TOKEN", raising=False)
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.delenv("XHS_AGENT_RUN_STORE", raising=False)
    monkeypatch.delenv("XHS_AGENT_RUN_QUEUE", raising=False)
    monkeypatch.delenv("XHS_AGENT_MEMORY_STORE", raising=False)

    results = check_profile("local")

    assert not [result for result in results if result.level == "FAIL"]
    assert any(result.level == "WARN" and "auth disabled" in result.message for result in results)


def test_production_lite_fails_without_api_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("XHS_AGENT_API_TOKEN", raising=False)
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path / "logs"))

    results = check_profile("production-lite")

    assert any(
        result.level == "FAIL" and "XHS_AGENT_API_TOKEN" in result.message
        for result in results
    )


def test_sqlite_worker_profile_checks_sqlite_backends(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_QUEUE_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(db_path))

    results = check_profile("sqlite-worker")

    assert not [result for result in results if result.level == "FAIL"]
    assert any("run queue backend: sqlite" in result.message for result in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_runtime_config_check.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'scripts.check_runtime_config'`.

- [ ] **Step 3: Add runtime config script**

Create `scripts/check_runtime_config.py`:

```python
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import PROJECT_ROOT, load_settings  # noqa: E402


@dataclass(frozen=True)
class CheckResult:
    level: str
    message: str


def _resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _check_writable_dir(label: str, path_value: str) -> CheckResult:
    path = _resolve_project_path(path_value)
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        return CheckResult("FAIL", f"{label} not writable: {path} ({exc})")
    return CheckResult("PASS", f"{label} writable: {path_value}")


def _check_db_parent(label: str, path_value: str) -> CheckResult:
    path = _resolve_project_path(path_value)
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        probe = parent / ".write_check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        return CheckResult("FAIL", f"{label} parent not writable: {parent} ({exc})")
    return CheckResult("PASS", f"{label} parent writable: {path_value}")


def _check_local_profile() -> list[CheckResult]:
    settings = load_settings()
    results = [
        CheckResult("PASS", "core modules importable"),
        _check_writable_dir("log_dir", settings.log_dir),
        CheckResult("PASS", f"run store backend: {settings.run_store_backend}"),
        CheckResult("PASS", f"run queue backend: {settings.run_queue_backend}"),
    ]
    if settings.api_token:
        results.append(CheckResult("PASS", "api token set: auth enabled"))
    else:
        results.append(CheckResult("WARN", "api token empty: auth disabled"))
    return results


def _check_sqlite_worker_profile() -> list[CheckResult]:
    settings = load_settings()
    results = [_check_writable_dir("log_dir", settings.log_dir)]

    expected = [
        ("run store backend", settings.run_store_backend, "sqlite"),
        ("run queue backend", settings.run_queue_backend, "sqlite"),
        ("memory store backend", settings.memory_store_backend, "sqlite"),
    ]
    for label, actual, expected_value in expected:
        if actual == expected_value:
            results.append(CheckResult("PASS", f"{label}: {actual}"))
        else:
            results.append(CheckResult("FAIL", f"{label} must be {expected_value}, got {actual}"))

    results.extend(
        [
            _check_db_parent("run db", settings.run_db_path),
            _check_db_parent("queue db", settings.queue_db_path),
            _check_db_parent("memory db", settings.memory_db_path),
        ]
    )

    if settings.run_db_path != settings.queue_db_path:
        results.append(CheckResult("WARN", "run DB path and queue DB path differ; verify both processes use matching env"))
    else:
        results.append(CheckResult("PASS", "run DB path and queue DB path match"))

    return results


def _check_production_lite_profile() -> list[CheckResult]:
    settings = load_settings()
    results = [_check_writable_dir("log_dir", settings.log_dir)]

    if settings.api_token:
        results.append(CheckResult("PASS", "XHS_AGENT_API_TOKEN set"))
    else:
        results.append(CheckResult("FAIL", "production-lite requires XHS_AGENT_API_TOKEN"))

    if settings.llm_api_key:
        results.append(CheckResult("PASS", "LLM_API_KEY set"))
    else:
        results.append(CheckResult("WARN", "LLM_API_KEY empty: real LLM calls will not work"))

    import os

    if os.getenv("XHS_COOKIES_PC"):
        results.append(CheckResult("PASS", "XHS_COOKIES_PC set"))
    else:
        results.append(CheckResult("WARN", "XHS_COOKIES_PC empty: real Spider_XHS collection will not work"))

    if settings.run_queue_backend == "sqlite":
        results.extend(_check_sqlite_worker_profile())
    else:
        results.append(CheckResult("WARN", f"run queue backend is {settings.run_queue_backend}; API and worker are not split"))

    return results


def check_profile(profile: str) -> list[CheckResult]:
    if profile == "local":
        return _check_local_profile()
    if profile == "sqlite-worker":
        return _check_sqlite_worker_profile()
    if profile == "production-lite":
        return _check_production_lite_profile()
    raise ValueError(f"Unsupported profile: {profile}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check xhs-agent runtime configuration.")
    parser.add_argument(
        "--profile",
        choices=("local", "sqlite-worker", "production-lite"),
        default="local",
        help="Configuration profile to check.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    results = check_profile(args.profile)
    for result in results:
        print(f"{result.level} {result.message}")
    return 1 if any(result.level == "FAIL" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run runtime config tests**

Run:

```powershell
python -m pytest tests/test_runtime_config_check.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Run script manually**

Run:

```powershell
python .\scripts\check_runtime_config.py --profile local
```

Expected: prints `PASS` lines and may print `WARN api token empty: auth disabled`; exit code `0`.

- [ ] **Step 6: Commit**

Run:

```powershell
git add scripts/check_runtime_config.py tests/test_runtime_config_check.py
git commit -m "feat: add runtime config checks"
```

---

### Task 6: Auth Header Support In API Smoke Script

**Files:**
- Modify: `scripts/check_api_run.py`
- Test: `tests/test_check_api_run_auth.py`

- [ ] **Step 1: Write failing script auth tests**

Create `tests/test_check_api_run_auth.py`:

```python
from __future__ import annotations

from scripts import check_api_run


def test_build_headers_empty_without_api_token() -> None:
    assert check_api_run.build_headers(None) == {}
    assert check_api_run.build_headers("") == {}


def test_build_headers_uses_bearer_token() -> None:
    assert check_api_run.build_headers("secret-token") == {
        "Authorization": "Bearer secret-token"
    }


def test_parser_accepts_api_token() -> None:
    args = check_api_run.build_parser().parse_args(["--api-token", "secret-token"])

    assert args.api_token == "secret-token"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_check_api_run_auth.py -q
```

Expected: fail with `AttributeError` for `build_headers` or parser missing `api_token`.

- [ ] **Step 3: Add auth header support**

Modify `scripts/check_api_run.py`:

```python
def build_headers(api_token: str | None) -> dict[str, str]:
    token = str(api_token or "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}
```

Add parser argument:

```python
    parser.add_argument("--api-token", default=None, help="API token for guarded API mode.")
```

In `main()` after `base_url`:

```python
    headers = build_headers(args.api_token)
```

Pass headers to POST:

```python
        response = requests.post(f"{base_url}/runs", json=payload, headers=headers, timeout=30)
```

Pass headers to GET:

```python
            poll_response = requests.get(f"{base_url}/runs/{run_id}", headers=headers, timeout=30)
```

- [ ] **Step 4: Run script auth tests**

Run:

```powershell
python -m pytest tests/test_check_api_run_auth.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

Run:

```powershell
git add scripts/check_api_run.py tests/test_check_api_run_auth.py
git commit -m "feat: pass api token in smoke script"
```

---

### Task 7: Documentation, Env Example, And Progress

**Files:**
- Modify: `.env.example`
- Create: `docs/m17a-production-guardrails.md`

- [ ] **Step 1: Update `.env.example`**

Add after the runtime mode block:

```env
# API guardrails.
# Empty token keeps local development auth disabled.
# Set a strong value before binding the API beyond localhost.
XHS_AGENT_API_TOKEN=

# Logging.
XHS_AGENT_LOG_DIR=data/logs
XHS_AGENT_LOG_LEVEL=INFO
XHS_AGENT_LOG_MAX_BYTES=1048576
XHS_AGENT_LOG_BACKUP_COUNT=5
```

- [ ] **Step 2: Add guardrails documentation**

Create `docs/m17a-production-guardrails.md` with this content:

~~~markdown
# M17a Production Guardrails

M17a adds optional API token auth, redacted file logs, and runtime configuration checks. It does not add Docker, Nginx, systemd, HTTPS, user accounts, or Redis.

## Local Development

Authentication is disabled when `XHS_AGENT_API_TOKEN` is empty.

cmd:

```bat
set COLLECTOR_MODE=mock
set LLM_MODEL_NAME=mock
set XHS_AGENT_RUN_QUEUE=local
set XHS_AGENT_API_TOKEN=
python .\scripts\run_api.py --host 127.0.0.1 --port 8010
```

PowerShell:

```powershell
$env:COLLECTOR_MODE='mock'
$env:LLM_MODEL_NAME='mock'
$env:XHS_AGENT_RUN_QUEUE='local'
$env:XHS_AGENT_API_TOKEN=''
python .\scripts\run_api.py --host 127.0.0.1 --port 8010
```

## Guarded API Mode

Set `XHS_AGENT_API_TOKEN` before starting the API.

cmd:

```bat
set XHS_AGENT_API_TOKEN=replace-with-local-secret
set COLLECTOR_MODE=mock
set LLM_MODEL_NAME=mock
python .\scripts\run_api.py --host 127.0.0.1 --port 8010
```

PowerShell:

```powershell
$env:XHS_AGENT_API_TOKEN='replace-with-local-secret'
$env:COLLECTOR_MODE='mock'
$env:LLM_MODEL_NAME='mock'
python .\scripts\run_api.py --host 127.0.0.1 --port 8010
```

Unauthenticated protected API calls return `401`.

Authenticated smoke check:

```powershell
python .\scripts\check_api_run.py --base-url http://127.0.0.1:8010 --api-token replace-with-local-secret --engine langgraph --collect-limit 3 --timeout 180
```

## Runtime Config Checks

Local profile:

```powershell
python .\scripts\check_runtime_config.py --profile local
```

SQLite split-process profile:

```powershell
python .\scripts\check_runtime_config.py --profile sqlite-worker
```

Guarded server-facing profile:

```powershell
python .\scripts\check_runtime_config.py --profile production-lite
```

`production-lite` fails if `XHS_AGENT_API_TOKEN` is empty.

## Logs

Default files:

```text
data/logs/api.log
data/logs/worker.log
```

Sensitive keys such as token, cookie, secret, password, authorization, and API key are redacted by logging helpers.
~~~

- [ ] **Step 3: Run docs checks**

Run:

```powershell
git diff --check
```

Expected: exit code `0`.

- [ ] **Step 4: Commit**

Run:

```powershell
git add .env.example docs/m17a-production-guardrails.md
git commit -m "docs: add production guardrails startup guide"
```

---

### Task 8: Final Verification And Guarded Smoke Test

**Files:**
- Verify all M17a files

- [ ] **Step 1: Run full test suite**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run compile check**

Run:

```powershell
python -m compileall app nodes routers platforms memory scripts llm
```

Expected: exit code `0`; no syntax errors.

- [ ] **Step 3: Run local config check**

Run:

```powershell
python .\scripts\check_runtime_config.py --profile local
```

Expected: exit code `0`; output includes `PASS log_dir writable`.

- [ ] **Step 4: Run production-lite failure check**

Run:

```powershell
$oldToken=$env:XHS_AGENT_API_TOKEN
$env:XHS_AGENT_API_TOKEN=''
python .\scripts\check_runtime_config.py --profile production-lite
$env:XHS_AGENT_API_TOKEN=$oldToken
```

Expected: command prints `FAIL production-lite requires XHS_AGENT_API_TOKEN` and exits `1`.

- [ ] **Step 5: Run guarded API smoke check**

Use a temporary SQLite DB and a temporary port. The exact port can change if occupied.

Run:

```powershell
$env:XHS_AGENT_API_TOKEN='test-token'
$env:COLLECTOR_MODE='mock'
$env:LLM_MODEL_NAME='mock'
$env:XHS_AGENT_RUN_STORE='sqlite'
$env:XHS_AGENT_RUN_DB_PATH='data/tmp_m17a_guardrails.sqlite3'
$env:XHS_AGENT_RUN_QUEUE='local'
$env:XHS_AGENT_MEMORY_STORE='sqlite'
$env:XHS_AGENT_MEMORY_DB_PATH='data/tmp_m17a_guardrails.sqlite3'
$python=(Get-Command python).Source
$proc=Start-Process -FilePath $python -ArgumentList @('.\scripts\run_api.py','--host','127.0.0.1','--port','8022') -WorkingDirectory (Get-Location) -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 2
try {
  python -c "import requests; r=requests.post('http://127.0.0.1:8022/runs', json={'topic':'x'}); print(r.status_code); print(r.json())"
  python .\scripts\check_api_run.py --base-url http://127.0.0.1:8022 --api-token test-token --engine langgraph --collect-limit 3 --timeout 60
} finally {
  Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}
```

Expected:

- unauthenticated POST prints `401`
- authenticated smoke script returns exit code `0`
- final run status is `success`

- [ ] **Step 6: Clean temporary smoke files**

Run a safe cleanup that only deletes the temporary M17a smoke DB files under the workspace:

```powershell
$workspace=(Resolve-Path '.').Path
Get-ChildItem -LiteralPath (Join-Path $workspace 'data') -Force |
  Where-Object { $_.Name -like 'tmp_m17a_guardrails*' } |
  ForEach-Object {
    $resolved=$_.FullName
    if ($resolved.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) {
      Remove-Item -LiteralPath $resolved -Force
    }
  }
```

Expected: no temporary `tmp_m17a_guardrails*` files remain.

- [ ] **Step 7: Record verified progress**

Prepend to `memory/current_progress.md` after Steps 1-6 have passed:

```markdown
## 2026-06-11 M17a 最小生产护栏

本轮目标是在不引入 Docker、Nginx、systemd、Redis 或新 Web 框架的前提下，给当前 API/worker 增加最小生产护栏。

已完成：
- API token 鉴权支持，默认本地开发关闭，设置 `XHS_AGENT_API_TOKEN` 后保护 `/runs`、`/queue`、审核和表现录入等接口。
- `/health` 和静态页面保持公开，便于健康检查和页面加载。
- API 与 worker 增加日志落盘，默认写入 `data/logs/api.log` 和 `data/logs/worker.log`。
- 增加敏感字段脱敏工具，避免 token、cookie、api key、authorization 等值进入结构化日志。
- 新增 `scripts/check_runtime_config.py`，支持 `local`、`sqlite-worker`、`production-lite` 三种配置检查。
- `scripts/check_api_run.py` 支持 `--api-token`，可验证带鉴权的 API。
- 新增 `docs/m17a-production-guardrails.md`，说明本地、分进程和带鉴权模式的启动方式。

已验证：
- `python -m pytest -q` 通过。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- `python .\scripts\check_runtime_config.py --profile local` 通过。
- `python .\scripts\check_runtime_config.py --profile production-lite` 在 token 为空时按预期失败。
- 带 `XHS_AGENT_API_TOKEN` 的 API 烟测通过：未带 token 的 `/runs` 返回 `401`，带 token 的 `check_api_run.py` 能完成 mock LangGraph run。

当前阶段判断：
- 当前系统仍不是完整生产部署，但已经具备最小 server-facing 护栏。
- 真正对公网部署前仍需要 HTTPS、反向代理、进程守护、备份、账号体系和更完整的密钥治理。

建议下一步：
1. M17b：补进程启动模板和部署清单，继续保持不引入重型新组件。
2. M18：需要更高并发时再进入 Redis/RQ 或 Celery。
3. M19：基础部署稳定后，再推进小红书创作者平台私密发布和作品列表同步。
```

Run:

```powershell
git add memory/current_progress.md
git commit -m "docs: record production guardrails progress"
```

- [ ] **Step 8: Final repository status**

Run:

```powershell
git status --short --untracked-files=all
git log --oneline -n 8
```

Expected:

- no uncommitted M17a changes
- recent commits show the M17a implementation commits

---

## Self-Review

- Spec coverage: API token auth is covered by Tasks 1 and 3; redacted logging by Tasks 2 and 4; runtime config checks by Task 5; smoke script token support by Task 6; env/docs by Task 7; final verification and progress by Task 8.
- Placeholder scan: the plan contains concrete files, code snippets, commands, and expected results for each task.
- Type consistency: `Settings.api_token`, `Settings.log_dir`, `configure_logging()`, `redact_sensitive()`, `safe_log_dict()`, `check_profile()`, and `build_headers()` use the same names across tests and implementation steps.
- Scope check: Docker, Nginx, systemd, HTTPS, user accounts, Redis/RQ/Celery, frontend login UI, and cookie encryption remain out of this implementation plan.
