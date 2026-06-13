# worker 心跳与 watchdog 自动超时扫描实施计划

> 给后续执行者：按任务勾选推进。每个生产代码变更前先写失败测试，确认失败原因后再实现。

## 目标

在现有 SQLite queue 基础上增加 worker 心跳和 watchdog 自动超时扫描，让长时间 running 且心跳过期的任务可以被自动标记为 `timed_out`，并进入现有 `run_events` 时间线。

## 架构

本轮继续使用 `SQLiteRunQueue` 作为队列状态机，不引入新队列技术。`run_queue_jobs` 增加 `heartbeat_at` 字段；worker 领取任务后写心跳；watchdog 通过显式脚本入口扫描过期 running job，并复用现有 `mark_timed_out()`。

## 技术栈

Python 标准库、SQLite、现有 `app.run_queue`、`scripts.run_worker`、`scripts.check_runtime_config` 和 pytest。

---

### 任务 1：SQLite queue 心跳字段与接口

涉及文件：

- 修改：`实施/xhs-agent/tests/test_sqlite_run_queue.py`
- 修改：`实施/xhs-agent/app/run_queue.py`

步骤：

- [ ] 写失败测试：claim 后 job 明细包含 `heartbeat_at`，且值不为空。

```python
def test_sqlite_queue_claim_sets_initial_heartbeat(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued"}),
    )
    queue.enqueue("run_1")

    assert queue.claim_next("worker-a") == "run_1"

    status = queue.status()
    assert status["jobs"][0]["heartbeat_at"]
```

