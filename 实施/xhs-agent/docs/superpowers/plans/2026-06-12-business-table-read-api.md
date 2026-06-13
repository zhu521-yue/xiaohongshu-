# 业务表只读查询 API 实施计划

## 目标

在 foundation 业务表已经具备旁路写入能力后，新增最小只读查询入口，让使用者能按 `run_id` 直接查看 SQLite 业务表中已经同步出的结构化快照。

## 架构约定

- 新增 `app/business_queries.py`，只负责读取 SQLite foundation 业务表，不做写入、不做迁移、不触发采集/发布。
- `app/api.py` 增加 `GET /business/runs/{run_id}`，返回该 run 的业务表快照。
- 只有当前 run store 是 SQLite 时才允许查询；JSON run store 返回明确错误。
- 返回内容以验证同步为主：包含各表 counts 和每张表的紧凑列表。
- 本轮不做工作台前端展示，不把现有 run JSON 查询切换到业务表。

## 接口契约

`GET /business/runs/{run_id}` 返回：

- `ok`
- `business_run`
  - `run_id`
  - `db_path`
  - `counts`
  - `raw_notes`
  - `collection_candidates`
  - `raw_comments`
  - `analysis_reports`
  - `drafts`
  - `creator_assets`
  - `creator_notes`
  - `performance_records`
  - `audit_events`

## 任务步骤

1. 新增 `tests/test_business_queries.py`：
   - 创建 SQLite run store 和 foundation 业务表数据。
   - 调用 `get_business_run_snapshot(db_path, run_id)`。
   - 断言 counts、草稿、素材、平台笔记和审计事件可读。

2. 扩展 `tests/test_api_business_table_sync.py`：
   - 在 SQLite API 配置下保存成功 run 并自动同步。
   - 调用新的 API 层函数读取业务表快照。
   - 在 JSON run store 配置下断言返回明确错误。

3. 扩展 HTTP 路由测试：
   - 通过测试 HTTP server 请求 `/business/runs/{run_id}`。
   - 断言返回业务表快照。

4. 实现 `app/business_queries.py`：
   - 使用 `initialize_foundation_schema()` 保证表存在。
   - 按 `run_id` 查询 9 张业务表。
   - 将 JSON 字符串字段安全解析为 dict/list。
   - 每张表返回紧凑字段，不返回过大的 raw JSON 明细。

5. 修改 `app/api.py`：
   - 引入查询函数。
   - 新增 `get_business_run_snapshot(run_id)` API 层函数。
   - 在 `do_GET()` 中处理 `/business/runs/{run_id}`。

6. 验证：
   - 聚焦测试：`D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_business_queries.py tests/test_api_business_table_sync.py tests/test_api_platform_status.py -q`
   - 编译：`D:\Anaconda\envs\ContentShare\python.exe -m compileall app tests`
   - 全量：`D:\Anaconda\envs\ContentShare\python.exe -m pytest -q`

## 当前不做

- 不新增前端工作台面板。
- 不迁移历史数据。
- 不把现有 `/runs/{run_id}` 改为从业务表读取。
- 不做 GraphRAG 入库。
