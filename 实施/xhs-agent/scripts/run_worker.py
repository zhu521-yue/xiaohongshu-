from __future__ import annotations

import argparse
import logging
import socket
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import api  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
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
    logger: logging.Logger | None = None,
    heartbeat_interval_seconds: float = 0.0,
) -> bool:
    logger = logger or logging.getLogger("xhs_agent.worker")
    run_id = queue.claim_next(worker_id)
    if not run_id:
        return False

    logger.info("worker_claimed run_id=%s worker_id=%s", run_id, worker_id)
    _record_heartbeat(queue, run_id, worker_id, logger)
    stop_heartbeat = threading.Event()
    heartbeat_thread = _start_periodic_heartbeat(
        queue,
        run_id=run_id,
        worker_id=worker_id,
        interval_seconds=heartbeat_interval_seconds,
        stop_event=stop_heartbeat,
        logger=logger,
    )
    try:
        execute_run(run_id)
        record = load_run(run_id) or {}
        status = record.get("status")
        if status == "success":
            queue.mark_succeeded(run_id, worker_id)
            logger.info("worker_succeeded run_id=%s worker_id=%s", run_id, worker_id)
        elif status == "failed":
            error = str(record.get("error") or "run failed")
            queue.mark_failed(run_id, worker_id, error)
            logger.warning("worker_failed run_id=%s worker_id=%s error=%s", run_id, worker_id, error)
        else:
            error = f"run ended with unexpected status: {status}"
            queue.mark_failed(run_id, worker_id, error)
            logger.warning("worker_failed run_id=%s worker_id=%s error=%s", run_id, worker_id, error)
    except Exception as exc:
        queue.mark_failed(run_id, worker_id, str(exc))
        logger.exception("worker_exception run_id=%s worker_id=%s", run_id, worker_id)
    finally:
        stop_heartbeat.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join(timeout=1.0)
    return True


def _record_heartbeat(
    queue: SQLiteRunQueue,
    run_id: str,
    worker_id: str,
    logger: logging.Logger,
) -> bool:
    heartbeat = getattr(queue, "heartbeat", None)
    if not callable(heartbeat):
        return False
    try:
        return bool(heartbeat(run_id, worker_id))
    except Exception as exc:
        logger.warning("worker_heartbeat_failed run_id=%s worker_id=%s error=%s", run_id, worker_id, exc)
        return False


def _start_periodic_heartbeat(
    queue: SQLiteRunQueue,
    *,
    run_id: str,
    worker_id: str,
    interval_seconds: float,
    stop_event: threading.Event,
    logger: logging.Logger,
) -> threading.Thread | None:
    interval = max(0.0, float(interval_seconds or 0.0))
    if interval <= 0:
        return None
    if not callable(getattr(queue, "heartbeat", None)):
        return None

    def _heartbeat_loop() -> None:
        while not stop_event.wait(interval):
            _record_heartbeat(queue, run_id, worker_id, logger)

    thread = threading.Thread(
        target=_heartbeat_loop,
        name=f"xhs-agent-heartbeat-{run_id}",
        daemon=True,
    )
    thread.start()
    return thread


def run_watchdog_once(
    queue: SQLiteRunQueue,
    *,
    max_seconds: int,
    worker_id: str,
    reason: str | None = None,
) -> list[str]:
    timed_out = queue.mark_stale_running_as_timed_out(
        max_seconds=max_seconds,
        worker_id=worker_id,
        reason=reason,
    )
    logging.getLogger("xhs_agent.worker").info(
        "watchdog_scanned timed_out_count=%s worker_id=%s",
        len(timed_out),
        worker_id,
    )
    return timed_out


def run_watchdog_loop(
    queue: SQLiteRunQueue,
    *,
    max_seconds: int,
    worker_id: str,
    poll_seconds: float,
    reason: str | None = None,
    scan_limit: int | None = None,
) -> int:
    scans = 0
    while True:
        run_watchdog_once(
            queue,
            max_seconds=max_seconds,
            worker_id=worker_id,
            reason=reason,
        )
        scans += 1
        if scan_limit is not None and scans >= scan_limit:
            return scans
        time.sleep(max(0.0, poll_seconds))


def run_loop(worker_id: str, poll_seconds: float, heartbeat_interval_seconds: float) -> None:
    logger = logging.getLogger("xhs_agent.worker")
    queue = api._run_queue_service()
    if not isinstance(queue, SQLiteRunQueue):
        raise RuntimeError("scripts/run_worker.py requires XHS_AGENT_RUN_QUEUE=sqlite")

    while True:
        did_work = run_once(
            queue=queue,
            worker_id=worker_id,
            logger=logger,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
        )
        if not did_work:
            time.sleep(max(0.1, poll_seconds))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SQLite queue worker for xhs-agent.")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job and exit.")
    parser.add_argument("--watchdog-once", action="store_true", help="Mark stale running jobs as timed out and exit.")
    parser.add_argument("--watchdog-loop", action="store_true", help="Continuously scan stale running jobs and mark them timed out.")
    parser.add_argument("--worker-id", default=None, help="Stable worker id for queue locks.")
    args = parser.parse_args(argv)

    settings = load_settings()
    worker_id = build_worker_id(args.worker_id or settings.worker_id)
    logger = configure_logging("worker")
    logger.info(
        "worker_starting worker_id=%s once=%s watchdog_once=%s watchdog_loop=%s",
        worker_id,
        args.once,
        args.watchdog_once,
        args.watchdog_loop,
    )
    queue = api._run_queue_service()
    if not isinstance(queue, SQLiteRunQueue):
        raise RuntimeError("scripts/run_worker.py requires XHS_AGENT_RUN_QUEUE=sqlite")

    if args.watchdog_once:
        run_watchdog_once(
            queue=queue,
            max_seconds=settings.queue_heartbeat_timeout_seconds,
            worker_id=worker_id,
        )
        return 0

    if args.watchdog_loop:
        run_watchdog_loop(
            queue=queue,
            max_seconds=settings.queue_heartbeat_timeout_seconds,
            worker_id=worker_id,
            poll_seconds=settings.queue_poll_seconds,
        )
        return 0

    if args.once:
        return 0 if run_once(
            queue=queue,
            worker_id=worker_id,
            logger=logger,
            heartbeat_interval_seconds=settings.queue_heartbeat_interval_seconds,
        ) else 1

    run_loop(
        worker_id=worker_id,
        poll_seconds=settings.queue_poll_seconds,
        heartbeat_interval_seconds=settings.queue_heartbeat_interval_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
