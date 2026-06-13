# SQLite stack smoke 组合检查设计

## 目标

本轮目标是提高日常开发效率：新增一个一键 smoke 检查，验证 SQLite API、SQLite queue、worker、watchdog、business tables 和 run_events 是否能在 mock 模式下完整联通。

该检查用于开发前后快速确认工程底座可用，不访问真实小红书平台，不调用真实 LLM，不启动外部 HTTP 服务。

## 方案

新增 `scripts/check_sqlite_stack.py`，在当前 Python 进程内完成：

1. 临时设置运行环境：
   - `XHS_AGENT_RUN_STORE=sqlite`
   - `XHS_AGENT_RUN_QUEUE=sqlite`
   - `XHS_AGENT_MEMORY_STORE=sqlite`
   - `XHS_AGENT_DB_SCHEMA=foundation`
   - `XHS_AGENT_BUSINESS_TABLES_ENABLED=true`
   - `COLLECTOR_MODE=mock`
   - `LLM_MODEL_NAME=mock`
2. 调用 `api.submit_run()` 提交一条异步 run。
3. 调用 `run_worker.run_once()` 用 SQLite worker 处理任务。
4. 调用 `run_worker.run_watchdog_once()` 验证 watchdog 扫描入口。
5. 调用 `api.get_business_run_snapshot()` 检查业务表和事件时间线。
6. 输出 JSON 摘要，包括 run、queue、watchdog、business_run、event_types 和 checks。
7. 结束后恢复原环境变量并重置 API/operation memory 单例。

## 边界

- 不启动 `scripts/run_api.py`，避免端口占用和后台进程清理问题。
- 不启动常驻 worker/watchdog loop，只验证同一套函数入口。
- 不访问真实平台，不读取真实 Cookie。
- 默认使用项目 `data/` 下的唯一 SQLite DB 文件；`data/` 已被 Git 忽略，便于保留排查。传入 `--db-path` 时使用指定数据库。

## 使用

```powershell
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_sqlite_stack.py
```

如需指定数据库：

```powershell
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_sqlite_stack.py --db-path data/sqlite_stack_smoke.sqlite3
```

## 完成标准

- smoke run 最终 `status=success`。
- SQLite queue 被清空。
- watchdog 没有误标记超时。
- business snapshot 可读取。
- `run_events` 中包含 queue 和 lifecycle 事件。
- 脚本返回 exit code 0，并输出 `"ok": true`。
