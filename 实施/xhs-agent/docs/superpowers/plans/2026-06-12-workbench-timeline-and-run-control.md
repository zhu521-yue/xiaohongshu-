# 工作台事件时间线与任务控制实施计划

## 目标

在 `run_events` 和 SQLite 队列事件已经可写可查后，补齐两个工程化能力：工作台只读展示事件时间线/队列诊断，以及 API/SQLite 队列的显式取消和超时标记。

## 架构

- 后端队列层继续由 `SQLiteRunQueue` 管理 job 状态。
- API 层新增 run 控制函数，负责同步更新 run record 和 SQLite queue job。
- 工作台只读事件时间线通过现有 `/business/runs/{run_id}` 读取，不改变 `/runs/{run_id}`。
- 工作台队列诊断复用 `/queue` 的 `jobs` 明细，并通过 `/runs/{run_id}/cancel`、`/runs/{run_id}/timeout` 做显式控制。

## 已纳入范围

- `SQLiteRunQueue.cancel()`：把 queued/running job 标记为 `cancelled`，记录 `queue_cancelled`。
- `SQLiteRunQueue.mark_timed_out()`：把 queued/running job 标记为 `timed_out`，记录 `queue_timed_out`。
- `queue_status()` 在 SQLite backend 下返回 `cancelled_count`、`timed_out_count` 和对应 run ID 列表。
- `app.api.cancel_run()` 与 `app.api.timeout_run()` 更新 run 状态并记录 lifecycle 事件。
- `_finish_run()` 避免 worker 后续把已 `cancelled` 或 `timed_out` 的 run 覆盖成 success/failed。
- 工作台结果区新增 `runTimeline`，展示 run lifecycle、queue events、graph node events。
- 工作台队列区展示 job 明细和取消/标记超时按钮。

## 当前不做

- 不强杀正在执行的 Python 线程。
- 不中断已经发出的真实平台发布请求。
- 不引入 Redis、Celery、RQ、多队列或优先级队列。
- 不做自动 watchdog 后台扫描；本轮超时是显式标记能力。

## 验证

- `tests/test_sqlite_run_queue.py` 覆盖取消、超时和事件记录。
- `tests/test_api_run_control.py` 覆盖 API 控制函数、run 状态和 queue 状态联动。
- `tests/test_workbench_event_timeline_static.py` 覆盖工作台时间线、队列诊断和控制按钮。
- 聚焦回归、JS 语法检查、compileall、全量 pytest 和工作台 smoke 作为收口验证。
