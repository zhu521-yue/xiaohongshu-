# 数据库基础表设计

## 目标

在已经具备 SQLite run store、SQLite run queue、SQLite operation memory 兼容后端的基础上，新增一层“基础业务表”设计，让采集、分析、草稿、素材、发布、表现和审计数据可以逐步从松散 JSON/run state 中沉淀到可查询、可迁移、可扩展的表结构。

本轮设计采用渐进式业务表 overlay：保留现有 `runs`、`run_queue_jobs`、`operation_records` 的兼容行为，同时新增围绕主链数据的结构化表。这样可以不打断当前 API、worker、运营记忆和工作台响应结构，又能为后续数据分析、GraphRAG、部署和审计打基础。

## 范围

本轮包含：
- 设计 SQLite first、PostgreSQL 兼容的基础业务表 schema。
- 明确现有兼容表和新增业务表之间的职责边界。
- 明确每张表的主键、关键字段、JSON 保底字段、索引和唯一约束。
- 明确 run 执行过程中的写入时机和数据流。
- 明确初版迁移边界和测试验收口径。

本轮不包含：
- 不立刻替换现有 `LocalRunStore`、`SQLiteRunStore`、`SQLiteOperationMemoryBackend` 的公开接口。
- 不自动迁移历史 `data/api_runs/*.json` 或 `memory/operation_history.json`。
- 不引入 ORM。
- 不引入 PostgreSQL、Redis、pgvector 或 GraphRAG。
- 不改变采集、生成、审核、发布、表现回填的业务行为。
- 不新增复杂前端页面。

## 当前存储现状

现有 SQLite 能力已经覆盖三类基础设施表：

- `runs`
  - 当前由 `app.run_store.SQLiteRunStore` 管理。
  - 保存 run 主记录、请求、摘要、内容、insights、完整 state 和路径。
  - 主要用于 API 查询和队列恢复兼容。
- `run_queue_jobs`
  - 当前由 `app.run_queue.SQLiteRunQueue` 管理。
  - 保存 queued/running/succeeded/failed 队列状态。
  - 主要用于 API/worker 拆分后的任务调度。
- `operation_records`
  - 当前由 `memory.operation_store.SQLiteOperationMemoryBackend` 管理。
  - 保存运营记忆记录和少量索引列。
  - 主要用于历史内容检索、表现录入和 successful patterns。

这三类表继续作为兼容层保留，不在本轮拆掉。新增业务表从 run state 和 operation record 中提取可查询字段，但仍保留 `payload_json` 或 `raw_json`，避免初版字段拆得过细导致返工。

## 推荐表结构

### run_events

记录 run 内部事件时间线，后续用于日志、监控、失败诊断和审计。

```sql
CREATE TABLE IF NOT EXISTS run_events (
  event_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  node_name TEXT,
  status TEXT,
  message TEXT,
  error TEXT,
  started_at TEXT,
  finished_at TEXT,
  duration_ms INTEGER,
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_run_events_run_id_created_at
ON run_events(run_id, created_at);

CREATE INDEX IF NOT EXISTS idx_run_events_type
ON run_events(event_type);
```

### raw_notes

保存脱敏后的采集笔记样本。平台敏感 token 不进入此表。

```sql
CREATE TABLE IF NOT EXISTS raw_notes (
  note_row_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  topic TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'xhs_pc',
  source_note_id TEXT,
  title TEXT,
  note_url TEXT,
  note_type TEXT,
  likes INTEGER NOT NULL DEFAULT 0,
  collects INTEGER NOT NULL DEFAULT 0,
  comments INTEGER NOT NULL DEFAULT 0,
  shares INTEGER NOT NULL DEFAULT 0,
  raw_json TEXT NOT NULL DEFAULT '{}',
  collected_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_notes_run_id
ON raw_notes(run_id);

CREATE INDEX IF NOT EXISTS idx_raw_notes_topic
ON raw_notes(topic);

CREATE INDEX IF NOT EXISTS idx_raw_notes_source_note_id
ON raw_notes(source_note_id);
```

### collection_candidates

保存候选池评分、排名和入选标记，是后续 RAG 入库质量的重要入口。

