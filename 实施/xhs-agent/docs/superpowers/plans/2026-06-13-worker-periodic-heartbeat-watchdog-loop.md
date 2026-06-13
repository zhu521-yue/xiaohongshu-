# worker 周期心跳与 watchdog loop 实施计划

## 目标

把上一轮的一次性 worker heartbeat 升级为执行期间的周期 heartbeat，并提供 watchdog 常驻扫描入口和启动模板配置。

## 架构

继续复用 `SQLiteRunQueue` 和 `scripts/run_worker.py`。worker 线程本体仍同步执行任务，旁路 heartbeat daemon 线程只负责刷新 `heartbeat_at`；watchdog loop 只扫描并标记本地队列状态，不中断运行线程。

## 技术栈

Python 标准库、SQLite、PowerShell 启动模板、pytest。

---

### 任务 1：run_once 周期 heartbeat

- 修改测试：`tests/test_run_worker.py`
- 修改实现：`scripts/run_worker.py`

步骤：

- [ ] 写失败测试：`run_once(..., heartbeat_interval_seconds=0.01)` 在任务执行期间至少写两次 heartbeat。
- [ ] 运行定点测试确认失败。
- [ ] 实现 heartbeat daemon 线程和停止逻辑。
- [ ] 运行定点测试确认通过。

### 任务 2：watchdog loop

- 修改测试：`tests/test_run_worker.py`
- 修改实现：`scripts/run_worker.py`

步骤：

- [ ] 写失败测试：`run_watchdog_loop(..., scan_limit=2)` 会调用 watchdog 两次。
- [ ] 运行定点测试确认失败。
- [ ] 实现 `run_watchdog_loop()` 和 CLI `--watchdog-loop`。
- [ ] 运行定点测试确认通过。

### 任务 3：配置读取与检查

- 修改测试：`tests/test_runtime_config_check.py`
- 修改实现：`app/config.py`
- 修改实现：`scripts/check_runtime_config.py`
- 修改模板：`.env.example`

步骤：

- [ ] 写失败测试：sqlite-worker profile 输出 heartbeat interval。
- [ ] 写失败测试：interval 大于等于 timeout 时 FAIL。
- [ ] 写失败测试：events 组合完整时输出 PASS，未启用 business tables 时输出 WARN。
- [ ] 实现配置读取和检查。
- [ ] 运行相关测试确认通过。

### 任务 4：启动模板

- 修改测试：`tests/test_startup_templates.py`
- 修改模板：`scripts/start_sqlite_worker.ps1`

步骤：

- [ ] 写失败测试：模板包含 `XHS_AGENT_QUEUE_HEARTBEAT_INTERVAL_SECONDS`、`XHS_AGENT_QUEUE_HEARTBEAT_TIMEOUT_SECONDS` 和 `--watchdog-loop`。
- [ ] 实现 PowerShell 参数和命令拼接。
- [ ] 运行相关测试确认通过。

### 任务 5：文档、验证与提交

- 修改：`memory/current_progress.md`
- 修改：`memory/project_status_and_roadmap.md`

验证命令：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_run_worker.py tests/test_runtime_config_check.py tests/test_startup_templates.py -q
D:\Anaconda\envs\ContentShare\python.exe -m compileall app scripts tests
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

提交：

```powershell
git add -A
git commit -m "feat: add worker heartbeat loop"
```
