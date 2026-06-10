# SQLite Run Queue Design

## Goal

M16a introduces a SQLite-backed run queue so the API process can submit jobs without executing them in an in-process worker thread. A separate worker script will claim queued jobs from SQLite and execute the existing run pipeline.

This is an incremental engineering step between the current `LocalRunQueue` and a future Redis/RQ or Celery queue. It uses only the Python standard library and the existing SQLite database path.

## Current State

The project currently has:

- `app.run_queue.LocalRunQueue`
  - stores queued `run_id` values in process memory
  - starts daemon worker threads inside the API process
  - recovers queued/running runs by scanning the run store at API startup
- `app.run_store.SQLiteRunStore`
  - stores run records in SQLite when `XHS_AGENT_RUN_STORE=sqlite`
  - keeps the public `_save_run()`, `_load_run()`, and `_list_runs()` API behavior stable
- `app.api.submit_run()`
  - creates a `queued` run record
  - calls `_enqueue_run(run_id)`
  - returns immediately to HTTP callers

The gap is that queued work is still owned by the API process when `LocalRunQueue` is used. If the API process exits, the in-memory queue disappears. Multiple API processes or external workers cannot coordinate through the current queue.

## Chosen Approach

Use SQLite as a persistent queue backend.

Add `SQLiteRunQueue` next to `LocalRunQueue` in `app/run_queue.py`. The API will select a queue backend through configuration:

```env
XHS_AGENT_RUN_QUEUE=local
XHS_AGENT_QUEUE_DB_PATH=data/xhs_agent.sqlite3
XHS_AGENT_WORKER_ID=
XHS_AGENT_QUEUE_POLL_SECONDS=1
XHS_AGENT_QUEUE_MAX_ATTEMPTS=3
XHS_AGENT_QUEUE_LOCK_TIMEOUT_SECONDS=900
```

Default behavior remains local. SQLite queue behavior is enabled only when `XHS_AGENT_RUN_QUEUE=sqlite`.

## Queue Table

Create a `run_queue_jobs` table in the configured SQLite database:

```sql
CREATE TABLE IF NOT EXISTS run_queue_jobs (
    run_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    available_at TEXT NOT NULL,
    locked_at TEXT,
    locked_by TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finished_at TEXT
);
```

Indexes:

```sql
CREATE INDEX IF NOT EXISTS idx_run_queue_jobs_status_available
ON run_queue_jobs(status, available_at);

CREATE INDEX IF NOT EXISTS idx_run_queue_jobs_locked_at
ON run_queue_jobs(locked_at);
```

Status values:

- `queued`: waiting to be claimed
- `running`: claimed by a worker
- `succeeded`: worker finished successfully
- `failed`: worker exhausted retry attempts

## Queue Interface

Keep the API-facing queue interface small:

- `enqueue(run_id: str) -> None`
- `recover_pending_runs() -> None`
- `status() -> dict[str, Any]`

Add worker-facing methods on `SQLiteRunQueue`:

- `claim_next(worker_id: str) -> str | None`
- `mark_succeeded(run_id: str, worker_id: str) -> None`
- `mark_failed(run_id: str, worker_id: str, error: str) -> bool`

`mark_failed()` returns `True` when the job is terminally failed and `False` when it was requeued for another attempt.

`LocalRunQueue` does not need the worker-facing methods because it remains an in-process development backend.

## Enqueue Behavior

`SQLiteRunQueue.enqueue(run_id)` inserts or requeues a job:

- If no row exists, insert `queued` with `attempts=0`.
- If row is `queued`, leave it unchanged.
- If row is `running`, leave it unchanged unless its lock is expired.
- If row is `failed`, reset to `queued` only if the run store still has the run in `queued` or `running` status.
- If row is `succeeded`, leave it unchanged.

This keeps duplicate HTTP submissions and startup recovery idempotent.

## Claim Behavior

`claim_next(worker_id)` claims one job using a short SQLite transaction:

1. Find the oldest job where:
   - `status='queued'`
   - `available_at <= now`
2. Also allow stale `running` jobs when:
   - `locked_at < now - lock_timeout_seconds`
   - `attempts < max_attempts`
3. Update the selected job:
   - `status='running'`
   - `attempts=attempts+1`
   - `locked_at=now`
   - `locked_by=worker_id`
   - `updated_at=now`
4. Return the claimed `run_id`.

If no job is available, return `None`.

SQLite does not provide PostgreSQL-style `SKIP LOCKED`, so the implementation will use a Python lock per process and SQLite transaction boundaries. This is sufficient for the local multi-process worker target of M16a. Redis/RQ remains the later production queue path.

## API Integration

Add settings:

- `run_queue_backend`
- `queue_db_path`
- `queue_poll_seconds`
- `queue_max_attempts`
- `queue_lock_timeout_seconds`

