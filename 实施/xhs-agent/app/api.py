"""Minimal HTTP API for the XHS agent workflow.

This module intentionally uses the Python standard library. It gives the
project a stable HTTP boundary before we decide whether to introduce FastAPI
and a frontend framework.
"""

from __future__ import annotations

import json
import mimetypes
import os
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.config import load_settings
from app.graph import run_langgraph, run_local_graph
from app.run_queue import LocalRunQueue, SQLiteRunQueue
from app.run_store import LocalRunStore, SQLiteRunStore
from memory.operation_store import load_history, operation_memory_path, update_record_performance
from nodes.memory_node import write_operation_memory
from nodes.publish_node import publish_or_schedule
from nodes.review_node import review_performance


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = PROJECT_ROOT / "data" / "api_runs"
STATIC_DIR = PROJECT_ROOT / "app" / "static"
RUN_STORE: LocalRunStore | SQLiteRunStore | None = None
RUN_QUEUE_SERVICE: LocalRunQueue | SQLiteRunQueue | None = None


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default).encode("utf-8")


def _resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _run_store() -> LocalRunStore | SQLiteRunStore:
    global RUN_STORE
    if RUN_STORE is None:
        settings = load_settings()
        if settings.run_store_backend == "sqlite":
            RUN_STORE = SQLiteRunStore(
                _resolve_project_path(settings.run_db_path),
                runs_dir=RUNS_DIR,
                json_default=_json_default,
            )
        else:
            RUN_STORE = LocalRunStore(RUNS_DIR, json_default=_json_default)
    return RUN_STORE


def _local_worker_count() -> int:
    return max(1, _int(os.getenv("XHS_AGENT_LOCAL_WORKERS"), default=1))


def _run_queue_service() -> LocalRunQueue | SQLiteRunQueue:
    global RUN_QUEUE_SERVICE
    if RUN_QUEUE_SERVICE is None:
        settings = load_settings()
        if settings.run_queue_backend == "sqlite":
            RUN_QUEUE_SERVICE = SQLiteRunQueue(
                db_path=_resolve_project_path(settings.queue_db_path),
                list_runs=_list_runs,
                max_attempts=settings.queue_max_attempts,
                lock_timeout_seconds=settings.queue_lock_timeout_seconds,
            )
        else:
            RUN_QUEUE_SERVICE = LocalRunQueue(
                execute_run=_execute_run,
                list_runs=_list_runs,
                worker_count=_local_worker_count(),
            )
    return RUN_QUEUE_SERVICE


def _static_path(path: str) -> Path | None:
    if path == "/":
        relative_path = "index.html"
    elif path.startswith("/static/"):
        relative_path = path.removeprefix("/static/")
    else:
        return None

    candidate = (STATIC_DIR / relative_path).resolve()
    static_root = STATIC_DIR.resolve()
    if not str(candidate).startswith(str(static_root)):
        return None
    return candidate


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _run_path(run_id: str) -> Path:
    return _run_store().run_path(run_id)


def _save_run(record: dict[str, Any]) -> None:
    _run_store().save(record)


def _load_run(run_id: str) -> dict[str, Any] | None:
    return _run_store().load(run_id)


def _list_runs(limit: int = 20) -> list[dict[str, Any]]:
    return _run_store().list(limit=limit)


def queue_status() -> dict[str, Any]:
    return _run_queue_service().status()


def _state_summary(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "raw_notes_count": len(state.get("raw_notes") or []),
        "raw_comments_count": len(state.get("raw_comments") or []),
        "comment_insights_count": len(state.get("comment_insights") or []),
        "pain_points_count": len(state.get("pain_points") or []),
        "comment_fetch_errors_count": len(state.get("comment_fetch_errors") or []),
        "retrieved_memory_count": len(state.get("retrieved_memory") or []),
        "successful_patterns_count": len(state.get("successful_patterns") or []),
        "content_format": state.get("content_format"),
        "content_type": state.get("content_type"),
        "compliance_risk_level": state.get("compliance_risk_level"),
        "compliance_issues": state.get("compliance_issues") or [],
        "human_approved": state.get("human_approved"),
        "publish_status": state.get("publish_status"),
        "post_id": state.get("post_id"),
        "operation_memory_written": state.get("operation_memory_written"),
        "operation_record_id": state.get("operation_record_id"),
        "review_summary": state.get("review_summary"),
        "next_action": state.get("next_action"),
        "llm_generation": state.get("llm_generation") or {},
        "review_generation": state.get("review_generation") or {},
    }


