# worker 周期心跳与 watchdog loop 设计

## 目标

本轮继续上一轮 worker 心跳/watchdog 初版，补齐两个工程化缺口：

- worker 执行长任务期间周期刷新 `heartbeat_at`，避免 watchdog 把仍在执行的任务误判为过期。
- watchdog 支持常驻循环入口，方便通过启动模板或独立进程持续扫描 stale running job。

本轮仍不引入 Redis、RQ、Celery，不强杀 Python 线程，不撤销已经发出的真实平台请求。

## 当前基础

已经具备：

- `run_queue_jobs.heartbeat_at`
- `SQLiteRunQueue.heartbeat()`
- `SQLiteRunQueue.mark_stale_running_as_timed_out()`
- `scripts/run_worker.py --watchdog-once`
- 工作台事件时间线的 `queue_heartbeat` 展示

缺口：

- `run_once()` 只在领取任务后写一次 heartbeat。
- watchdog 只能跑一次，不能以常驻进程形态定期扫描。
- 启动模板没有 watchdog 模式。
- 配置检查没有明确提示 heartbeat interval、timeout 与 events 组合状态。

## 设计

### worker 周期心跳

`run_once()` 增加 `heartbeat_interval_seconds` 参数。行为：

- 领取任务后立即写一次 heartbeat，保留上一轮行为。
- 当 `heartbeat_interval_seconds > 0` 且队列支持 `heartbeat()` 时，启动一个 daemon 心跳线程。
- 心跳线程每隔 interval 调用 `queue.heartbeat(run_id, worker_id)`。
- `execute_run()` 返回或抛异常后停止线程。
- 心跳失败只记录 warning，不影响任务主流程。

### watchdog loop

新增 `run_watchdog_loop()`：

- 循环调用 `run_watchdog_once()`。
- 每次扫描后按 `poll_seconds` 等待。
- CLI 新增 `--watchdog-loop`。
- 为测试提供可选 `scan_limit`，生产路径不传。

### 配置

新增：

- `XHS_AGENT_QUEUE_HEARTBEAT_INTERVAL_SECONDS=30`

沿用：

- `XHS_AGENT_QUEUE_HEARTBEAT_TIMEOUT_SECONDS=1800`
- `XHS_AGENT_QUEUE_POLL_SECONDS=1`

约束：

- heartbeat interval 必须大于 0。
- heartbeat interval 应小于 heartbeat timeout。

### 启动模板

`scripts/start_sqlite_worker.ps1` 新增：

- `HeartbeatIntervalSeconds`
- `HeartbeatTimeoutSeconds`
- `Watchdog`

当传入 `-Watchdog` 时，启动 `scripts/run_worker.py --watchdog-loop`；否则启动普通 worker。

### 配置检查

`scripts/check_runtime_config.py --profile sqlite-worker` 增加：

- heartbeat interval 检查。
- heartbeat interval 与 timeout 的相对关系检查。
- SQLite run store、SQLite queue、foundation schema、business tables enabled 同时满足时提示队列事件时间线完整。
- business tables 未启用时提示 watchdog 仍能标记超时，但工作台事件时间线不完整。

## 测试

- `tests/test_run_worker.py`
  - `run_once()` 在执行期间会周期写 heartbeat。
  - `run_watchdog_loop()` 会重复扫描。
- `tests/test_runtime_config_check.py`
  - sqlite-worker profile 检查 heartbeat interval。
  - interval 大于等于 timeout 时失败。
  - events 组合完整时输出 PASS。
  - business tables 未启用时输出 WARN。
- `tests/test_startup_templates.py`
  - SQLite worker 启动模板包含 watchdog 和 heartbeat 配置。

## 完成标准

- 长任务执行期间 heartbeat 会持续刷新。
- watchdog 可以用 loop 模式常驻扫描。
- 启动模板支持普通 worker 与 watchdog 两种模式。
- 配置检查能提示 heartbeat/watchdog/events 组合状态。
- 聚焦测试、编译检查和全量回归通过。
