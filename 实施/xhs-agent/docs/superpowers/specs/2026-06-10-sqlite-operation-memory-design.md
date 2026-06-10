# SQLite Operation Memory Design

## 背景

当前运营记忆由 `memory/operation_store.py` 直接读写 `memory/operation_history.json`。这套 JSON 记忆已经支撑 MVP：保存草稿记录、录入表现数据、生成复盘、检索同主题历史记录、提取 `successful_patterns`，并且已经包含跨领域健康污染过滤。

第一阶段已经完成 run 存储的 SQLite 可切换后端。第二阶段目标是把运营记忆也推进到 SQLite 可切换后端，但不同时做队列、API/worker 拆分或历史数据迁移。

## 目标

- 新增 SQLite 版运营记忆存储。
- 保留现有 JSON 运营记忆作为默认行为。
- 对外函数 API 保持不变：
  - `load_history()`
  - `save_history()`
  - `upsert_record_from_state()`
  - `find_relevant_records()`
  - `find_successful_patterns()`
  - `update_record_performance()`
- 让 `nodes/memory_node.py`、`app/api.py`、`scripts/record_performance.py` 尽量不改调用方式。
- 用 `pytest` 覆盖 SQLite 后端的新增记录、更新记录、历史检索、成功模式提取、表现录入。

## 非目标

- 不自动迁移 `memory/operation_history.json` 里的历史记录。
- 不拆分 operation memory 的多张业务表。
- 不引入 ORM。
- 不引入 PostgreSQL、pgvector、GraphRAG 或 embedding。
- 不改变内容生成、评论洞察、复盘生成、合规逻辑。
- 不改变 `/memory/records` 和 `/performance` 的响应结构。

## 推荐方案

在 `memory/operation_store.py` 内部抽出轻量存储后端：

```python
class JsonOperationMemoryBackend:
    load_history() -> dict[str, Any]
    save_history(history: dict[str, Any]) -> Path

class SQLiteOperationMemoryBackend:
    load_history() -> dict[str, Any]
    save_history(history: dict[str, Any]) -> Path
```

现有模块级函数继续存在，并通过 `_memory_backend()` 委托到当前后端。业务算法仍保留在 `operation_store.py`：

- `record_from_state()`
- `_topic_relevance()`
- `_record_has_cross_domain_health_pollution()`
- `successful_patterns_from_records()`
- `build_review_result()`

这样调用方不用理解后端差异，第二阶段也不会把存储改造扩大成业务重构。

## 配置

新增环境变量：

```env
XHS_AGENT_MEMORY_STORE=json
XHS_AGENT_MEMORY_DB_PATH=data/xhs_agent.sqlite3
```

规则：

- `json` 或缺省：继续使用 `memory/operation_history.json`。
- `sqlite`：使用 SQLite 的 `operation_records` 表。
- SQLite 默认 DB 路径与 run store 一致，方便本地部署只有一个数据库文件。

`operation_memory_path` 在 SQLite 后端下返回 DB 文件路径，便于前端和脚本继续展示“记忆位置”。

## 数据模型

SQLite 表：

```sql
CREATE TABLE IF NOT EXISTS operation_records (
  record_id TEXT PRIMARY KEY,
  post_id TEXT UNIQUE,
  topic TEXT NOT NULL,
  target_user TEXT,
  content_type TEXT,
  content_format TEXT,
  status TEXT,
  publish_status TEXT,
  performance_score INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  record_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_operation_records_topic ON operation_records(topic);
CREATE INDEX IF NOT EXISTS idx_operation_records_updated_at ON operation_records(updated_at);
CREATE INDEX IF NOT EXISTS idx_operation_records_performance_score ON operation_records(performance_score);
```

`record_json` 保存完整记录，避免第一阶段过早拆分痛点、评论洞察、表现数据和复盘结果。索引字段用于后续列表、迁移和查询优化。

## 行为细节

### load_history()

JSON 后端保持当前行为。

SQLite 后端返回同样结构：

```python
{
    "version": 1,
    "updated_at": latest_updated_at_or_none,
    "records": [record, ...],
}
```

records 按 `created_at ASC` 返回，保持 JSON 历史“追加顺序”的语义。

