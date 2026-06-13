# /performance 到 performance_records 反向同步设计

## 目标

本轮目标是收口表现数据闭环：当用户通过 `/performance` 人工录入表现数据后，系统不仅更新运营记忆，也要把同一份表现数据同步回 SQLite run state，并复用现有业务表同步能力写入 `performance_records`。

完成后，开发和复盘时可以从三处看到一致结果：

- `/memory/records` 中的运营记忆表现状态。
- `/runs/{run_id}` 中的 run summary/state 表现摘要。
- `/business/runs/{run_id}` 中的 `performance_records` 业务表快照。

## 范围

本轮只处理现有人工录入链路，不新增真实平台自动抓取指标，不新增调度器，不引入新存储技术。

包含：

- `/performance` 按 `post_id` 或 `creator_note_id` 找到运营记忆记录并更新表现。
- 在 SQLite run store + foundation schema + business tables enabled 时，找到关联的成功 run。
- 把更新后的表现数据、表现分、复盘摘要和下一步建议合并回 run state。
- 调用现有 `_save_run()`，让 `sync_run_business_tables()` 继续负责写入 `performance_records`。
- `/performance` 返回业务表同步状态摘要，便于 API 和工作台确认。
- 增加测试覆盖 JSON/local 模式不受影响、SQLite 模式自动同步、未找到关联 run 时不影响运营记忆更新。

不包含：

- 不自动从小红书平台抓取浏览、点赞、收藏、评论、关注数据。
- 不新增 business table schema。
- 不修改表现分计算规则。
- 不做历史数据批量迁移。
- 不改变现有 `/performance` 请求字段。

## 现状

当前 `/performance` 调用 `memory.operation_store.update_record_performance()`，可以按 `post_id` 或 `creator_note_id` 更新运营记忆。

`performance_records` 当前只在 success run 保存时由 `app.business_store.sync_run_business_tables()` 从 run state 写入。因此，人工录入表现后，如果 run 已经完成保存，业务表不会自动得到最新表现数据。

这会造成三份数据不一致：

- operation memory 已经是 `performance_recorded`。
- run state 仍保留录入前的空表现或旧表现。
- `performance_records` 缺失或仍是旧快照。

## 设计方案

### API 协调

`app.api.record_performance()` 在更新运营记忆后，新增一个 SQLite-only 同步步骤。

同步步骤只在以下条件全部满足时执行：

- `XHS_AGENT_RUN_STORE=sqlite`
- `XHS_AGENT_DB_SCHEMA=foundation`
- `XHS_AGENT_BUSINESS_TABLES_ENABLED=true`
- 当前 run store 是 `SQLiteRunStore`

不满足条件时，保持现有行为，只返回运营记忆更新结果，并在响应中标记业务同步为 `skipped`。

### 关联 run 查找

新增内部函数按以下优先级查找关联 run：

1. `operation_record_id` 匹配 run state 中的 `operation_record_id`。
2. `creator_note_id` 匹配 run state 或 summary 中的 `creator_note_id`。
3. `post_id` 匹配 run paths、summary 或 state 中的 `post_id`。

只选择 `status=success` 的 run。若存在多条候选，选择 `updated_at` 最新的一条。

### run state 合并

找到关联 run 后，从更新后的运营记忆记录中提取：

- `performance_data`
- `performance_score`
- `review_summary`
- `next_action`
- `review_generation`
- `creator_note_id`
- `published_url`
- `operator_notes`

将这些字段合并进 run state，并同步更新 summary/content/insights/paths 的现有结构。保存时调用 `_save_run()`，让现有业务表同步入口负责刷新 `performance_records`。

### 响应结果

`/performance` 保持原有字段：

- `memory_path`
- `updated_record`

新增字段：

- `business_sync.status`: `success`、`skipped` 或 `failed`
- `business_sync.run_id`: 成功同步时的 run id
- `business_sync.counts`: 成功同步后 summary 中的 `business_table_sync_counts`
- `business_sync.reason`: 跳过或失败原因

失败不阻断运营记忆更新。同步失败会返回 `failed`，错误信息需要脱敏。

## 错误处理

- 找不到运营记忆记录：继续沿用当前 `ValueError`。
- 找不到关联 success run：运营记忆更新成功，业务同步返回 `skipped`。
- SQLite/business table 配置未启用：运营记忆更新成功，业务同步返回 `skipped`。
- business table 写入失败：运营记忆更新成功，业务同步返回 `failed`，并复用现有错误脱敏逻辑。

## 测试策略

新增或扩展 API 级测试：

- JSON run store 下 `/performance` 行为保持兼容，业务同步为 `skipped`。
- SQLite run store 下，按 `creator_note_id` 录入表现后，关联 success run 的 state 和 summary 被更新。
- SQLite run store 下，`/business/runs/{run_id}` 返回 `performance_records`，数值与录入 payload 一致。
- 未找到关联 run 时，operation memory 仍更新成功，业务同步为 `skipped`。
- business sync 异常时错误脱敏，不泄露 cookie/token。

验证命令：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_note_performance_sync.py tests/test_api_business_table_sync.py tests/test_business_store.py -q
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_sqlite_stack.py
D:\Anaconda\envs\ContentShare\python.exe -m compileall app scripts tests
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

## 成功标准

- 人工表现录入后，运营记忆、run state 和 `performance_records` 可保持一致。
- 非 SQLite 或业务表未启用时，现有用户流程不受影响。
- 同步失败不破坏 `/performance` 的主功能。
- 全量测试和 SQLite stack smoke 通过。