```sql
CREATE TABLE IF NOT EXISTS collection_candidates (
  candidate_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  note_row_id TEXT,
  topic TEXT NOT NULL,
  rank INTEGER NOT NULL,
  selected INTEGER NOT NULL DEFAULT 0,
  score INTEGER NOT NULL DEFAULT 0,
  title TEXT,
  note_url TEXT,
  reasons_json TEXT NOT NULL DEFAULT '[]',
  penalties_json TEXT NOT NULL DEFAULT '[]',
  score_breakdown_json TEXT NOT NULL DEFAULT '{}',
  candidate_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (note_row_id) REFERENCES raw_notes(note_row_id)
);

CREATE INDEX IF NOT EXISTS idx_collection_candidates_run_rank
ON collection_candidates(run_id, rank);

CREATE INDEX IF NOT EXISTS idx_collection_candidates_topic_score
ON collection_candidates(topic, score);

CREATE INDEX IF NOT EXISTS idx_collection_candidates_selected
ON collection_candidates(run_id, selected);
```

### raw_comments

保存脱敏后的评论样本，保留来源笔记标题或 `note_row_id`，不保存用户 ID、头像、昵称等标识。

```sql
CREATE TABLE IF NOT EXISTS raw_comments (
  comment_row_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  note_row_id TEXT,
  topic TEXT NOT NULL,
  source_note_title TEXT,
  content TEXT NOT NULL,
  like_count INTEGER NOT NULL DEFAULT 0,
  kept INTEGER NOT NULL DEFAULT 1,
  noise_reason TEXT,
  raw_json TEXT NOT NULL DEFAULT '{}',
  collected_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (note_row_id) REFERENCES raw_notes(note_row_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_comments_run_id
ON raw_comments(run_id);

CREATE INDEX IF NOT EXISTS idx_raw_comments_topic
ON raw_comments(topic);

CREATE INDEX IF NOT EXISTS idx_raw_comments_note_row_id
ON raw_comments(note_row_id);
```

### analysis_reports

保存本阶段新增的 `analysis_report`，用于后续数据分析、RAG 入库解释和工作台展示。

```sql
CREATE TABLE IF NOT EXISTS analysis_reports (
  report_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE,
  topic TEXT NOT NULL,
  candidate_count INTEGER NOT NULL DEFAULT 0,
  selected_count INTEGER NOT NULL DEFAULT 0,
  raw_comments_count INTEGER NOT NULL DEFAULT 0,
  evidence_count INTEGER NOT NULL DEFAULT 0,
  comment_quality_level TEXT,
  pain_point_confidence_level TEXT,
  pain_point_confidence_score INTEGER NOT NULL DEFAULT 0,
  recommended_type TEXT,
  risks_json TEXT NOT NULL DEFAULT '[]',
  summary TEXT,
  report_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_analysis_reports_topic
ON analysis_reports(topic);

CREATE INDEX IF NOT EXISTS idx_analysis_reports_quality
ON analysis_reports(comment_quality_level, pain_point_confidence_level);
```

### drafts

保存生成内容草稿，兼容图文和视频。

```sql
CREATE TABLE IF NOT EXISTS drafts (
  draft_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  operation_record_id TEXT,
  topic TEXT NOT NULL,
  content_format TEXT NOT NULL,
  content_type TEXT,
  title TEXT,
  titles_json TEXT NOT NULL DEFAULT '[]',
  body TEXT,
  cover_texts_json TEXT NOT NULL DEFAULT '[]',
  image_page_plan_json TEXT NOT NULL DEFAULT '[]',
  image_prompts_json TEXT NOT NULL DEFAULT '[]',
  video_script_json TEXT NOT NULL DEFAULT '{}',
  tags_json TEXT NOT NULL DEFAULT '[]',
  comment_call TEXT,
  markdown_path TEXT,
  status TEXT NOT NULL DEFAULT 'draft',
  draft_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_drafts_run_id
ON drafts(run_id);

CREATE INDEX IF NOT EXISTS idx_drafts_topic
ON drafts(topic);

CREATE INDEX IF NOT EXISTS idx_drafts_status
ON drafts(status);
```

### creator_assets

保存图片素材和 run 绑定关系，包含手动素材和生成素材。

```sql
CREATE TABLE IF NOT EXISTS creator_assets (
  asset_id TEXT PRIMARY KEY,
  run_id TEXT,
  draft_id TEXT,
  source TEXT NOT NULL,
  provider TEXT,
  model TEXT,
  file_path TEXT NOT NULL,
  file_name TEXT,
  mime_type TEXT,
  file_size INTEGER,
  width INTEGER,
  height INTEGER,
  prompt TEXT,
  bound_order INTEGER,
  status TEXT NOT NULL DEFAULT 'available',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (draft_id) REFERENCES drafts(draft_id)
);

CREATE INDEX IF NOT EXISTS idx_creator_assets_run_id
ON creator_assets(run_id);

CREATE INDEX IF NOT EXISTS idx_creator_assets_status
ON creator_assets(status);
```