### save_history()

JSON 后端继续原子写入整个 history。

SQLite 后端把 `history["records"]` 中的每条 dict upsert 到 `operation_records`。这主要用于兼容 `scripts/repair_operation_memory.py` 这类仍按整份 history 修改后保存的脚本。

### upsert_record_from_state()

现有逻辑仍负责把 state 压缩成 operation record。SQLite 后端通过 `post_id` 或 `record_id` upsert。

如果 `post_id` 存在，优先按 `post_id` 找旧记录并保留旧 `created_at`。这保持当前 JSON 行为。

### update_record_performance()

继续按 `post_id` 查找记录，更新：

- `performance_data`
- `performance_score`
- `status`
- `updated_at`
- `published_url`
- `operator_notes`
- `review_summary`
- `next_action`
- `review_generation`

SQLite 后端写回同一条 `record_json`。

### find_relevant_records() / find_successful_patterns()

先从当前后端读取 records，再复用现有 Python 过滤和评分逻辑。跨领域健康污染过滤不改。

## 文件职责

- `memory/operation_store.py`
  - 新增 JSON/SQLite 后端类。
  - 新增 `_memory_backend()` 和 `operation_memory_path()`。
  - 保持现有公开函数名。
  - 保留现有业务算法。

- `app/config.py`
  - `Settings` 增加 `memory_store_backend` 和 `memory_db_path`。

- `nodes/memory_node.py`
  - 使用 `operation_memory_path()` 替代直接展示 `HISTORY_PATH`。

- `app/api.py`
  - 使用 `operation_memory_path()` 替代直接展示 `HISTORY_PATH`。

- `scripts/record_performance.py`
  - 使用 `operation_memory_path()` 替代直接展示 `HISTORY_PATH`。

- `.env.example`
  - 记录 `XHS_AGENT_MEMORY_STORE` 和 `XHS_AGENT_MEMORY_DB_PATH`。

- `tests/test_operation_store.py`
  - 覆盖 SQLite 后端和 JSON 后端的核心行为。

## 测试策略

使用 `pytest`。

覆盖行为：

- SQLite 后端保存一条 state 后能读出 operation record。
- 同一 `post_id` 再次 upsert 会更新旧记录而不是追加重复记录。
- SQLite 后端 `find_relevant_records()` 能按主题返回相关记录。
- SQLite 后端 `find_successful_patterns()` 只返回有表现数据的高分记录。
- SQLite 后端 `update_record_performance()` 能更新表现数据、表现分和复盘字段。
- 非健康主题在 SQLite 后端仍会跳过健康污染记录。
- JSON 后端的基础 load/save 行为仍可用。

验证命令：

```powershell
python -m pytest -q
python -m compileall app nodes routers platforms memory scripts llm
```

## 迁移策略

第二阶段不自动迁移历史 JSON。理由：

- 当前 JSON 历史包含真实测试记录和修复痕迹，迁移需要单独校验。
- 直接迁移会把数据清洗和存储后端改造混在一起。
- 先验证 SQLite 后端对新增记录和表现录入可用。

后续可以单独新增：

```text
scripts/migrate_operation_history_to_sqlite.py
```

该脚本读取 `memory/operation_history.json`，调用 SQLite 后端保存。

## 风险与边界

- SQLite 后端仍是单机存储，不是最终多实例生产数据库。
- `record_json` 整体存储便于兼容，但不适合复杂分析查询；后续 PostgreSQL 阶段再拆表。
- `save_history()` 在 SQLite 后端会批量 upsert 当前 history records，不会删除 SQLite 中 history 不包含的旧记录，避免误删。
- `scripts/repair_operation_memory.py` 在 SQLite 后端下可保存修改后的记录，但第二阶段不专门优化它的交互体验。

## 完成标准

- 默认 `XHS_AGENT_MEMORY_STORE=json` 行为不变。
- `XHS_AGENT_MEMORY_STORE=sqlite` 时，生成后写入运营记忆、查询 `/memory/records`、录入 `/performance`、检索 successful patterns 都使用 SQLite。
- `python -m pytest -q` 通过。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- `.env.example` 记录新配置。
