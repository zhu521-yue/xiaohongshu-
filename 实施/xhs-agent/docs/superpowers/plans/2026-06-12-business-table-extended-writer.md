# 业务表剩余快照写入实施计划

## 目标

在现有 `sync_run_business_tables()` 已经写入 `raw_notes`、`collection_candidates`、`raw_comments`、`analysis_reports` 的基础上，继续把同一个 run record 中可确定的数据旁路写入 `drafts`、`creator_assets`、`creator_notes`、`performance_records`、`audit_events`。

## 架构约定

- 继续使用 `app/business_store.py` 作为唯一业务表快照写入入口。
- 不改变默认 JSON run 行为，不改变 API 响应结构，不改变发布、表现录入和运营记忆的现有流程。
- 写入逻辑保持幂等，使用稳定 hash 主键和 SQLite upsert。
- 所有 JSON 兜底字段继续复用现有脱敏逻辑，避免 Cookie、token、用户身份字段和敏感 URL 参数落库。

## 文件范围

- 修改 `app/business_store.py`：新增剩余业务表的 upsert 函数，并把返回 counts 扩展到 9 张业务表。
- 修改 `tests/test_business_store.py`：先补失败测试，覆盖剩余业务表写入、幂等和敏感字段脱敏。
- 修改 `tests/test_api_business_table_sync.py`：更新自动同步返回 counts 的契约。
- 修改 `memory/current_progress.md` 和 `memory/project_status_and_roadmap.md`：任务完成后记录最新进度和遗留限制。

## 任务步骤

1. 在 `tests/test_business_store.py` 写失败测试：
   - 构造一个包含图文草稿、绑定图片文件、creator 发布结果、表现数据和人工审核状态的成功 run。
   - 调用 `sync_run_business_tables()`。
   - 断言 `drafts`、`creator_assets`、`creator_notes`、`performance_records`、`audit_events` 都有结构化行。
   - 断言重复同步不会重复插入。

2. 运行聚焦测试确认 RED：
   - 命令：`D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_business_store.py -q`
   - 预期：新增测试因剩余表未写入而失败。

3. 在 `app/business_store.py` 实现最小 GREEN：
   - `drafts` 从 run `state` 和 `content` 读取标题、正文、标签、图文页规划、视频脚本和 `post_id`。
   - `creator_assets` 从 `state.creator_image_files` 读取文件路径、文件名、大小、扩展名推断的 mime、绑定顺序和对应图片 prompt。
   - `creator_notes` 从 `state.creator_note_id`、`creator_publish_status`、`creator_publish_mode`、`creator_publish_result` 写入。
   - `performance_records` 从 `state.performance_data` 写入；如果没有表现数据则不写。
   - `audit_events` 写入人工审核、creator 发布和运营记忆写入三类可追踪事件。

4. 运行聚焦测试确认 GREEN：
   - 命令：`D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_business_store.py tests/test_api_business_table_sync.py -q`
   - 预期：业务表写入和 API 自动同步测试通过。

5. 运行验证：
   - 编译检查：`D:\Anaconda\envs\ContentShare\python.exe -m compileall app tests`
   - 全量回归：`D:\Anaconda\envs\ContentShare\python.exe -m pytest -q`
   - 预期：所有检查通过；如果失败，先修复本轮引入的问题，再更新进度文件。

## 当前不做

- 不新增工作台只读查询入口。
- 不迁移历史运营记忆到 `performance_records`。
- 不把分析查询从 run JSON 切换到业务表。
- 不接入 GraphRAG。
