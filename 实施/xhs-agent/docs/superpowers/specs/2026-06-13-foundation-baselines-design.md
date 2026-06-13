# 三条基础线一期闭环设计

## 目标

在继续主线功能开发之前，先补齐三条基础线的一期最小闭环：

1. RAG / GraphRAG 之前的数据质量基线。
2. 剩余硬编码业务规则的配置治理。
3. 面向最终部署的 production-lite 部署基线。

本轮目标是“小而可测、能落地、不给后续返工埋坑”。它必须兼容当前 LangGraph-first、SQLite-capable 的运行时，不引入向量检索、图数据库、Docker、Nginx、systemd、Redis、用户账号体系，也不扩大真实平台写入行为。

## 当前状态

项目已经具备：

- 采集候选池评分和入选标记，结果写入 `collection_candidates`。
- 确定性 `analysis_report`，覆盖样本选择、评论质量、痛点可信度、结构建议和风险。
- SQLite run store、SQLite queue、SQLite operation memory、业务表 overlay、表现记录、运行事件和本地 stack 脚本。
- M5 第一片：`app/memory_graph.py` 能从 operation memory 派生图谱视图。
- 最小生产护栏：可选 API token、日志脱敏、运行配置检查、启动/健康检查/停止/日志脚本。

项目仍然缺少：

- 明确的 RAG 入库资格判断，无法判断一次 run 是否足够干净、可信、可进入后续 RAG / GraphRAG 记忆。
- 可配置的数据分析阈值和跨领域污染过滤规则。
- 比现有 runtime config 更贴近部署前检查的 production-lite checklist。
- 面向单 SQLite DB 形态的备份和恢复脚本。

## 范围

### 本轮包含

数据质量线：

- 新增确定性的质量门槛模块，消费现有 run state 字段：
  - `analysis_report`
  - `collection_candidates`
  - `raw_comments`
  - `comment_insights`
  - `pain_points`
  - `comment_fetch_errors`
- 返回 `rag_eligibility` 对象：
  - `eligible`
  - `level`
  - `score`
  - `reasons`
  - `blocking_reasons`
  - `recommended_action`
- 在可复用现有同步路径的前提下，把门槛结果写入 run state 和业务表 JSON payload。

配置治理线：

- 把 `analysis_report` 中的质量阈值从代码迁移到新的 JSON 配置文件。
- 把 operation memory 的跨领域健康污染关键词和模式迁移到配置文件。
- 代码里只保留缺省标签等安全兜底，不再把业务策略硬编码在 Python 里。

部署基线：

- 新增 production-lite 部署检查脚本，检查：
  - API token 已设置。
  - run store、queue、memory 都使用 SQLite。
  - 数据库 schema 使用 foundation。
  - 业务表写入已开启。
  - 日志目录可写。
  - DB 父目录可写。
  - 备份目录可写。
  - 真实 LLM key 和 Spider_XHS cookie 存在；缺失时给出 warning，不打印明文值。
- 新增 SQLite 备份和恢复脚本。
- 更新文档，明确本轮能支持什么，以及公网正式部署前仍缺什么。

### 本轮不包含

- embedding、向量数据库、pgvector、图数据库或完整 GraphRAG 入库。
- 历史数据全量迁移。
- Docker、Nginx、systemd、HTTPS 证书、Redis/RQ/Celery 或用户账号体系。
- 公开发布、视频发布、平台定时发布或扩大 creator 写入范围。
- cookie 落盘加密。它属于后续安全专项。

## 架构设计

### 数据质量门槛

新增 `app/data_quality_gate.py`。

职责：

- 从配置文件加载阈值规则。
- 基于现有结构化字段做判断，不重新采集、不访问平台。
- 生成紧凑的 `rag_eligibility`，供 run state、业务表 payload、后续 GraphRAG 入库和前端展示复用。

建议返回结构：

```json
{
  "eligible": false,
  "level": "blocked",
  "score": 38,
  "reasons": ["候选池存在，但评论证据偏少"],
  "blocking_reasons": ["评论样本较少", "痛点证据不足"],
  "recommended_action": "重新采集更多候选和评论后再进入 RAG 入库"
}
```

评分先保持简单、确定性：

- 以 `analysis_report.pain_point_confidence.score` 作为主信号。
- 叠加入选候选数信号。
- 叠加评论洞察和证据数信号。
- 对评论抓取错误做惩罚。
- 候选为空、评论为空、证据不足或置信度低于配置阈值时阻断。

### 配置文件

新增 `config/data_quality_rules.json`。

初始结构：