def _content_payload(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("content_format") == "video":
        return {
            "video_script": state.get("video_script") or {},
            "tags": state.get("tags") or [],
            "comment_call": state.get("comment_call") or "",
        }

    return {
        "titles": state.get("titles") or [],
        "cover_texts": state.get("cover_texts") or [],
        "body": state.get("body") or "",
        "image_page_plan": state.get("image_page_plan") or [],
        "image_prompts": state.get("image_prompts") or [],
        "tags": state.get("tags") or [],
        "comment_call": state.get("comment_call") or "",
    }


def _insight_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "comment_insights": state.get("comment_insights") or [],
        "pain_points": state.get("pain_points") or [],
        "comment_fetch_errors": state.get("comment_fetch_errors") or [],
    }


def _run_record(
    run_id: str,
    request_payload: dict[str, Any],
    status: str,
    state: dict[str, Any] | None = None,
    error: str | None = None,
    created_at: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> dict[str, Any]:
    state = state or {}
    now = _now_iso()
    return {
        "run_id": run_id,
        "status": status,
        "created_at": created_at or now,
        "updated_at": now,
        "started_at": started_at,
        "finished_at": finished_at,
        "request": request_payload,
        "summary": _state_summary(state) if state else {},
        "content": _content_payload(state) if state else {},
        "insights": _insight_payload(state) if state else {},
        "state": state if state else {},
        "paths": {
            "post_id": state.get("post_id"),
            "collection_path": state.get("collection_path"),
            "operation_memory_path": state.get("operation_memory_path"),
        },
        "error": error,
    }


def _build_run_request(payload: dict[str, Any]) -> dict[str, Any]:
    topic = str(payload.get("topic") or "").strip()
    if not topic:
        raise ValueError("Missing required field: topic")

    content_format = str(payload.get("format") or payload.get("content_format") or "image_text")
    if content_format not in {"image_text", "video"}:
        raise ValueError("content format must be image_text or video")

    engine = str(payload.get("engine") or "langgraph")
    if engine not in {"local", "langgraph"}:
        raise ValueError("engine must be local or langgraph")

    approve = _bool(payload.get("approve"), default=False)
    request_payload = {
        "topic": topic,
        "target_user": str(payload.get("target_user") or "小红书目标用户"),
        "format": content_format,
        "goal": str(payload.get("goal") or "生成一篇冷启动阶段的知识分享内容"),
        "approve": approve,
        "engine": engine,
        "collect_limit": _int(payload.get("collect_limit"), default=5),
        "save_collection": _bool(payload.get("save_collection"), default=False),
    }

    return request_payload


def _initial_state_from_request(request_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_topic": request_payload["topic"],
        "target_user": request_payload["target_user"],
        "user_selected_format": request_payload["format"],
        "user_goal": request_payload["goal"],
        "human_approved": request_payload["approve"],
        "collect_limit": request_payload["collect_limit"],
        "save_collection": request_payload["save_collection"],
    }


def _runner_for_request(request_payload: dict[str, Any]):
    return run_langgraph if request_payload["engine"] == "langgraph" else run_local_graph


def _finish_run(
    existing: dict[str, Any],
    status: str,
    state: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    record = _run_record(
        run_id=existing["run_id"],
        request_payload=existing["request"],
        status=status,
        state=state,
        error=error,
        created_at=existing.get("created_at"),
        started_at=existing.get("started_at"),
        finished_at=_now_iso(),
    )
    _save_run(record)
    return record


def _mark_run_running(existing: dict[str, Any]) -> dict[str, Any]:
    record = _run_record(
        run_id=existing["run_id"],
        request_payload=existing["request"],
        status="running",
        created_at=existing.get("created_at"),
        started_at=_now_iso(),
        finished_at=None,
    )
    _save_run(record)
    return record


def _state_from_record(record: dict[str, Any]) -> dict[str, Any]:
    state = record.get("state")
    if isinstance(state, dict) and state:
        return dict(state)

    request = record.get("request") or {}
    summary = record.get("summary") or {}
    content = record.get("content") or {}
    insights = record.get("insights") or {}
    paths = record.get("paths") or {}
    if not isinstance(request, dict) or not isinstance(content, dict):
        return {}

    restored = {
        "user_topic": request.get("topic"),
        "target_user": request.get("target_user"),
        "user_selected_format": request.get("format"),
        "user_goal": request.get("goal"),
        "collect_limit": request.get("collect_limit"),
        "save_collection": request.get("save_collection"),
        "content_format": summary.get("content_format") or request.get("format"),
        "content_type": summary.get("content_type"),
        "compliance_risk_level": summary.get("compliance_risk_level"),
        "compliance_issues": summary.get("compliance_issues") or [],
        "human_approved": summary.get("human_approved"),
        "publish_status": summary.get("publish_status"),
        "post_id": paths.get("post_id") or summary.get("post_id"),
        "collection_path": paths.get("collection_path"),
        "operation_memory_path": paths.get("operation_memory_path"),
        "pain_points": insights.get("pain_points") or [],
        "comment_insights": insights.get("comment_insights") or [],
        "comment_fetch_errors": insights.get("comment_fetch_errors") or [],
    }
    restored.update(content)
    return restored


def _save_reviewed_run(
    record: dict[str, Any],
    state: dict[str, Any],
    review_action: str,
) -> dict[str, Any]:
    reviewed = _run_record(
        run_id=record["run_id"],
        request_payload=record["request"],
        status="success",
        state=state,
        created_at=record.get("created_at"),
        started_at=record.get("started_at"),
        finished_at=record.get("finished_at"),
    )
    reviewed["approved_at"] = _now_iso() if review_action == "approved" else record.get("approved_at")
    reviewed["reviewed_at"] = _now_iso()
    reviewed["review_action"] = review_action
    _save_run(reviewed)
    return reviewed


def approve_run(run_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    record = _load_run(run_id)
    if not record:
        raise ValueError(f"Run not found: {run_id}")
    if record.get("status") != "success":
        raise ValueError("Only successful generated runs can be approved")

    state = _state_from_record(record)
    if not state or not _content_payload(state):
        raise ValueError("Run does not contain a resumable draft state")
    if state.get("publish_status") == "success":
        return record
    if state.get("compliance_risk_level") == "high":
        raise ValueError("High-risk compliance result cannot be approved directly")

    payload = payload or {}
    feedback = str(payload.get("feedback") or "人工审核通过。").strip()
    state["human_approved"] = True
    state["human_feedback"] = feedback
    state["publish_status"] = "pending"

    state.update(publish_or_schedule(state))
    state.update(review_performance(state))
    state.update(write_operation_memory(state))

    return _save_reviewed_run(record, state, review_action="approved")


def reject_run(run_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    record = _load_run(run_id)
    if not record:
        raise ValueError(f"Run not found: {run_id}")
    if record.get("status") != "success":
        raise ValueError("Only successful generated runs can be rejected")

    state = _state_from_record(record)
    if state.get("publish_status") == "success":
        raise ValueError("Run has already been approved and saved")

    payload = payload or {}
    feedback = str(payload.get("feedback") or "人工审核不通过。").strip()
    topic = state.get("user_topic") or record.get("request", {}).get("topic") or "未命名主题"
    state.update(
        {
            "human_approved": False,
            "human_feedback": feedback,
            "publish_status": "rejected",
            "post_id": None,
            "operation_memory_written": False,
            "operation_memory_path": str(operation_memory_path()),
            "review_summary": f"主题「{topic}」已被人工审核驳回，草稿未保存。",
            "next_action": "根据人工反馈修改主题、结构或合规表达后重新生成。",
            "review_generation": {
                "enabled": False,
                "provider_mode": "manual_review",
                "model": None,
                "usage": {},
            },
        }
    )

    return _save_reviewed_run(record, state, review_action="rejected")


def _execute_run(run_id: str) -> None:
    existing = _load_run(run_id)
    if not existing:
        return
    if existing.get("status") in {"success", "failed"}:
        return

    running = _mark_run_running(existing)
    request_payload = running["request"]
    runner = _runner_for_request(request_payload)
    initial_state = _initial_state_from_request(request_payload)

    try:
        final_state = runner(initial_state)
    except Exception as exc:
        _finish_run(running, status="failed", error=str(exc))
        return

    _finish_run(running, status="success", state=dict(final_state))


def _enqueue_run(run_id: str) -> None:
    _run_queue_service().enqueue(run_id)


def _recover_pending_runs() -> None:
    _run_queue_service().recover_pending_runs()


def create_run(payload: dict[str, Any]) -> dict[str, Any]:
    """Run synchronously. Useful for internal smoke tests."""

    request_payload = _build_run_request(payload)
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    started_at = _now_iso()
    runner = _runner_for_request(request_payload)
    initial_state = _initial_state_from_request(request_payload)

    try:
        final_state = runner(initial_state)
    except Exception as exc:
        record = _run_record(
            run_id,
            request_payload,
            status="failed",
            error=str(exc),
            started_at=started_at,
            finished_at=_now_iso(),
        )
        _save_run(record)
        raise

    record = _run_record(
        run_id,
        request_payload,
        status="success",
        state=dict(final_state),
        started_at=started_at,
        finished_at=_now_iso(),
    )
    _save_run(record)
    return record


def submit_run(payload: dict[str, Any]) -> dict[str, Any]:
    """Submit an asynchronous run and return immediately."""

    request_payload = _build_run_request(payload)
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    record = _run_record(run_id, request_payload, status="queued")
    _save_run(record)
    _enqueue_run(run_id)
    return record


def _compact_memory_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": record.get("record_id"),
        "topic": record.get("topic"),
        "title": record.get("title"),
        "post_id": record.get("post_id"),
        "status": record.get("status"),
        "content_type": record.get("content_type"),
        "content_format": record.get("content_format"),
        "performance_data": record.get("performance_data") or {},
        "performance_score": record.get("performance_score"),
        "review_summary": record.get("review_summary"),
        "next_action": record.get("next_action"),
        "review_generation": record.get("review_generation") or {},
        "updated_at": record.get("updated_at"),
    }


def list_memory_records(limit: int = 20) -> dict[str, Any]:
    history = load_history()
    records = [
        record
        for record in history.get("records") or []
        if isinstance(record, dict)
    ]
    records = records[-limit:]
    return {
        "memory_path": str(operation_memory_path()),
        "records": [_compact_memory_record(record) for record in records],
    }


def record_performance(payload: dict[str, Any]) -> dict[str, Any]:
    post_id = str(payload.get("post_id") or "").strip()
    if not post_id:
        raise ValueError("Missing required field: post_id")

    performance_data = {
        "views": _int(payload.get("views"), default=0),
        "likes": _int(payload.get("likes"), default=0),
        "collects": _int(payload.get("collects"), default=0),
        "comments": _int(payload.get("comments"), default=0),
        "follows": _int(payload.get("follows"), default=0),
    }
    record = update_record_performance(
        post_id=post_id,
        performance_data=performance_data,
        published_url=str(payload.get("published_url") or "").strip() or None,
        notes=str(payload.get("notes") or "").strip() or None,
    )
    return {
        "memory_path": str(operation_memory_path()),
        "updated_record": _compact_memory_record(record),
    }


class XHSAgentAPIHandler(BaseHTTPRequestHandler):
    server_version = "XHSAgentAPI/0.1"

    def _send_json(self, status: int, payload: Any) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self._send_error(404, f"Static file not found: {path.name}")
            return

        body = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if path.suffix == ".js":
            content_type = "application/javascript"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = _int(self.headers.get("Content-Length"), default=0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object")
        return data

    def _send_error(self, status: int, message: str) -> None:
        self._send_json(status, {"ok": False, "error": message})

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json(200, {"ok": True})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        limit = _int((query.get("limit") or [20])[0], default=20)

        static_path = _static_path(path)
        if static_path:
            self._send_file(static_path)
            return

        if path == "/health":
            self._send_json(200, {"ok": True, "service": "xhs-agent-api", "time": _now_iso()})
            return

        if path == "/runs":
            self._send_json(
                200,
                {
                    "ok": True,
                    "runs": [
                        {
                            "run_id": run.get("run_id"),
                            "status": run.get("status"),
                            "created_at": run.get("created_at"),
                            "updated_at": run.get("updated_at"),
                            "started_at": run.get("started_at"),
                            "finished_at": run.get("finished_at"),
                            "request": run.get("request"),
                            "summary": run.get("summary"),
                        }
                        for run in _list_runs(limit=limit)
                    ],
                },
            )
            return

        if path == "/queue":
            self._send_json(200, {"ok": True, **queue_status()})
            return

        if path.startswith("/runs/"):
            run_id = path.split("/", 2)[2]
            record = _load_run(run_id)
            if not record:
                self._send_error(404, f"Run not found: {run_id}")
                return
            self._send_json(200, {"ok": True, "run": record})
            return

        if path == "/memory/records":
            self._send_json(200, {"ok": True, **list_memory_records(limit=limit)})
            return

        self._send_error(404, f"Unknown endpoint: {path}")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        try:
            payload = self._read_json()
            if path == "/runs":
                record = submit_run(payload)
                self._send_json(202, {"ok": True, "run": record})
                return

            if path == "/performance":
                result = record_performance(payload)
                self._send_json(200, {"ok": True, **result})
                return

            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[0] == "runs" and parts[2] == "approve":
                record = approve_run(parts[1], payload)
                self._send_json(200, {"ok": True, "run": record})
                return

            if len(parts) == 3 and parts[0] == "runs" and parts[2] == "reject":
                record = reject_run(parts[1], payload)
                self._send_json(200, {"ok": True, "run": record})
                return

            self._send_error(404, f"Unknown endpoint: {path}")
        except ValueError as exc:
            self._send_error(400, str(exc))
        except Exception as exc:  # Keep the HTTP API alive if the graph fails.
            self._send_error(500, str(exc))

    def log_message(self, format: str, *args: Any) -> None:
        timestamp = _now_iso()
        print(f"[{timestamp}] {self.address_string()} {format % args}")


def run_server(host: str = "127.0.0.1", port: int = 8010) -> None:
    _recover_pending_runs()
    server = ThreadingHTTPServer((host, port), XHSAgentAPIHandler)
    print(f"XHS Agent API listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