- [ ] 运行失败测试。

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_sqlite_run_queue.py::test_sqlite_queue_claim_sets_initial_heartbeat -q
```

预期：失败，原因是 `jobs` 明细没有 `heartbeat_at`。

- [ ] 实现最小代码：`run_queue_jobs` 增加 `heartbeat_at` 字段，`claim_next()` 写入，`status()` 返回。

- [ ] 运行同一个测试，预期通过。

### 任务 2：heartbeat 方法与事件

涉及文件：

- 修改：`实施/xhs-agent/tests/test_sqlite_run_queue.py`
- 修改：`实施/xhs-agent/app/run_queue.py`

步骤：

- [ ] 写失败测试：匹配 worker 的 running job 可以更新 heartbeat，并记录 `queue_heartbeat`。

```python
def test_sqlite_queue_heartbeat_updates_running_job_and_records_event(tmp_path: Path) -> None:
    db_path = tmp_path / "queue.sqlite3"
    queue = SQLiteRunQueue(
        db_path=db_path,
        list_runs=sample_runs({"run_1": "queued"}),
        event_db_path=db_path,
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    changed = queue.heartbeat("run_1", "worker-a")

    assert changed is True
    status = queue.status()
    assert status["jobs"][0]["heartbeat_at"]
    event_types = [row["event_type"] for row in _event_rows(db_path, "run_1")]
    assert "queue_heartbeat" in event_types
```

- [ ] 写失败测试：worker 不匹配时不更新。

```python
def test_sqlite_queue_heartbeat_rejects_different_worker(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued"}),
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    changed = queue.heartbeat("run_1", "worker-b")

    assert changed is False
```

- [ ] 运行失败测试。

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_sqlite_run_queue.py::test_sqlite_queue_heartbeat_updates_running_job_and_records_event tests/test_sqlite_run_queue.py::test_sqlite_queue_heartbeat_rejects_different_worker -q
```

预期：失败，原因是 `SQLiteRunQueue.heartbeat` 不存在。

- [ ] 实现 `heartbeat()`。

- [ ] 运行同一组测试，预期通过。

### 任务 3：watchdog 扫描队列过期任务

涉及文件：

- 修改：`实施/xhs-agent/tests/test_sqlite_run_queue.py`
- 修改：`实施/xhs-agent/app/run_queue.py`

步骤：

- [ ] 写失败测试：心跳过期的 running job 被标记为 `timed_out`。

```python
def test_sqlite_queue_watchdog_marks_expired_heartbeat_timed_out(tmp_path: Path) -> None:
    db_path = tmp_path / "queue.sqlite3"
    queue = SQLiteRunQueue(
        db_path=db_path,
        list_runs=sample_runs({"run_1": "running"}),
        event_db_path=db_path,
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"
    old_time = (datetime.now() - timedelta(seconds=120)).isoformat(timespec="seconds")
    with queue._connect() as connection:
        connection.execute(
            "UPDATE run_queue_jobs SET heartbeat_at = ? WHERE run_id = ?",
            (old_time, "run_1"),
        )

    timed_out = queue.mark_stale_running_as_timed_out(
        max_seconds=60,
        worker_id="watchdog",
        reason="watchdog heartbeat timeout",
    )

    assert timed_out == ["run_1"]
    status = queue.status()
    assert status["timed_out_run_ids"] == ["run_1"]
```

- [ ] 写失败测试：心跳未过期的 running job 不处理。

```python
def test_sqlite_queue_watchdog_keeps_fresh_heartbeat_running(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "running"}),
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    timed_out = queue.mark_stale_running_as_timed_out(max_seconds=60, worker_id="watchdog")

    assert timed_out == []
    assert queue.status()["running_run_ids"] == ["run_1"]
```

- [ ] 运行失败测试。

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_sqlite_run_queue.py::test_sqlite_queue_watchdog_marks_expired_heartbeat_timed_out tests/test_sqlite_run_queue.py::test_sqlite_queue_watchdog_keeps_fresh_heartbeat_running -q
```

预期：失败，原因是 watchdog 方法不存在。

- [ ] 实现 `mark_stale_running_as_timed_out()`。

- [ ] 运行同一组测试，预期通过。

### 任务 4：worker 脚本接入心跳和 watchdog 入口

涉及文件：

- 修改：`实施/xhs-agent/tests/test_run_worker.py`
- 修改：`实施/xhs-agent/scripts/run_worker.py`

步骤：

- [ ] 写失败测试：`run_once()` 领取任务后调用 `queue.heartbeat()`。

```python
class HeartbeatQueue(FakeQueue):
    def __init__(self) -> None:
        super().__init__(["run_1"])
        self.heartbeats: list[tuple[str, str]] = []

    def heartbeat(self, run_id: str, worker_id: str) -> bool:
        self.heartbeats.append((run_id, worker_id))
        return True


def test_run_once_records_heartbeat_after_claim() -> None:
    queue = HeartbeatQueue()
    records = {"run_1": {"status": "success"}}

    did_work = run_once(
        queue=queue,
        worker_id="worker-a",
        execute_run=lambda run_id: None,
        load_run=lambda run_id: records[run_id],
    )

    assert did_work is True
    assert queue.heartbeats == [("run_1", "worker-a")]
```

- [ ] 写失败测试：`run_watchdog_once()` 返回超时 run 列表。

```python
def test_run_watchdog_once_marks_stale_jobs() -> None:
    class WatchdogQueue(FakeQueue):
        def mark_stale_running_as_timed_out(self, **kwargs):
            self.watchdog_kwargs = kwargs
            return ["run_1"]

    queue = WatchdogQueue([])

    timed_out = run_watchdog_once(queue, max_seconds=60, worker_id="watchdog")

    assert timed_out == ["run_1"]
    assert queue.watchdog_kwargs["max_seconds"] == 60
```

- [ ] 运行失败测试。

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_run_worker.py::test_run_once_records_heartbeat_after_claim tests/test_run_worker.py::test_run_watchdog_once_marks_stale_jobs -q
```

预期：失败，原因是 `run_once()` 没有调用 heartbeat，`run_watchdog_once()` 不存在。

- [ ] 实现 worker 脚本改动。

- [ ] 运行同一组测试，预期通过。

### 任务 5：配置与运行检查

涉及文件：

- 修改：`实施/xhs-agent/app/config.py`
- 修改：`实施/xhs-agent/.env.example`
- 修改：`实施/xhs-agent/scripts/check_runtime_config.py`
- 修改：`实施/xhs-agent/tests/test_runtime_config_check.py`

步骤：

- [ ] 写失败测试：sqlite-worker profile 输出 heartbeat timeout 检查。

```python
def test_sqlite_worker_profile_checks_heartbeat_timeout(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_QUEUE_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_QUEUE_HEARTBEAT_TIMEOUT_SECONDS", "1800")

    results = check_profile("sqlite-worker")

    assert any("queue heartbeat timeout seconds: 1800" in result.message for result in results)
```

- [ ] 运行失败测试。

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_runtime_config_check.py::test_sqlite_worker_profile_checks_heartbeat_timeout -q
```

预期：失败，原因是配置字段未读取或检查未输出。

- [ ] 实现配置读取和检查输出，补 `.env.example`。

- [ ] 运行同一测试，预期通过。

### 任务 6：文档、验证与提交

涉及文件：

- 修改：`实施/xhs-agent/memory/current_progress.md`
- 修改：`实施/xhs-agent/memory/project_status_and_roadmap.md`

步骤：

- [ ] 更新进度文档，记录本轮完成内容、验证结果、限制和下一步。
- [ ] 运行聚焦测试。

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_sqlite_run_queue.py tests/test_run_worker.py tests/test_runtime_config_check.py -q
```

- [ ] 运行编译检查。

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app scripts tests
```

- [ ] 运行全量回归。

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

- [ ] 检查工作区状态和敏感文件。

```powershell
git status --short
```

- [ ] 暂存并提交。

```powershell
git add -A
git commit -m "feat: add sqlite worker watchdog"
```