```json
{
  "rag_gate": {
    "min_score": 60,
    "min_selected_candidates": 1,
    "min_raw_comments": 5,
    "min_evidence_count": 2,
    "block_on_comment_fetch_errors": false
  },
  "analysis_report": {
    "high_quality_min_comments": 20,
    "high_quality_min_evidence": 5,
    "medium_quality_min_comments": 5,
    "medium_quality_min_evidence": 2,
    "comment_fetch_error_penalty": 15,
    "empty_sample_score_cap": 45
  },
  "cross_domain_pollution": {
    "health_topic_keywords": [],
    "health_pollution_patterns": []
  }
}
```

实际关键词列表从 `memory/operation_store.py` 迁移到这个文件。

扩展 `app/rules.py`，新增 `load_data_quality_rules()`。

### 集成点

数据质量门槛采用最低风险接入方式：

- `platforms/analysis_report.py` 读取配置阈值，但保持现有返回结构不变。
- 在 `analysis_report` 生成之后，为 run state 增加 `rag_eligibility`。
- 业务表同步先把 `rag_eligibility` 放入现有脱敏 JSON payload；专用列可以留到后续 schema 迁移。
- `memory_graph` 继续保持只读派生视图，本轮不新增真正 RAG 入库。

### 部署辅助脚本

新增脚本：

- `scripts/check_production_lite_deploy.py`
- `scripts/backup_sqlite_db.py`
- `scripts/restore_sqlite_db.py`

`check_production_lite_deploy.py` 应尽量复用 `scripts/check_runtime_config.py` 的能力，在此基础上补部署专项检查，避免重复维护两套逻辑。

备份脚本行为：

- DB 路径默认解析到项目内；传入绝对路径时按绝对路径处理。
- 默认备份到 `data/backups`。
- 生成带时间戳的备份文件。
- 不覆盖已有备份。
- 输出结构化 JSON。

恢复脚本行为：

- 默认 dry-run。
- 必须显式传入 `--apply` 才替换目标 DB。
- 替换前先创建 pre-restore 备份。
- 不删除任何文件。
- 输出结构化 JSON。

## 错误处理

- 必需配置缺失或 JSON 格式错误时，通过 `app.rules` 抛出清晰错误。
- 数据质量门槛遇到缺失字段时不抛异常，而是返回 blocked 或 low confidence。
- 备份和恢复脚本不能删除文件。
- 恢复脚本没有 `--apply` 时不能修改 DB。
- 所有脚本输出都不能打印 cookie、API key、authorization header 或 `.env` 明文值。

## 测试设计

新增聚焦测试：

- `tests/test_data_quality_gate.py`
  - 候选、评论、证据和置信度充足时返回 eligible。
  - 评论或证据缺失时返回 blocked。
  - 存在评论抓取错误时按配置惩罚或阻断。
- `tests/test_analysis_report_config.py`
  - 配置阈值能影响评论质量等级。
- `tests/test_operation_memory_config.py`
  - 跨领域污染关键词从配置加载，非健康主题仍能阻断健康类污染。
- `tests/test_production_lite_deploy_check.py`
  - 缺少 API token 时失败。
  - SQLite production-lite 设置齐全时通过。
  - 备份目录不存在时能创建或报告可写。
- `tests/test_sqlite_backup_restore_scripts.py`
  - 备份脚本生成带时间戳的副本。
  - restore dry-run 不修改 DB。
  - restore `--apply` 会创建 pre-restore 备份并替换 DB。

验证顺序：

1. 先跑新增定点测试。
2. 再跑相关回归测试。
3. 最后视时间跑全量测试。

## 文档更新

需要更新：

- `docs/m17b-startup-templates.md`：补 production-lite 部署 checklist、备份和恢复命令。
- `memory/current_progress.md`：记录本轮完成内容、验证结果和限制。
- `memory/project_status_and_roadmap.md`：把三条基础线标记为“一期开始/初版完成”，不能写成彻底完成。

## 验收标准

- `analysis_report` 的质量阈值可配置。
- operation memory 的跨领域污染规则可配置。
- run state 能暴露 `rag_eligibility`，且不引入完整 RAG。
- 有独立 production-lite 部署检查脚本。
- 有 SQLite 备份和恢复脚本，并有测试覆盖。
- 不读取或输出 `.env` 明文敏感值。
- 现有 local/mock 流程保持可用。

## 本轮之后仍未完成

- 完整 RAG / GraphRAG 入库和向量召回。
- 历史 JSON 与 operation memory 全量迁移。
- 为 RAG eligibility 和质量指标增加专用业务表列。
- 公网生产部署所需的 HTTPS、反向代理、进程守护、用户账号和更强密钥治理。
- 完整 BI 与时间序列分析。
