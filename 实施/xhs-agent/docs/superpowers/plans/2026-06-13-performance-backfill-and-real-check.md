# 表现闭环真实检查与历史补偿实施计划

目标：新增两个开发效率工具，让真实表现闭环可重复检查，让历史已录入表现可补偿写回 SQLite run state 与 `performance_records`。

架构：真实检查脚本复用 creator 只读列表、SQLite run store、operation memory 和 `api.record_performance()`；历史补偿脚本复用当前配置的 operation memory 与 run store，并继续走现有 `/performance` 同步路径，避免新增旁路 SQL。

技术栈：Python 标准库、现有 `app.api`、`app.run_store`、`memory.operation_store`、`platforms.creator`、pytest。

---

## 文件结构

- 新增：`scripts/check_real_performance_closure.py`
  - 负责真实 creator 只读列表检查、临时 SQLite 环境、run 导入、表现录入和业务表快照校验。
- 新增：`scripts/backfill_performance_records.py`
  - 负责扫描 operation memory 中的历史表现记录，并按 dry-run/apply 模式复用 `api.record_performance()` 补偿。
- 新增：`tests/test_check_real_performance_closure.py`
  - 使用 fake creator 列表测试真实闭环脚本，不访问网络。
- 新增：`tests/test_backfill_performance_records.py`
  - 测试 dry-run、apply、skipped、幂等。
- 修改：`memory/current_progress.md`
  - 记录本轮完成内容、验证结果和限制。
- 修改：`memory/project_status_and_roadmap.md`
  - 更新当前主线进度。

---

## 任务一：真实闭环检查脚本

文件：
- 新增：`tests/test_check_real_performance_closure.py`
- 新增：`scripts/check_real_performance_closure.py`

步骤：

1. 写失败测试：构造临时 JSON run、fake `list_published_notes()`，调用 `run_real_performance_closure_check()`，断言输出 `ok=true`、平台笔记已找到、`business_sync.status=success`、`performance_records=1`。

2. 运行红灯测试：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_check_real_performance_closure.py -q
```

预期：因为脚本文件不存在而失败。

3. 实现最小脚本：

- 提供 `_sqlite_closure_environment(db_path)`，临时设置：
  - `XHS_AGENT_RUN_STORE=sqlite`
  - `XHS_AGENT_RUN_DB_PATH=<db_path>`
  - `XHS_AGENT_MEMORY_STORE=sqlite`
  - `XHS_AGENT_MEMORY_DB_PATH=<db_path>`
  - `XHS_AGENT_DB_SCHEMA=foundation`
  - `XHS_AGENT_BUSINESS_TABLES_ENABLED=true`
  - `CREATOR_MODE=spider_xhs`
- 提供 `run_real_performance_closure_check(...)`。
- 读取并保存指定 run。
- 调用 `operation_store.upsert_record_from_state(state)`。
- 调用 `api.record_performance(payload)`。
- 查询 `api.get_business_run_snapshot(run_id)`。
- 输出 checks 和 JSON 结果。

4. 运行绿灯测试：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_check_real_performance_closure.py -q
```

预期：测试通过。

---

## 任务二：历史表现补偿脚本

文件：
- 新增：`tests/test_backfill_performance_records.py`
- 新增：`scripts/backfill_performance_records.py`

步骤：

1. 写失败测试：在临时 SQLite 环境中创建 success run 和已录入表现的 operation memory 记录，调用 `backfill_performance_records(dry_run=True)`，断言返回候选但 `performance_records` 表不存在或行数为 0。

2. 运行红灯测试：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_backfill_performance_records.py -q
```

预期：因为脚本文件不存在而失败。

3. 实现 dry-run：

- 提供 `backfill_performance_records(...)`。
- 加载 operation memory history。
- 过滤 `status=performance_recorded` 且 `performance_data` 非空的记录。
- 支持 `record_id`、`creator_note_id`、`post_id`、`limit` 过滤。
- dry-run 只返回 `processed` 候选，不调用 `api.record_performance()`。

4. 写 apply 测试：调用 `backfill_performance_records(dry_run=False)`，断言 run state 更新，`performance_records` 行数为 1。

5. 实现 apply：

- 构造 payload：
  - `post_id`
  - `creator_note_id`
  - `views`
  - `likes`
  - `collects`
  - `comments`
  - `follows`
  - `published_url`
  - `notes`
- 调用 `api.record_performance(payload)`。
- `business_sync.status=success` 进入 processed。
- `business_sync.status=skipped` 进入 skipped，并保留 reason。

6. 写 skipped 与幂等测试：

- 没有匹配 success run 时进入 skipped。
- 连续执行两次 apply 后，`performance_records` 仍只有一行。

7. 运行绿灯测试：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_backfill_performance_records.py -q
```

预期：测试通过。

---

## 任务三：命令行入口与组合验证

文件：
- 修改：`scripts/check_real_performance_closure.py`
- 修改：`scripts/backfill_performance_records.py`
- 修改：`tests/test_check_real_performance_closure.py`
- 修改：`tests/test_backfill_performance_records.py`

步骤：

1. 给真实检查脚本增加 argparse：

- `--run-id`
- `--creator-note-id`
- `--db-path`
- `--limit`
- `--use-platform-metrics`
- `--views`
- `--likes`
- `--collects`
- `--comments`
- `--follows`

2. 给补偿脚本增加 argparse：

- `--apply`
- `--dry-run`
- `--record-id`
- `--creator-note-id`
- `--post-id`
- `--limit`

3. 增加 CLI 测试：用 `main([...])` 验证输出 JSON 和退出码。

4. 运行脚本定点测试：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_check_real_performance_closure.py tests/test_backfill_performance_records.py -q
```

预期：全部通过。

---

## 任务四：文档记忆、验证和提交

文件：
- 修改：`memory/current_progress.md`
- 修改：`memory/project_status_and_roadmap.md`

步骤：

1. 更新项目记忆，记录：

- 新增真实闭环检查脚本。
- 新增历史表现补偿脚本。
- 默认 dry-run 和只读平台边界。
- 本轮验证命令与结果。
- 后续仍未完成的平台真实自动指标抓取、公开发布、GraphRAG、阶段二软广/达人任务。

2. 运行定点测试：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_check_real_performance_closure.py tests/test_backfill_performance_records.py -q
```

3. 运行相关回归：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_note_performance_sync.py tests/test_api_business_table_sync.py tests/test_business_store.py tests/test_sync_run_to_business_tables_script.py -q
```

4. 运行 SQLite stack smoke：

```powershell
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_sqlite_stack.py
```

5. 运行编译检查：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app scripts tests
```

6. 运行全量测试：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

7. 检查工作区：

```powershell
git status --short
git diff --check
git diff --stat
```

8. 提交实现：

```powershell
git add 实施/xhs-agent/scripts/check_real_performance_closure.py 实施/xhs-agent/scripts/backfill_performance_records.py 实施/xhs-agent/tests/test_check_real_performance_closure.py 实施/xhs-agent/tests/test_backfill_performance_records.py 实施/xhs-agent/memory/current_progress.md 实施/xhs-agent/memory/project_status_and_roadmap.md
git commit -m "feat: add performance closure maintenance tools"
```

---

## 自检

- 设计覆盖：真实只读检查、历史补偿、dry-run、幂等、测试和验证均有任务对应。
- 范围控制：不新增真实发布，不改 schema，不新增后台调度。
- 类型一致：两个脚本都输出 `processed`、`skipped`、`errors` 或 `checks` 这类结构化 JSON，便于后续自动化读取。
