# SQLite RunStore Design

## 背景

当前项目已经把 API 层的 run 存储边界抽到 `app/run_store.py`，但实际实现仍是 `LocalRunStore`，每个 run 落成一个 `data/api_runs/*.json` 文件。这适合 MVP 和本地调试，但不适合后续 API/worker 拆分、多 worker 执行、审计查询和生产部署。

第一阶段目标只替换 run 存储边界，不同时迁移运营记忆、不引入外部队列、不拆 API/worker 进程。这样可以先验证数据库读写模型，再继续推进队列和进程拆分。

## 目标

- 新增 SQLite 兼容的 run 存储实现。
- 保留现有 JSON 存储作为回退和默认行为。
- 让 API 层通过环境变量选择 `json` 或 `sqlite` 后端。
- 用 `pytest` 建立最小测试基础，覆盖新存储行为。
- 不改变 HTTP API 响应结构、前端轮询、人审通过/驳回行为。

## 非目标

- 不迁移 `memory/operation_history.json`。
- 不引入 Redis、RQ、Celery 或 PostgreSQL 客户端。
- 不做旧 `data/api_runs/*.json` 的自动迁移。
- 不改变 LangGraph 节点、内容生成、合规、采集或 LLM 行为。
- 不把 SQLite 设为默认后端；第一阶段默认仍使用 `json`，由环境变量显式开启。

## 推荐方案

新增 `SQLiteRunStore`，与 `LocalRunStore` 暴露同样的接口：

```python
save(record: dict[str, Any]) -> None
load(run_id: str) -> dict[str, Any] | None
list(limit: int = 20) -> list[dict[str, Any]]
run_path(run_id: str) -> Path
```

`run_path()` 在 SQLite 后端中仅用于兼容现有调用和展示，不代表实际存储文件；它可以返回 `data/api_runs/{run_id}.json` 的逻辑路径，避免 API 层现有辅助函数立即改动。

API 层新增后端选择：

```env
XHS_AGENT_RUN_STORE=json
XHS_AGENT_RUN_DB_PATH=data/xhs_agent.sqlite3
```

当 `XHS_AGENT_RUN_STORE=sqlite` 时，`app/api.py` 初始化 `SQLiteRunStore`；其他值或缺省时继续使用 `LocalRunStore`。

## 数据模型

SQLite 数据库默认路径：

```text
data/xhs_agent.sqlite3
```

新增表：

```sql
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  request_json TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  content_json TEXT NOT NULL,
  insights_json TEXT NOT NULL,
  state_json TEXT NOT NULL,
  paths_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
```

`save()` 使用 upsert。复杂字段继续以 JSON 文本保存，避免第一阶段设计过度拆表。`metadata_json` 用于保留未显式拆列的顶层字段，例如 `approved_at`、`reviewed_at`、`review_action`，确保 API 响应结构不因存储后端切换而丢字段。`load()` 负责把 JSON 字段还原为现有 run record 结构。`list()` 按 `created_at DESC` 返回最近记录。

## 文件职责

- `app/run_store.py`
  - 保留 `LocalRunStore`。
  - 新增 `SQLiteRunStore`。
  - 新增内部 JSON 编解码辅助函数。
  - 新增 SQLite 初始化和 upsert 逻辑。

- `app/config.py`
  - `Settings` 增加 `run_store_backend` 和 `run_db_path`。
  - `load_settings()` 读取 `XHS_AGENT_RUN_STORE` 和 `XHS_AGENT_RUN_DB_PATH`。

- `app/api.py`
  - `_run_store()` 根据配置选择 `LocalRunStore` 或 `SQLiteRunStore`。
  - 其他 API、队列、人审和前端响应逻辑保持不变。

- `.env.example`
  - 增加 run store 后端配置示例。

- `tests/test_run_store.py`
  - 用 `pytest` 覆盖 `SQLiteRunStore` 的保存、读取、更新、列表和缺失记录行为。

## 数据流

当前 API 数据流保持不变：

```text
POST /runs
-> submit_run()
-> _save_run(record)
-> selected RunStore.save(record)
-> worker 执行
-> _finish_run()
-> selected RunStore.save(record)
```

切换到 SQLite 后，只改变 `_save_run()`、`_load_run()`、`_list_runs()` 背后的存储实现。`LocalRunQueue` 仍通过 `_list_runs()` 恢复 queued/running 任务，因此新存储必须保持 `status` 和时间字段行为一致。

## 错误处理

- SQLite 父目录不存在时自动创建。
- 数据库表不存在时自动创建。
- `save()` 缺少 `run_id` 时继续抛 `ValueError("run record missing run_id")`。
- JSON 字段解析失败时，`load()` 返回结构化记录并把坏字段降级为 `{}`，避免单条坏数据拖垮列表接口。
- SQLite 异常不吞掉，由调用方暴露为失败，方便开发阶段发现问题。

## 测试策略

使用 `pytest`，不引入 ORM 或额外测试框架。

覆盖行为：

- 保存后能按 `run_id` 读取完整记录。
- 保存同一 `run_id` 会覆盖旧记录。
- `list(limit)` 按 `created_at` 倒序返回。
- 不存在的 run 返回 `None`。
- 复杂字段 `request`、`summary`、`content`、`insights`、`state`、`paths` 能 JSON 往返。
- `LocalRunStore` 现有基本行为不被破坏：保存后能读取，同一 `run_id` 保存会覆盖旧记录。

验证命令：

```powershell
python -m pytest
python -m compileall app nodes routers platforms memory scripts llm
```

## 迁移策略

第一阶段不自动迁移历史 JSON run 文件。理由：

- 当前 `data/api_runs/` 是运行数据，不属于代码主线。
- 自动迁移会引入数据清洗、重复 run、损坏 JSON 处理等额外问题。
- 新后端先验证新增 run 的读写和前端轮询即可。

后续如需要迁移，可单独新增脚本：

```text
scripts/migrate_api_runs_to_sqlite.py
```

该脚本读取 `data/api_runs/*.json`，调用 `SQLiteRunStore.save()` 写入数据库。

## 风险与边界

- SQLite 支持单机和低并发开发，不是最终高并发方案。
- 多进程写入 SQLite 可以工作，但会遇到写锁竞争；后续 PostgreSQL 仍是生产目标。
- 队列仍是本进程内 `LocalRunQueue`，服务重启和多 worker 能力不会因本阶段自动变成生产级。
- operation memory 仍在 JSON 文件中，表现录入和 successful patterns 暂不迁移。

## 完成标准

- `XHS_AGENT_RUN_STORE=json` 或缺省时，现有行为保持不变。
- `XHS_AGENT_RUN_STORE=sqlite` 时，提交 run、轮询 run、列出 runs、人审通过/驳回都通过同一 SQLite 数据库读写。
- `python -m pytest` 通过。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- `.env.example` 记录新配置。