### creator_notes

保存创作者平台笔记 ID、发布状态、可见性和状态同步信息。

```sql
CREATE TABLE IF NOT EXISTS creator_notes (
  creator_note_id TEXT PRIMARY KEY,
  run_id TEXT,
  operation_record_id TEXT,
  draft_id TEXT,
  title TEXT,
  publish_mode TEXT,
  publish_status TEXT,
  visibility_label TEXT,
  permission_code TEXT,
  tab_status TEXT,
  platform_type TEXT,
  metrics_snapshot_json TEXT NOT NULL DEFAULT '{}',
  last_sync_status TEXT,
  last_synced_at TEXT,
  publish_response_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (draft_id) REFERENCES drafts(draft_id)
);

CREATE INDEX IF NOT EXISTS idx_creator_notes_run_id
ON creator_notes(run_id);

CREATE INDEX IF NOT EXISTS idx_creator_notes_operation_record_id
ON creator_notes(operation_record_id);

CREATE INDEX IF NOT EXISTS idx_creator_notes_publish_status
ON creator_notes(publish_status);
```

### performance_records

保存表现数据快照。一个平台笔记可以有多次表现快照。

```sql
CREATE TABLE IF NOT EXISTS performance_records (
  performance_id TEXT PRIMARY KEY,
  operation_record_id TEXT,
  creator_note_id TEXT,
  run_id TEXT,
  views INTEGER NOT NULL DEFAULT 0,
  likes INTEGER NOT NULL DEFAULT 0,
  collects INTEGER NOT NULL DEFAULT 0,
  comments INTEGER NOT NULL DEFAULT 0,
  follows INTEGER NOT NULL DEFAULT 0,
  performance_score INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'manual',
  notes TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}',
  recorded_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (creator_note_id) REFERENCES creator_notes(creator_note_id)
);

CREATE INDEX IF NOT EXISTS idx_performance_records_creator_note_id
ON performance_records(creator_note_id, recorded_at);

CREATE INDEX IF NOT EXISTS idx_performance_records_operation_record_id
ON performance_records(operation_record_id, recorded_at);
```

### audit_events

保存人工审核、发布确认、表现录入、配置检查等关键动作。

```sql
CREATE TABLE IF NOT EXISTS audit_events (
  audit_id TEXT PRIMARY KEY,
  run_id TEXT,
  operation_record_id TEXT,
  actor TEXT,
  action TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  result TEXT,
  message TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_audit_events_run_id_created_at
ON audit_events(run_id, created_at);

CREATE INDEX IF NOT EXISTS idx_audit_events_action
ON audit_events(action);
```

## 数据写入时机

初版建议分三步落地，不一次性接管所有写入。

### 第一阶段：schema 与仓储边界

- 新增 `app/database_schema.py` 或 `app/database.py`，负责建表 SQL 和初始化。
- 新增测试验证所有表能创建、索引存在、初始化幂等。
- 不改变现有 run 执行行为。

### 第二阶段：run 完成后的快照写入

在 run 成功、审核通过、保存草稿或表现回填后，从现有 run record/state 中同步写入业务表：
- `raw_notes`
- `collection_candidates`
- `raw_comments`
- `analysis_reports`
- `drafts`
- `creator_assets`
- `creator_notes`
- `performance_records`
- `audit_events`

这一阶段以“旁路写入”为主，现有 API 仍读取 `runs` 和 `operation_records`，避免大范围改查询。

### 第三阶段：查询切换

当旁路表积累稳定后，再逐步把工作台、分析报告、记忆检索、表现趋势等查询切到业务表。

## ID 和幂等策略

所有新表使用文本主键，避免 SQLite/PostgreSQL 自增差异：
- `event_id = evt_<hash/run_id/time/type>`
- `note_row_id = note_<hash(run_id + note_url/title)>`
- `candidate_id = cand_<hash(run_id + rank + title)>`
- `comment_row_id = cmt_<hash(run_id + source_note_title + content)>`
- `report_id = rpt_<run_id>`
- `draft_id = drf_<run_id>`
- `asset_id = ast_<hash(run_id + file_path)>`
- `performance_id = perf_<hash(creator_note_id + recorded_at)>`
- `audit_id = aud_<hash(run_id + action + created_at)>`

