from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import api  # noqa: E402
from memory import operation_store  # noqa: E402
from scripts import run_worker  # noqa: E402


_SMOKE_ENV_KEYS = (
    "XHS_AGENT_RUN_STORE",
    "XHS_AGENT_RUN_DB_PATH",
    "XHS_AGENT_RUN_QUEUE",
    "XHS_AGENT_QUEUE_DB_PATH",
    "XHS_AGENT_MEMORY_STORE",
    "XHS_AGENT_MEMORY_DB_PATH",
    "XHS_AGENT_DB_SCHEMA",
    "XHS_AGENT_BUSINESS_TABLES_ENABLED",
    "XHS_AGENT_QUEUE_HEARTBEAT_INTERVAL_SECONDS",
    "XHS_AGENT_QUEUE_HEARTBEAT_TIMEOUT_SECONDS",
    "COLLECTOR_MODE",
    "LLM_MODEL_NAME",
    "CREATOR_MODE",
)


def _reset_services() -> None:
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    operation_store.MEMORY_BACKEND = None


@contextmanager
def _sqlite_smoke_environment(db_path: Path) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in _SMOKE_ENV_KEYS}
    os.environ.update(
        {
            "XHS_AGENT_RUN_STORE": "sqlite",
            "XHS_AGENT_RUN_DB_PATH": str(db_path),
            "XHS_AGENT_RUN_QUEUE": "sqlite",
            "XHS_AGENT_QUEUE_DB_PATH": str(db_path),
            "XHS_AGENT_MEMORY_STORE": "sqlite",
            "XHS_AGENT_MEMORY_DB_PATH": str(db_path),
            "XHS_AGENT_DB_SCHEMA": "foundation",
            "XHS_AGENT_BUSINESS_TABLES_ENABLED": "true",
            "XHS_AGENT_QUEUE_HEARTBEAT_INTERVAL_SECONDS": "0.1",
            "XHS_AGENT_QUEUE_HEARTBEAT_TIMEOUT_SECONDS": "60",
            "COLLECTOR_MODE": "mock",
            "LLM_MODEL_NAME": "mock",
            "CREATOR_MODE": "mock",
        }
    )
    _reset_services()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _reset_services()


def run_sqlite_stack_smoke(
    *,
    db_path: str | Path,
    worker_id: str = "sqlite-smoke-worker",
    watchdog_worker_id: str = "sqlite-smoke-watchdog",
    topic: str = "小红书新手选题方法",
    target_user: str = "内容创作新手",
    content_format: str = "image_text",
    engine: str = "local",
    collect_limit: int = 2,
) -> dict[str, Any]:
    """Run an in-process SQLite API/worker/watchdog/business-table smoke check."""

    resolved_db_path = Path(db_path)
    resolved_db_path.parent.mkdir(parents=True, exist_ok=True)
    with _sqlite_smoke_environment(resolved_db_path):
        submitted = api.submit_run(
            {
                "topic": topic,
                "target_user": target_user,
                "format": content_format,
                "engine": engine,
                "approve": False,
                "collect_limit": collect_limit,
            }
        )
        run_id = submitted["run_id"]
        did_work = run_worker.run_once(
            queue=api._run_queue_service(),
            worker_id=worker_id,
            heartbeat_interval_seconds=0.1,
        )
        timed_out = run_worker.run_watchdog_once(
            queue=api._run_queue_service(),
            max_seconds=60,
            worker_id=watchdog_worker_id,
        )
        loaded = api._load_run(run_id) or {}
        queue = api.queue_status()
        business_run = api.get_business_run_snapshot(run_id)["business_run"]
        event_types = [
            str(event.get("event_type"))
            for event in business_run.get("run_events") or []
            if event.get("event_type")
        ]
        checks = {
            "worker_processed": bool(did_work),
            "run_succeeded": loaded.get("status") == "success",
            "queue_drained": queue.get("queued_count") == 0 and queue.get("running_count") == 0,
            "business_snapshot_available": business_run.get("run_id") == run_id,
            "run_events_recorded": int((business_run.get("counts") or {}).get("run_events") or 0) > 0,
        }
        return {
            "ok": all(checks.values()) and not timed_out,
            "db_path": str(resolved_db_path),
            "run": {
                "run_id": run_id,
                "status": loaded.get("status"),
                "failure_category": loaded.get("failure_category"),
                "summary": loaded.get("summary") or {},
            },
            "queue": queue,
            "watchdog": {"timed_out_run_ids": timed_out},
            "business_run": business_run,
            "event_types": event_types,
            "checks": checks,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an in-process SQLite API/worker/watchdog/business-table smoke check."
    )
    parser.add_argument("--db-path", default=None, help="SQLite DB path. Defaults to an ignored data/ smoke DB.")
    parser.add_argument("--worker-id", default="sqlite-smoke-worker", help="Worker id for the smoke job.")
    parser.add_argument(
        "--watchdog-worker-id",
        default="sqlite-smoke-watchdog",
        help="Worker id used by the watchdog scan.",
    )
    parser.add_argument("--topic", default="小红书新手选题方法", help="Smoke run topic.")
    parser.add_argument("--target-user", default="内容创作新手", help="Smoke run target user.")
    parser.add_argument("--format", default="image_text", choices=("image_text", "video"), dest="content_format")
    parser.add_argument("--engine", default="local", choices=("local", "langgraph"), help="Workflow engine.")
    parser.add_argument("--collect-limit", type=int, default=2, help="Mock collector limit.")
    return parser


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.db_path:
        result = run_sqlite_stack_smoke(
            db_path=Path(args.db_path),
            worker_id=args.worker_id,
            watchdog_worker_id=args.watchdog_worker_id,
            topic=args.topic,
            target_user=args.target_user,
            content_format=args.content_format,
            engine=args.engine,
            collect_limit=args.collect_limit,
        )
    else:
        temp_root = ROOT / "data"
        temp_root.mkdir(parents=True, exist_ok=True)
        result = run_sqlite_stack_smoke(
            db_path=temp_root / f"sqlite_stack_smoke_{uuid.uuid4().hex[:8]}.sqlite3",
            worker_id=args.worker_id,
            watchdog_worker_id=args.watchdog_worker_id,
            topic=args.topic,
            target_user=args.target_user,
            content_format=args.content_format,
            engine=args.engine,
            collect_limit=args.collect_limit,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
