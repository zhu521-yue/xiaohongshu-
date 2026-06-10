"""Local task queue boundary.

This is still an in-process queue, but the API layer no longer owns the queue
implementation. A Redis/Celery backend can later implement the same public
methods and replace this class.
"""

from __future__ import annotations

import threading
from queue import Queue
from typing import Any, Callable


class LocalRunQueue:
    def __init__(
        self,
        execute_run: Callable[[str], None],
        list_runs: Callable[[int], list[dict[str, Any]]],
        worker_count: int = 1,
    ) -> None:
        self._execute_run = execute_run
        self._list_runs = list_runs
        self._worker_count = max(1, int(worker_count or 1))
        self._queue: Queue[str] = Queue()
        self._lock = threading.RLock()
        self._enqueued_run_ids: set[str] = set()
        self._started_workers = 0

    def enqueue(self, run_id: str) -> None:
        with self._lock:
            if run_id in self._enqueued_run_ids:
                return
            self._enqueued_run_ids.add(run_id)
            self._queue.put(run_id)
            self._ensure_workers_started()

    def recover_pending_runs(self) -> None:
        pending = [
            run
            for run in self._list_runs(10000)
            if run.get("status") in {"queued", "running"}
        ]
        pending.sort(key=lambda item: str(item.get("created_at") or ""))
        for run in pending:
            run_id = str(run.get("run_id") or "")
            if run_id:
                self.enqueue(run_id)

    def status(self) -> dict[str, Any]:
        runs = self._list_runs(10000)
        queued = [run for run in runs if run.get("status") == "queued"]
        running = [run for run in runs if run.get("status") == "running"]
        return {
            "queued_count": len(queued),
            "running_count": len(running),
            "queued_run_ids": [
                run.get("run_id")
                for run in sorted(queued, key=lambda item: str(item.get("created_at") or ""))
            ],
            "running_run_ids": [run.get("run_id") for run in running],
            "worker_backend": "local",
            "worker_count": self._worker_count,
        }

    def _ensure_workers_started(self) -> None:
        while self._started_workers < self._worker_count:
            index = self._started_workers + 1
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"xhs-agent-worker-{index}",
                daemon=True,
            )
            worker.start()
            self._started_workers += 1

    def _worker_loop(self) -> None:
        while True:
            run_id = self._queue.get()
            try:
                self._execute_run(run_id)
            finally:
                with self._lock:
                    self._enqueued_run_ids.discard(run_id)
                self._queue.task_done()