写入使用 upsert，保证同一个 run 重复同步不会产生大量重复行。历史迁移脚本也应复用同一套 ID 规则。

## 敏感数据边界

以下字段不得进入业务表明文字段或 JSON 字段：
- Cookie。
- Authorization header。
- API key。
- xsec_token。
- 用户昵称、头像、主页、用户 ID、评论 ID。
- 未脱敏平台原始响应。

如果后续必须保存平台原始响应，只能保存经过现有脱敏函数处理后的版本，并写入 `raw_json` 或 `payload_json`。

## 与现有表的关系

- `runs` 仍是 run API 的主记录。
- `operation_records` 仍是运营记忆兼容层。
- 新表围绕 `run_id`、`operation_record_id`、`creator_note_id` 建立关联。
- 初版不强依赖 SQLite 外键强制开启；外键声明用于文档和未来 PostgreSQL 迁移。
- `payload_json`、`raw_json`、`report_json` 保留完整结构，方便兼容现有 API 输出。

## 配置

复用现有数据库路径配置：

```env
XHS_AGENT_RUN_DB_PATH=data/xhs_agent.sqlite3
XHS_AGENT_MEMORY_DB_PATH=data/xhs_agent.sqlite3
XHS_AGENT_QUEUE_DB_PATH=data/xhs_agent.sqlite3
```

新增配置建议：

```env
XHS_AGENT_DB_SCHEMA=foundation
XHS_AGENT_BUSINESS_TABLES_ENABLED=false
```

含义：
- `XHS_AGENT_DB_SCHEMA=foundation`：初始化基础业务表。
- `XHS_AGENT_BUSINESS_TABLES_ENABLED=false`：默认只建表，不旁路写入。后续实现第二阶段时再开启写入。

## 测试计划

schema 测试：
- 初始化数据库会创建所有基础业务表。
- 初始化重复执行不会报错。
- 每张表的关键索引存在。
- `runs`、`run_queue_jobs`、`operation_records` 已存在时，新增 schema 不破坏旧表。

数据写入测试：
- 用一份模拟 run state 同步写入 `raw_notes`、`collection_candidates`、`raw_comments`、`analysis_reports`。
- 重复同步同一 run 不产生重复行。
- 敏感字段不会出现在业务表 JSON 中。

兼容测试：
- 现有 `SQLiteRunStore` 测试继续通过。
- 现有 `SQLiteOperationMemoryBackend` 测试继续通过。
- 现有 `SQLiteRunQueue` 测试继续通过。
- 全量测试通过。

## 完成标准

本设计落地后的第一阶段完成标准：
- 有统一 schema 初始化入口。
- 新增业务表和索引可在 SQLite 中创建。
- 初始化过程幂等。
- 不改变当前默认 JSON 行为。
- 不改变现有 API 响应结构。
- 不迁移历史数据。
- 全量测试通过。

第二阶段完成标准：
- 新 run 可旁路写入候选、评论、分析报告、草稿、素材、平台笔记和表现快照。
- 同一 run 重复同步幂等。
- 工作台/API 仍保持原响应结构。

## 风险与边界

- 表较多，但这是为了给后续查询、分析和 GraphRAG 准备稳定边界；初版实现可以先只建表和写入核心四张表。
- SQLite 适合本地和单机部署，未来生产化仍可迁移 PostgreSQL。
- JSON 保底字段会带来重复存储，但能降低初版 schema 设计错误的返工成本。
- 旁路写入阶段可能出现 `runs` 已成功但业务表同步失败的情况，后续需要 `run_events` 或 repair 脚本补偿。

## 下一步实施建议

第一轮实现建议只做：
- `app/database_schema.py`：基础表 SQL 和初始化函数。
- `tests/test_foundation_database_schema.py`：建表、索引、幂等、旧表兼容测试。
- `.env.example`：新增配置说明。

第二轮再做：
- `app/business_store.py`：从 run state 同步写入核心业务表。
- `scripts/sync_run_to_business_tables.py`：手动补偿脚本。
- 核心四张表旁路写入：`raw_notes`、`collection_candidates`、`raw_comments`、`analysis_reports`。
