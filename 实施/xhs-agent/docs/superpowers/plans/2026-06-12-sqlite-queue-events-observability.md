# SQLite 队列事件可观测性实施计划

## 目标

在 `run_events` 基础时间线已经可写可查后，把 SQLite 队列和 worker 的关键状态变化接入同一条时间线，让任务排队、领取、重试、恢复、成功和终态失败可以被统一诊断。

## 架构

- 新增 `app/queue_events.py` 作为队列事件适配层，只负责把队列语义转换为 `record_run_event()` 调用。
- `app/run_queue.py` 继续负责队列状态机，不直接拼装 `run_events` payload。
- `app/api.py` 只在 SQLite run store、`XHS_AGENT_DB_SCHEMA=foundation`、`XHS_AGENT_BUSINESS_TABLES_ENABLED=true` 同时满足时，为 SQLite 队列传入事件数据库路径。
- 事件写入是 best-effort，失败不阻断 enqueue、claim、mark_succeeded 或 mark_failed。

## 事件类型

- `queue_enqueued`：任务进入 SQLite 队列。
- `queue_claimed`：worker 领取 queued 任务。
- `queue_reclaimed`：worker 重新领取 stale running 任务。
- `queue_requeued`：任务失败但未达到最大尝试次数，重新回到 queued。
- `queue_succeeded`：worker 标记队列任务成功。
- `queue_failed`：任务达到最大尝试次数或队列记录缺失时进入终态失败。

## 当前不做

- 不引入 Redis、RQ、Celery 或其它新队列技术。
- 不实现任务取消、业务超时中断、优先级队列或多队列拆分。
- 不改变 `/runs/{run_id}` 响应结构。
- 不新增前端工作台展示。
- 不自动重试 creator 真实发布类副作用操作；本轮只记录队列状态变化。

## 验证

- `tests/test_queue_events.py` 覆盖队列事件适配层。
- `tests/test_sqlite_run_queue.py` 覆盖 SQLite 队列事件写入、stale reclaim 事件和状态明细。
- `tests/test_api_run_queue_selection.py` 覆盖 API 配置开启后向队列传入事件 DB。
- `tests/test_run_worker.py` 覆盖 worker 成功路径会触发队列事件。
- 聚焦回归、编译检查和全量 pytest 作为收口验证。
