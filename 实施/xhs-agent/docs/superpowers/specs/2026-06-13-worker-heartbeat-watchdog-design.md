# worker 心跳与 watchdog 自动超时扫描设计

## 目标

本轮继续队列/worker 工程化主线，在现有 SQLite queue、`run_events` 和工作台时间线基础上，补齐“worker 是否仍然存活”的可观测信号，并提供一个显式 watchdog 扫描入口，自动把长时间 running 且心跳过期的任务标记为 `timed_out`。

本轮不引入 Redis、RQ、Celery 或新的后台调度技术；不强杀正在运行的 Python 线程；不撤销已经发出的真实 creator 平台请求。

## 当前上下文

已有能力：

- `SQLiteRunQueue` 使用 `run_queue_jobs` 保存 queued/running/failed/cancelled/timed_out 等状态。
- running job 已有 `locked_at`、`locked_by`，并支持 stale reclaim。
- 已有手动 `cancel()` 和 `mark_timed_out()`。
- 队列事件已经通过 `queue_events.py` 写入 `run_events`。
- 工作台可以展示 run lifecycle、queue events 和 graph node events。

缺口：

- worker 领取任务后没有持续心跳；长任务是否仍在执行，只能看首次 `locked_at`。
- 超时需要人工点击“标记超时”，没有显式 watchdog 入口。
- 运行配置检查还不能提示 heartbeat/watchdog 是否配置完整。

## 方案比较

推荐方案：在现有 `run_queue_jobs` 表上补 `heartbeat_at` 字段，并新增 `SQLiteRunQueue.heartbeat()` 与 `mark_stale_running_as_timed_out()`。worker 在执行任务前写一次心跳，并提供可测试的 watchdog 扫描方法；脚本层先提供 `scripts/run_worker.py --watchdog-once`，后续再接常驻 watchdog。

优点：贴合现有 SQLite 队列和事件模型；不引入新进程技术；测试范围可控；能立即服务当前工作台诊断。缺点：默认 worker 仍是同步执行，一次 `execute_run()` 期间无法自动周期心跳，除非后续把工作流拆成可中断执行或单独心跳线程。

备选方案一：只复用 `locked_at` 做超时扫描，不新增 `heartbeat_at`。优点是改动最小；缺点是无法区分“长任务仍在运行”和“worker 已死”，误判风险高。

备选方案二：引入独立 watchdog 常驻进程和 worker 心跳线程。优点是更接近生产形态；缺点是本轮改动面过大，会提前进入进程编排和线程退出治理。

本轮采用推荐方案，并把周期心跳线程留作后续增强。

## 设计

### 数据模型

`run_queue_jobs` 增加字段：

- `heartbeat_at TEXT`：worker 最近一次确认该 job 仍在处理的时间。

兼容旧库：`SQLiteRunQueue._init_db()` 检测字段，不存在时执行 `ALTER TABLE`。`status()` 的 job 明细返回 `heartbeat_at`，便于 API 和工作台后续展示。

### 队列接口

新增方法：

- `heartbeat(run_id, worker_id) -> bool`
  - 只更新 status 为 `running` 的 job。
  - worker 不匹配时不更新，避免旧 worker 覆盖新 worker。
  - 更新 `heartbeat_at` 和 `updated_at`。
  - 记录 `queue_heartbeat` 事件。

- `mark_stale_running_as_timed_out(max_seconds, worker_id="watchdog", reason=None, limit=100) -> list[str]`
  - 查找 `status='running'` 的 job。
  - 优先用 `heartbeat_at` 判断过期；没有心跳的历史 running job 回退到 `locked_at`。
  - 对过期 job 调用现有 `mark_timed_out()`，复用 run_events 事件写入。
  - 返回被标记超时的 run_id 列表。

### worker 脚本

`scripts/run_worker.py` 增加：

- `run_watchdog_once(queue, max_seconds, worker_id, reason=None) -> list[str]`
- CLI 参数 `--watchdog-once`

本轮不做后台线程常驻 watchdog。手动或计划任务可以先调用：

```powershell
D:\Anaconda\envs\ContentShare\python.exe .\scripts\run_worker.py --watchdog-once
```

### 配置

新增配置：

- `XHS_AGENT_QUEUE_HEARTBEAT_TIMEOUT_SECONDS=1800`

说明：

- `XHS_AGENT_QUEUE_LOCK_TIMEOUT_SECONDS` 继续服务 stale reclaim。
- `XHS_AGENT_QUEUE_HEARTBEAT_TIMEOUT_SECONDS` 服务 watchdog 自动标记超时。

### 运行配置检查

`scripts/check_runtime_config.py --profile sqlite-worker` 增加提示：

- heartbeat timeout 大于 0：PASS。
- SQLite queue 启用但 heartbeat timeout 小于等于 0：FAIL。
- business table events 未启用时，提示 watchdog 仍可改队列状态，但事件时间线不可完整呈现。

### 错误处理

- 心跳写入失败由 worker 日志暴露；不改变 run 主流程结果。
- watchdog 标记超时复用现有 `mark_timed_out()`，不会强杀线程，也不会撤销外部平台请求。
- worker 执行结束时已有 `_finish_run()` 保护：若 run 已经被标记为 `timed_out`，后续不会覆盖为 success/failed。

## 测试策略

新增或扩展测试：

- `tests/test_sqlite_run_queue.py`
  - claim job 时初始化 `heartbeat_at`。
  - `heartbeat()` 只更新匹配 worker 的 running job。
  - watchdog 能把心跳过期的 running job 标记为 timed_out。
  - watchdog 不处理心跳未过期的 running job。

- `tests/test_run_worker.py`
  - `run_once()` 在领取 job 后写 heartbeat。
  - `run_watchdog_once()` 返回被标记超时的 run_id。

- `tests/test_runtime_config_check.py`
  - sqlite-worker profile 会检查 heartbeat timeout。

验证命令：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_sqlite_run_queue.py tests/test_run_worker.py tests/test_runtime_config_check.py -q
D:\Anaconda\envs\ContentShare\python.exe -m compileall app scripts tests
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

## 完成标准

- SQLite running job 有可查询的 `heartbeat_at`。
- worker 领取任务后至少写一次 heartbeat。
- watchdog 显式扫描能自动把过期 running job 标记为 `timed_out`，并写入队列事件。
- 配置检查能提示 heartbeat/watchdog 配置状态。
- 聚焦测试、编译检查和全量测试通过。
