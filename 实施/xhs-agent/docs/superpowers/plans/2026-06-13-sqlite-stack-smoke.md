# SQLite stack smoke 组合检查实施计划

## 目标

新增 `scripts/check_sqlite_stack.py`，用一条命令验证 SQLite API、worker、watchdog、business tables 和 run_events 的组合状态。

## 架构

脚本不启动外部 HTTP 服务，直接复用现有 `app.api`、`scripts.run_worker` 和业务表查询入口。它在进程内临时切换为 mock + SQLite 环境，执行一条异步 run，再恢复原环境。

## 技术栈

Python 标准库、现有 API/worker 模块、pytest。

---

### 任务 1：写 RED 测试

- 新增 `tests/test_check_sqlite_stack.py`
- 覆盖：
  - mock run 能提交、worker 处理成功、watchdog 扫描、business snapshot 可读。
  - 脚本恢复原环境变量。
  - CLI `main()` 输出 JSON 摘要并返回 0。

### 任务 2：实现脚本

- 新增 `scripts/check_sqlite_stack.py`
- 实现：
  - `_sqlite_smoke_environment()`
  - `run_sqlite_stack_smoke()`
  - `build_parser()`
  - `main()`

### 任务 3：验证

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_check_sqlite_stack.py -q
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_sqlite_stack.py
D:\Anaconda\envs\ContentShare\python.exe -m compileall app scripts tests
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

### 任务 4：更新进度并提交

- 更新 `memory/current_progress.md`
- 更新 `memory/project_status_and_roadmap.md`
- 提交：

```powershell
git add -A
git commit -m "feat: add sqlite stack smoke check"
```