Update `app.api._run_queue_service()`:

- If `XHS_AGENT_RUN_QUEUE=local`, instantiate `LocalRunQueue` exactly as today.
- If `XHS_AGENT_RUN_QUEUE=sqlite`, instantiate `SQLiteRunQueue` with no embedded worker thread.

When using SQLite queue:

- `submit_run()` still saves the run as `queued`.
- `_enqueue_run()` writes the queue row.
- `run_server()` calls `_recover_pending_runs()`, but this only makes sure queue rows exist for run records still marked `queued` or `running`.
- The API process does not execute background jobs.

`GET /queue` should return:

- `worker_backend`: `local` or `sqlite`
- `queued_count`
- `running_count`
- `queued_run_ids`
- `running_run_ids`
- `failed_count`
- `failed_run_ids`

## Worker Entry Point

Create `scripts/run_worker.py`.

The worker script will:

1. Load settings and select the queue backend.
2. Require `XHS_AGENT_RUN_QUEUE=sqlite`.
3. Generate a worker id when `XHS_AGENT_WORKER_ID` is empty.
4. Loop:
   - call `claim_next(worker_id)`
   - if no job exists, sleep `XHS_AGENT_QUEUE_POLL_SECONDS`
   - if a job exists, call `app.api._execute_run(run_id)`
   - if `_execute_run()` returns without raising, call `mark_succeeded()`
   - if `_execute_run()` raises, call `mark_failed()`

The current `_execute_run()` catches graph exceptions and marks the run as `failed`. Because of that, the worker must inspect the resulting run record after `_execute_run()` returns:

- If run status is `success`, mark queue job `succeeded`.
- If run status is `failed`, call `mark_failed()` with the run error.
- If run status remains `queued` or `running`, call `mark_failed()` with a defensive error message.

This avoids changing the core execution path in M16a.

## Failure And Retry Rules

Queue-level retry is conservative:

- Default max attempts: 3.
- On failure before max attempts, set job back to `queued`.
- On terminal failure, set job to `failed`.
- `last_error` stores the latest failure message.
- The run record remains the source of truth for generated content and final run status.

For M16a, retry re-executes the entire run. That is acceptable because the current pipeline is already task-level, not node-level. Node-level retry and partial resume are future LangGraph orchestration work.

## Recovery Rules

`SQLiteRunQueue.recover_pending_runs()` scans the run store for records with `status` in `queued` or `running` and calls `enqueue(run_id)`.

This keeps existing behavior compatible:

- If the API submitted a run but crashed before a worker picked it up, recovery creates or keeps the queue row.
- If a worker crashed while a job was running, lock timeout makes the job claimable again.
- If the run record already finished as `success` or `failed`, recovery does not enqueue it.

## Testing Scope

Add tests for:

- SQLite queue enqueues a run id once.
- SQLite queue status reports queued and running jobs.
- `claim_next()` locks exactly one job.
- A second worker cannot claim the same locked job.
- `mark_succeeded()` removes the job from active status.
- `mark_failed()` requeues before max attempts.
- `mark_failed()` marks terminal failure after max attempts.
- stale running jobs become claimable after lock timeout.
- API queue selection uses `LocalRunQueue` by default.
- API queue selection uses `SQLiteRunQueue` when configured.

Final verification:

```powershell
python -m pytest -q
python -m compileall app nodes routers platforms memory scripts llm
```

Add one smoke check that uses a temporary SQLite database, mock collector, mock LLM, and one worker pass to prove:

- `submit_run()` returns a queued record.
- the worker claims and executes the run.
- the run becomes `success`.
- the queue job becomes `succeeded`.

## Out Of Scope

M16a does not include:

- Redis, RQ, Celery, Dramatiq, or any new queue dependency.
- Docker Compose or server deployment.
- API authentication.
- LangGraph interrupt/resume.
- node-level retries.
- cancellation endpoints.
- queue priority.
- scheduled future jobs beyond immediate `available_at`.
- frontend queue management UI.

## Rollback

Rollback is environment-based:

- Set `XHS_AGENT_RUN_QUEUE=local` to use the current in-process queue.
- Keep `XHS_AGENT_RUN_STORE=json` if local JSON run files are preferred.
- SQLite queue rows can remain in the database; they are ignored by the local queue backend.

## Self-Review

- Placeholder scan: no unfinished placeholders remain.
- Internal consistency: API owns submission and status; worker owns execution; run store remains source of truth for run records.
- Scope check: the spec is limited to SQLite queue and worker entry point. Redis/RQ and deployment stay out of scope.
- Ambiguity check: default behavior remains local; SQLite queue is opt-in through `XHS_AGENT_RUN_QUEUE=sqlite`.
