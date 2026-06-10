from __future__ import annotations

import argparse
import socket
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import api  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.run_queue import SQLiteRunQueue  # noqa: E402


def build_worker_id(configured_worker_id: str | None = None) -> str:
    configured = str(configured_worker_id or "").strip()
    if configured:
        return configured
    return f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


def run_once(
    queue: SQLiteRunQueue,
    worker_id: str,
    execute_run: Callable[[str], None] = api._execute_run,
    load_run: Callable[[str], dict[str, Any] | None] = api._load_run,
) -> bool:
    run_id = queue.claim_next(worker_id)
    if not run_id:
        return False

    try:
        execute_run(run_id)
        record = load_run(run_id) or {}
        status = record.get("status")
        if status == "success":
            queue.mark_succeeded(run_id, worker_id)
        elif status == "failed":
            queue.mark_failed(run_id, worker_id, str(record.get("error") or "run failed"))
        else:
            queue.mark_failed(run_id, worker_id, f"run ended with unexpected status: {status}")
    except Exception as exc:
        queue.mark_failed(run_id, worker_id, str(exc))
    return True


def run_loop(worker_id: str, poll_seconds: float) -> None:
    queue = api._run_queue_service()
    if not isinstance(queue, SQLiteRunQueue):
        raise RuntimeError("scripts/run_worker.py requires XHS_AGENT_RUN_QUEUE=sqlite")

    while True:
        did_work = run_once(queue=queue, worker_id=worker_id)
        if not did_work:
            time.sleep(max(0.1, poll_seconds))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SQLite queue worker for xhs-agent.")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job and exit.")
    parser.add_argument("--worker-id", default=None, help="Stable worker id for queue locks.")
    args = parser.parse_args(argv)

    settings = load_settings()
    worker_id = build_worker_id(args.worker_id or settings.worker_id)
    queue = api._run_queue_service()
    if not isinstance(queue, SQLiteRunQueue):
        raise RuntimeError("scripts/run_worker.py requires XHS_AGENT_RUN_QUEUE=sqlite")

    if args.once:
        return 0 if run_once(queue=queue, worker_id=worker_id) else 1

    run_loop(worker_id=worker_id, poll_seconds=settings.queue_poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
