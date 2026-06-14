# 当前工程进度

## 2026-06-14 M5 合规留痕与召回解释可见化设计确认

本轮开始 M5 第五片设计：在第四片规则版合规风险召回之后，补齐 operation memory 合规字段留痕、API 暴露、结构化合规风险召回优先级，以及工作台召回解释的轻量展示。

已完成：
- 已确认下一片采用“合规留痕与召回解释可见化”方案，并允许在同一条链路内适度扩大范围。
- 已新增中文设计文档：`docs/superpowers/specs/2026-06-14-m5-compliance-memory-and-recall-visibility-design.md`。
- 设计范围包含 operation memory 合规字段、memory records API、`historical_compliance_risks` 结构化来源优先、工作台相似经验/历史风险/召回解释展示。
- 明确本轮不做 embedding、向量库、历史大迁移、复杂图谱可视化或真实平台写入。

下一步：
- 写实施计划并按 TDD 执行。
- 优先覆盖 operation store 留痕、API compact、memory graph 结构化命中、工作台静态渲染和相关回归。

## 2026-06-14 M5 规则版相似经验与合规风险召回完成

本轮完成 M5 第四片：在不引入 embedding、向量库、图数据库或新外部服务的前提下，用规则版增强现有 `graphrag_memory`，让系统能基于当前痛点和合规风险召回跨主题相似经验与历史风险提醒。

已完成：
- 已确认采用“规则版召回增强”方案，而不是直接进入 embedding/向量检索。
- 已新增中文设计文档：`docs/superpowers/specs/2026-06-14-m5-rule-based-recall-enhancement-design.md`。
- 已新增中文实施计划：`docs/superpowers/plans/2026-06-14-m5-rule-based-recall-enhancement.md`。
- `app/memory_graph.py` 支持传入当前痛点、评论洞察和合规信息，并返回 `similar_experience_records`、`similar_pain_points`、`historical_compliance_risks` 和 `recall_explanations`。
- `nodes/memory_node.retrieve_graphrag_memory()` 会把当前 state 的痛点、评论洞察、合规风险等级和合规 issue 传给图谱召回层。
- `nodes/memory_context.py` 会把相似经验和历史合规风险压缩进生成上下文，并继续控制字段长度。
- 明确本轮不改变真实平台写入、不改变 RAG 入库门槛、不做历史大迁移、不新增复杂前端图谱。

验证：
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_graph.py tests/test_memory_node.py tests/test_memory_context.py -q` -> `14 passed`。
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_strategy_memory_context.py tests/test_generation_memory_context.py tests/test_api_memory_graph.py -q` -> `9 passed`。
- `D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes memory tests` -> exit code 0。

当前限制：
- 本轮仍是规则版召回，不是 embedding/向量检索。
- operation memory 仍未统一保存完整 `compliance_issues` / `compliance_risk_level`，历史风险召回会优先使用已有字段，并兼容扫描复盘摘要、下一步建议等文本。
- 工作台暂未展示新增的相似经验和历史风险提醒。

下一步：
- 可继续评估 embedding/向量检索的最小可测方案。
- 可补 operation memory 的合规字段留痕，提高历史风险召回质量。
- 可把新增召回解释展示到工作台召回依据区。

## 2026-06-14 手动合并后的遗留问题收口

本轮目标是接续用户手动执行后的状态：先核对本地合并结果，收口不会触碰远端和旧分支的遗留问题，再为下一条主线任务做规划复核。

已完成：
- 本地 `master` 当前 HEAD 为 `533778f docs: record rag eligibility recall evidence progress`，与 `codex/m5-rag-eligibility-recall` 和 `origin/codex/m5-rag-eligibility-recall` 指向一致。
- `git status --short --branch` 显示本地 `master` 仍为 `## master...origin/master [ahead 36]`，说明本地远端引用尚未确认同步。
- 尝试 `git fetch origin` 时被 `.git/FETCH_HEAD` 权限阻断；提权请求未获系统审批，因此本轮未能自动刷新 `origin/master`。
- 已同步 `AGENTS.md` 中过时的 M5 状态、当前优先级、最近提交与旧 worktree 提示，避免后续线程继续按“M5 第三片未完成”的旧信息推进。
- 用户授权后已用 `git worktree remove` 清理旧 worktree `.worktrees/m5-rag-eligibility-recall-evidence`；本地分支 `codex/m5-rag-eligibility-recall-evidence` 仍保留。
- 未推送 `master`，未改动业务代码。

当前遗留：
- 远端 `origin/master` 是否已被用户手动推送同步，仍需用户在本机手动 `git fetch origin` 后确认。
- GitHub PR 是否已创建仍未确认；`gh` CLI 不可用时可继续使用网页 compare 链接创建。
- 本地分支 `codex/m5-rag-eligibility-recall-evidence` 尚未删除，后续如确认不再需要可单独清理。

下一步主线建议：
- 继续 M5，但不急于直接引入向量库或图数据库。
- 优先候选一：基于现有 operation memory 做跨主题相似经验召回的轻量规则版，把相似痛点、内容类型和高表现记录纳入 `graphrag_memory`。
- 优先候选二：补合规风险历史召回，把过往高风险/中风险命中原因作为生成和审核前的提醒。
- embedding/向量检索可作为下一阶段设计任务，在规则版召回边界稳定后再评估最小可测方案。

## 2026-06-14 M5 RAG 入库门槛与召回依据展示

本轮继续推进 M5 第三片：在不引入向量库、图数据库或新外部服务的前提下，用 `rag_eligibility` 控制长期运营记忆写入，并在工作台展示当前主题的召回依据。

已完成：
- `write_operation_memory()` 会在 `publish_status=success` 后检查 `rag_eligibility`；明确 blocked 的 run 不再写入长期运营记忆。
- run summary 会返回 `operation_memory_skip_reason` 和 `operation_memory_skip_detail`。
- 运营记忆记录保存 `rag_eligibility`，用于后续入库审计和补偿。
- memory records API 暴露 `rag_eligibility`。
- 工作台复用 `/memory/graph?topic=...` 展示推荐内容类型、相关痛点和召回记录。
- mock collector 补足开发基线评论样本，creator review 测试夹具显式使用 mock collector/mock LLM，避免继承本地 `.env` 导致测试数据被 RAG 门槛误阻断。

当前限制：
- 本轮不改变历史召回过滤逻辑，不过滤旧记录。
- 本轮不是完整 RAG/GraphRAG：仍没有 embedding、向量检索、图数据库或跨主题语义召回。
- 工作台只做结构化文本展示，不做复杂图谱可视化。

验证：
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_node.py tests/test_operation_store_sqlite.py tests/test_api_memory_graph.py -q` -> `13 passed`。
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_memory_visibility_static.py -q` -> `4 passed`。
- `node --check app/static/app.js` -> exit code 0。
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_graph.py tests/test_memory_context.py tests/test_strategy_memory_context.py tests/test_generation_memory_context.py tests/test_memory_node.py -q` -> `16 passed`。
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` -> `307 passed`。
- `D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes memory platforms tests` -> exit code 0。

## 2026-06-14 项目阅读与下一步规划复核

本次目标是重新阅读当前项目状态，梳理主线任务，并确认下一步规划。已对照根目录 `从0实现指导手册.md` 的 M0-M6 主线、`AGENTS.md`、`memory/current_progress.md`、`memory/project_status_and_roadmap.md`、现有 M5 规格/计划文档和关键代码边界。

当前判断：
- 主代码目录仍是 `实施/xhs-agent`，仓库工作树当前干净，本地分支领先远端。
- M0-M4 已形成阶段一 MVP 和 creator 私密图文闭环基线；公开图文、视频发布、定时发布继续后置。
- M5 已完成图谱视图初版和记忆消费侧初版，但第三片“RAG 入库门槛与召回依据展示”尚未落到业务代码。
- 现有计划 `docs/superpowers/plans/2026-06-13-m5-rag-eligibility-and-recall-evidence.md` 可作为下一步执行计划。
- 当前 `write_operation_memory()` 仍只按 `publish_status=success` 写入长期运营记忆，尚未检查 `rag_eligibility`。
- 当前 `record_from_state()` 尚未保存 `rag_eligibility`，API summary 尚未暴露记忆跳过原因，工作台尚未展示 `/memory/graph` 召回依据。

下一步建议：
- 直接执行 M5 第三片计划，顺序为：运营记忆写入门槛 -> 运营记忆记录留痕 -> API 摘要字段 -> 工作台召回依据展示 -> 文档与回归收口。
- 本轮继续保持边界：不引入 embedding、向量库、图数据库、新外部服务或新的真实平台写入行为。

## 2026-06-13 项目阅读与下一主线确认

本次目标是阅读当前项目状态，明确下一步主线任务。已对照 `AGENTS.md`、`memory/current_progress.md`、`memory/project_status_and_roadmap.md` 和根目录 `从0实现指导手册.md` 的 M0-M6 主线。

当前判断：
- M0-M4 已形成阶段一 MVP、LangGraph-first 主链和私密图文 creator 闭环基线；公开视频、视频发布和定时发布仍后置，执行前需要重新确认真实平台写入风险。
- M5 已完成两片：operation memory 派生图谱视图与查询初版、`graphrag_memory` 进入策略和 LLM prompt 的消费侧初版。
- M6 阶段二软广与达人仍未开始，继续后置。
- 当前工作树除协作约定文档 `AGENTS.md` 外，未发现业务代码未提交改动。

下一步主线任务：
- 继续 M5，优先做“按 `rag_eligibility` 控制可入库长期记忆 + 工作台展示召回依据”。

建议边界：
- 本轮先不引入 embedding、向量库、图数据库或新的外部服务。
- 先把现有结构化数据和召回证据的质量门槛、可解释展示做扎实，再评估后续真正 RAG/GraphRAG 入库与向量召回。

## 2026-06-13 M5 GraphRAG 记忆消费侧初版

本轮目标是在 M5 图谱视图初版之后，继续推进第二片：让 `graphrag_memory` 从“主流程能产出”变成“策略和生成链路能消费”。范围只覆盖现有 operation memory 派生视图的消费侧，不引入向量库、图数据库、新入库流程或前端图谱展示。

已完成：
- 新增中文设计文档：
  - `docs/superpowers/specs/2026-06-13-m5-graphrag-memory-consumption-design.md`
- 新增中文实施计划：
  - `docs/superpowers/plans/2026-06-13-m5-graphrag-memory-consumption.md`
- 新增 `nodes/memory_context.py`：
  - 统一从 `XHSState.graphrag_memory` 提取推荐内容类型、相关痛点和召回证据。
  - 过滤非法 content type、无证据推荐、异常结构和空字段。
  - 为生成节点输出紧凑的 `memory_context` prompt payload。
- 改造 `nodes/strategy_node.py`：
  - 策略优先级调整为：关键词规则 > GraphRAG 推荐 > `successful_patterns` > 默认类型。
  - 保留冷启动和软广限制兜底。
- 改造 `nodes/content_node.py` 和 `nodes/video_node.py`：
  - LLM input payload 增加 `memory_context`。
  - JSON 输出合同不变。
  - fallback 模板不强依赖历史记忆，记忆为空时行为保持稳定。
- 新增测试：
  - `tests/test_memory_context.py`
  - `tests/test_strategy_memory_context.py`
  - `tests/test_generation_memory_context.py`

已验证：
- TDD RED：
  - `tests/test_memory_context.py` 先因 `nodes.memory_context` 缺失失败。
  - `tests/test_strategy_memory_context.py` 先因策略仍返回 `knowledge_share` 而失败。
  - `tests/test_generation_memory_context.py` 先因 prompt payload 缺少 `memory_context` 而失败。
- RED->GREEN：
  - `tests/test_memory_context.py` -> `5 passed`。
  - `tests/test_strategy_memory_context.py tests/test_memory_context.py` -> `8 passed`。
  - `tests/test_generation_memory_context.py tests/test_memory_context.py` -> `8 passed`。
  - 新增定点组合：`tests/test_memory_context.py tests/test_strategy_memory_context.py tests/test_generation_memory_context.py` -> `11 passed`。
- 相关回归：
  - `tests/test_memory_context.py tests/test_strategy_memory_context.py tests/test_generation_memory_context.py tests/test_memory_graph.py tests/test_memory_node.py tests/test_graph_run_events.py tests/test_langgraph_runtime.py` -> `21 passed`。
- Python 编译检查通过：
  - `D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes memory platforms scripts tests`。
- 全量测试通过：
  - `D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` -> `300 passed`。

当前效果：
- M5 已从“图谱视图可查询”推进到“下游策略和 LLM prompt 能消费图谱记忆”。
- 记忆解析集中在 `nodes/memory_context.py`，避免策略、图文、视频节点各自硬编码 `graphrag_memory` 结构。
- 生成节点现在能把召回证据、相关痛点和推荐结构交给 LLM，但不会把历史正文硬塞进 fallback 模板。

当前限制：
- 仍不是真正完整 RAG/GraphRAG：没有 embedding、向量检索、图数据库或跨主题语义召回。
- 还没有按 `rag_eligibility` 控制哪些 run 可以进入长期记忆。
- 前端尚未展示召回依据和图谱关系。
- 历史 operation memory 全量迁移仍未完成。
- 正式公网部署仍缺 HTTPS、反向代理、系统级进程守护、账号权限和更强密钥治理。

下一步建议：
- 继续 M5 时，优先做“按 `rag_eligibility` 控制可入库记忆 + 工作台展示召回依据”。
- 如果先收口部署，则继续补 production-lite 的真实配置模板、密钥治理和进程守护方案。

## 2026-06-13 三条基础线一期闭环

本轮目标是在继续 M5/M6 主线前，先补齐 RAG 前数据质量、硬编码配置治理和 production-lite 部署基线的最小可测闭环。范围控制在当前 LangGraph-first + SQLite runtime 内，不引入向量库、图数据库、Docker、Nginx、systemd、Redis 或新的真实平台写入行为。

已完成：
- 新增 `config/data_quality_rules.json`：
  - 统一保存 RAG 入库门槛、`analysis_report` 阈值和跨领域健康污染过滤规则。
- 扩展 `app.rules.load_data_quality_rules()`。
- 改造 `platforms/analysis_report.py`：
  - 评论质量等级阈值、评论抓取失败惩罚和空样本分数上限改为配置驱动。
- 新增 `app/data_quality_gate.py`：
  - 基于 `analysis_report`、候选池、评论、评论洞察、痛点和抓取错误生成 `rag_eligibility`。
  - 输出 `eligible`、`level`、`score`、`reasons`、`blocking_reasons` 和 `recommended_action`。
- 扩展 `nodes/insight_node.py` 和 `app/state.py`：
  - 洞察分析后写入 `rag_eligibility`。
- 扩展 `app.api._insight_payload()`：
  - API insight payload 暴露 `rag_eligibility`，便于后续工作台展示。
- 改造 `memory/operation_store.py`：
  - 健康主题关键词和跨领域污染模式从配置加载，不再硬编码在 Python 常量里。
- 新增 production-lite 部署辅助脚本：
  - `scripts/check_production_lite_deploy.py`
  - `scripts/backup_sqlite_db.py`
  - `scripts/restore_sqlite_db.py`
- 更新 `docs/m17b-startup-templates.md`：
  - 补充部署检查、SQLite 备份和恢复命令。

已验证：
- `tests/test_analysis_report_config.py tests/test_analysis_report.py tests/test_analysis_report_integration.py tests/test_check_collector_output.py` -> `10 passed`。
- `tests/test_data_quality_gate.py tests/test_analysis_report_integration.py` -> `7 passed`。
- `tests/test_operation_memory_config.py tests/test_operation_store_sqlite.py tests/test_memory_graph.py tests/test_memory_node.py` -> `10 passed`。
- `tests/test_production_lite_deploy_check.py` -> `2 passed`。
- `tests/test_sqlite_backup_restore_scripts.py` -> `3 passed`。
- 最终新增定点组合：`tests/test_analysis_report_config.py tests/test_data_quality_gate.py tests/test_operation_memory_config.py tests/test_production_lite_deploy_check.py tests/test_sqlite_backup_restore_scripts.py` -> `10 passed`。
- 最终相关回归组合：`tests/test_analysis_report.py tests/test_analysis_report_integration.py tests/test_check_collector_output.py tests/test_operation_store_sqlite.py tests/test_memory_graph.py tests/test_memory_node.py tests/test_business_store.py tests/test_api_business_table_sync.py` -> `32 passed`。
- Python 编译检查通过：`D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes memory platforms scripts tests`。
- 全量测试通过：`D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` -> `289 passed`。
- 当前本地 `.env` 下运行 `scripts/check_production_lite_deploy.py --backup-dir data/backups` 按预期返回 `ok=false`：API token 缺失、run store/queue/memory 仍是开发默认、业务表写入未启用；这说明当前环境还不是 production-lite 部署配置。

当前效果：
- RAG/GraphRAG 入库前已经有明确的质量资格对象，但本轮不执行真正入库。
- 数据分析阈值和历史记忆污染规则已从源码迁到配置文件，后续可继续把 fallback 文案和更多质量规则外置。
- 单机 SQLite production-lite 部署多了部署前检查和备份/恢复入口。

当前限制：
- 还不是完整 RAG：没有 embedding、向量检索、图数据库、跨主题语义召回或前端召回依据展示。
- 还不是正式公网生产部署：仍缺 HTTPS、反向代理、系统级进程守护、自动重启、账号权限和更强密钥治理。
- 备份/恢复脚本只处理单 SQLite 文件形态，不处理多文件对象存储、图片素材目录或历史 JSON 大迁移。

下一步建议：
- 跑完本轮最终回归和编译检查后，再决定继续 M5 的 `graphrag_memory` 消费侧，或继续把 fallback 文案、质量阈值和部署脚本做进一步收口。

## 2026-06-13 M5 GraphRAG 运营记忆图谱视图初版

本轮目标是在工程化遗留项收口后，启动 M5 主线的第一片：先不引入新数据库、向量库或外部 GraphRAG 框架，而是基于现有 operation memory 记录生成可查询的图谱视图，为后续向量检索和召回解释打基础。

已完成：
- 新增 `app/memory_graph.py`：
  - 从 operation memory 记录抽取 `topic`、`pain`、`content_type`、`content_format`、`record` 节点。
  - 生成 `about_topic`、`addresses_pain`、`uses_content_type`、`uses_content_format`、`topic_has_pain`、`pain_uses_content_type` 等边。
  - 按主题过滤相关记录，避免单字模糊召回导致跨领域污染。
  - 输出高表现记录、相关痛点、推荐内容形式和召回证据。
- 新增 API：
  - `GET /memory/graph?topic=...&limit=...`
  - 返回 `memory_graph`，用于后续工作台展示召回依据或调试 M5 记忆。
- 扩展 `nodes/memory_node.retrieve_graphrag_memory()`：
  - 保留旧的 `retrieved_memory` 和 `successful_patterns`。
  - 新增 `graphrag_memory`，把图谱摘要写入 LangGraph state。
- 扩展 `app/state.py`：
  - 新增 `graphrag_memory` state 字段。

验证结果：
- TDD RED：`app.memory_graph` 缺失时新增测试先失败；`retrieve_graphrag_memory` 未返回 `graphrag_memory` 时节点测试先失败。
- RED->GREEN：`tests/test_memory_graph.py tests/test_api_memory_graph.py tests/test_memory_node.py` -> `4 passed`。
- 相关回归通过：记忆图谱、HTTP、记忆节点、operation store、graph events、LangGraph runtime -> `17 passed`。
- Python 编译检查通过：`D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes memory scripts tests`。

当前效果：
- M5 已从“未开始”推进到“基于现有运营记忆的图谱视图与查询初版”。
- 主流程已经能在记忆检索节点产出 `graphrag_memory`，但生成节点暂时还没有消费它。

当前限制：
- 还不是完整 GraphRAG：没有向量检索、embedding、图数据库或跨主题语义召回。
- 前端尚未展示 `memory_graph` 召回依据。
- 召回仍主要基于 operation memory 的结构化字段和保守文本包含匹配。

下一步建议：
- 继续 M5：把 `graphrag_memory` 用于内容策略/生成前的可解释召回输入，或先做工作台召回依据展示。
- 后续再评估是否加入 embedding/向量库；当前阶段先不引入新依赖。

## 2026-06-13 SQLite stack 健康检查、停止与日志脚本

本轮目标是在统一启动编排脚本之后，继续收口本地工程化遗留问题：补齐启动后的健康检查、停止和日志查看入口。该能力只管理本地运行进程和日志，不触发真实平台写入。

已完成：
- 新增 `scripts/check_sqlite_stack_health.ps1`：
  - 复用 `check_runtime_config.py --profile sqlite-worker` 做配置预检。
  - 支持检查本地 API `/health` 和 `/queue`。
  - 支持查找 `run_api.py`、`run_worker.py`、`run_creator_performance_scheduler.py` 相关进程。
  - 支持 `-ConfigOnly` 和 `-SkipApi`，便于不依赖 HTTP 服务的检查。
  - 当当前权限无法读取进程命令行时，输出 warning 并降级为空进程列表。
- 新增 `scripts/stop_sqlite_stack.ps1`：
  - 默认 dry-run，只列出匹配进程。
  - 只有显式传入 `-Apply` 才会 `Stop-Process`。
  - 只匹配已知运行入口，避免误停无关 Python 进程。
- 新增 `scripts/tail_sqlite_stack_logs.ps1`：
  - 读取 `api.log`、`worker.log`、`scheduler.log` 的尾部。
  - 日志不存在时只提示，不报错。
- 扩展 `tests/test_startup_templates.py` 覆盖三个新脚本的静态契约。
- 更新 `docs/m17b-startup-templates.md`，补充 health、tail logs 和 stop 用法。

验证结果：
- TDD RED：新增测试先因三个脚本缺失失败，`4 failed, 5 passed`。
- RED->GREEN：`tests/test_startup_templates.py` -> `9 passed`。
- `check_sqlite_stack_health.ps1 -ConfigOnly` 通过。
- `check_sqlite_stack_health.ps1 -SkipApi` 通过；当前环境读取进程命令行权限不足，已降级为 warning。
- `stop_sqlite_stack.ps1` dry-run 通过；没有传 `-Apply`，未停止任何进程。
- `tail_sqlite_stack_logs.ps1 -Tail 5` 通过，成功读取现有 API/worker 日志，`scheduler.log` 不存在时正常提示。

当前效果：
- SQLite stack 已有启动、健康检查、停止和日志查看四类本地运维入口。
- 对真实平台仍保持只读/显式触发边界。

当前限制：
- 停止脚本依赖进程命令行可见性；权限不足时只能 warning，无法列出目标进程。
- 仍没有系统级进程守护、崩溃自动重启和告警通知。

下一步建议：
- 工程化遗留项可以暂告一段落。
- 接下来进入 M5 GraphRAG 前的数据入库/查询设计与首个服务模块。

## 2026-06-13 SQLite stack 统一启动编排脚本

本轮目标是继续解决上一轮遗留的工程化问题：把 API、SQLite worker、watchdog 和平台指标 scheduler 的分散入口整合成一个统一启动脚本。该能力只做本地进程编排，不新增服务框架，不引入 Redis/Celery/systemd/Docker，也不扩大真实平台写入范围。

已完成：
- 新增 `scripts/start_sqlite_stack.ps1`：
  - 统一设置 SQLite run store、run queue、operation memory 的 DB 路径。
  - 统一设置 `COLLECTOR_MODE`、`CREATOR_MODE`、`LLM_MODEL_NAME`、API token 和 heartbeat 配置。
  - 默认启动 API、worker 和 watchdog loop。
  - 使用 `Start-Process -WindowStyle Hidden -PassThru` 启动子进程并输出 PID。
  - 支持 `-NoApi`、`-NoWorker`、`-NoWatchdog` 精简启动组件。
  - 支持 `-CheckOnly` 只运行 `check_runtime_config.py --profile sqlite-worker`。
  - 支持显式 `-StartScheduler`，并通过 `-CreatorNoteId` / `-RunId` 传入只读平台指标同步目标。
  - `-StartScheduler` 没有目标时会直接报错，避免误启动无目标轮询。
- 扩展 `tests/test_startup_templates.py`：
  - 覆盖统一脚本存在性、CheckOnly、Start-Process、隐藏窗口、API/worker/watchdog/scheduler 入口和调度器目标参数。
- 更新 `docs/m17b-startup-templates.md`：
  - 新增 SQLite Stack Mode 使用说明。
  - 明确 scheduler 仍是只读表现同步，不触发公开发布、编辑、删除或平台定时发布。

验证结果：
- TDD RED：新增启动模板测试先因 `start_sqlite_stack.ps1` 缺失失败，`3 failed, 3 passed`。
- RED->GREEN：`tests/test_startup_templates.py` -> `6 passed`。
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_sqlite_stack.ps1 -CheckOnly -Python D:\Anaconda\envs\ContentShare\python.exe` 通过，sqlite-worker profile 退出 0。

当前效果：
- 本地分进程运行从“多个分散脚本手动开多个终端”提升为“一条命令启动 API/worker/watchdog，可选 scheduler”。
- 后续长期巡检可以把 scheduler 挂进同一个 stack 入口，但仍需要用户显式提供目标。

当前限制：
- 这不是系统级进程守护；脚本启动后不负责自动重启崩溃进程。
- 还没有告警通知；scheduler 的失败停手仍主要通过结构化输出和日志观察。
- M5 GraphRAG、M6 软广/达人、公开视频/公开图文/平台定时发布仍未开始。

下一步建议：
- 如果继续收口工程化，可补“启动后健康检查/停止脚本/日志查看脚本”。
- 如果转主线，优先进入 M5 GraphRAG 前的数据入库/查询设计。

## 2026-06-13 平台指标后台同步调度器初版

本轮目标是在平台指标批量同步和工作台入口之后，继续收口 M4 的低风险遗留项：补一个模块化的后台同步调度入口。该能力只复用已有 creator 作品列表只读同步链路，不触发发布、编辑、删除、公开或平台定时发布。

已完成：
- 新增 `app/creator_performance_scheduler.py`：
  - 负责多轮调度、轮间等待、连续失败停手和汇总结果。
  - 每一轮只调用注入的批量同步函数，默认对接 `api.sync_creator_note_performance_batch()`。
  - 同步服务仍保留在 `app/creator_performance_sync.py`，调度器不直接耦合 HTTP、SQLite 或平台实现。
  - 支持 `max_rounds` 限制轮数，支持 `max_consecutive_failed_rounds` 连续失败阈值，避免长期异常时无限撞平台。
- 新增 CLI：
  - `scripts/run_creator_performance_scheduler.py`
  - 支持多个 `--creator-note-id` / `--run-id`。
  - 支持 `--schedule-interval-seconds`、`--max-rounds`、`--max-consecutive-failed-rounds`。
  - 支持 `--mode mock|spider_xhs`、`--wait`、`--limit`、`--attempts`、`--status-interval-seconds` 和 `--notes`。

验证结果：
- TDD RED：新增调度器服务和 CLI 测试先因模块/脚本缺失失败。
- 定点 RED->GREEN：`tests/test_creator_performance_scheduler.py tests/test_run_creator_performance_scheduler_script.py` -> `6 passed`。
- 相关回归通过：调度器、同步服务、同步脚本和平台状态 API 组合 -> `24 passed`。
- Python 编译检查通过：`D:\Anaconda\envs\ContentShare\python.exe -m compileall app scripts tests`。
- 全量测试通过：`D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` -> `269 passed`。

当前效果：
- 平台指标同步现在具备三层入口：工作台按钮、手动/短循环脚本、可长期运行的调度器脚本。
- 调度器具备连续失败停手，适合作为 Windows 计划任务、后台进程或后续 worker 编排的基础入口。
- 该能力仍保持真实平台只读，不扩大到公开发布、视频发布或平台定时发布。

当前限制：
- 调度器是脚本级常驻入口，不是完整任务编排平台；还没有统一 API/worker/watchdog/scheduler 的一键编排脚本。
- 没有接入告警通知，只在结构化结果里汇总失败轮次。
- 完整 BI、时间序列分析、M5 GraphRAG、M6 软广/达人仍未开始。

下一步建议：
- 如果继续收口工程化，可做统一启动编排脚本，把 API、SQLite worker、watchdog 和 performance scheduler 组合起来。
- 如果转主线，优先进入 M5 GraphRAG 前的数据入库/查询设计。

## 2026-06-13 平台指标批量同步、趋势摘要与工作台入口

本轮目标是在平台指标手动触发初版之后，继续解决遗留问题：补齐批量同步、安全的脚本循环同步、表现趋势摘要和工作台一键同步入口。真实公开发布、视频发布、定时发布、M5 GraphRAG、M6 软广/达人属于高风险或大模块，本轮未混入。

已完成：
- 扩展 `app/creator_performance_sync.py`：
  - 新增 `sync_creator_note_performance_batch()`，支持多个 `creator_note_id` / `run_id` 目标。
  - 单个目标失败不会中断批量任务，会在 `results` 中返回失败项和错误原因。
  - 新增 `summarize_performance_trends()`，从 operation memory 表现记录生成总量、均值、分数区间、高分内容和最近记录摘要。
- 扩展 API：
  - `POST /creator/notes/performance-sync/batch`
  - `GET /performance/trends?limit=...`
  - API 层仍只做参数解析，实际同步与趋势逻辑保留在服务模块。
- 扩展 CLI：
  - `scripts/sync_creator_note_performance.py` 支持多次传入 `--creator-note-id` 和 `--run-id`。
  - 新增 `--repeat-count` 和 `--repeat-interval-seconds`，作为手动脚本循环入口；不创建后台常驻定时服务。
- 扩展工作台：
  - 表现录入区新增 `performanceTrends` 趋势摘要。
  - 平台作品列表新增“同步表现”按钮。
  - 运营记忆中有 `creator_note_id` 的记录新增“同步表现”按钮。
  - 点击后调用 `/creator/notes/performance-sync`，从平台快照回填本地表现。

验证结果：
- TDD RED：新增测试先因批量服务、趋势函数、HTTP 路由、CLI 多目标/循环和工作台入口缺失失败。
- 定点 RED->GREEN：新增批量/趋势/前端入口测试组 -> `20 passed`。
- 相关回归通过：`tests/test_creator_performance_sync_service.py tests/test_api_platform_status.py tests/test_sync_creator_note_performance_script.py tests/test_workbench_creator_notes_static.py tests/test_creator_note_performance_sync.py` -> `33 passed`。
- JS 语法检查通过：`node --check app/static/app.js`。
- Python 编译检查通过：`D:\Anaconda\envs\ContentShare\python.exe -m compileall app scripts tests`。
- 浏览器工作台 smoke 通过：
  - 本地 mock API 使用 `http://127.0.0.1:8029`
  - `GET /performance/trends?limit=20` 返回 `ok=true` 和 `record_count=15`
  - 页面渲染 `表现趋势`、`高分内容`
  - 页面中可见 4 个同步表现按钮
- 全量测试通过：`D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` -> `263 passed`。
- 真实 creator 只读批量同步复验通过：
  - 使用隔离 SQLite `data/langgraph_private_publish_20260613.sqlite3`
  - 命令目标：`--run-id run_877b49f35f98` + `--creator-note-id 6a2d186a000000003503829c`
  - `total=2`
  - `succeeded=2`
  - `failed=0`
  - 两个目标都读到平台状态 `synced`，可见性 `仅自己可见`
  - 本地 `performance_result.business_sync.status=success`

当前效果：
- 平台指标同步已经从“单条手动触发”升级为：单条、批量、脚本循环、工作台按钮、趋势摘要。
- 脚本循环可以支持人工触发的短周期复查，但不会常驻后台，也不会绕过平台安全边界。
- 批量同步能容忍单条失败，适合真实平台只读巡检。

当前限制：
- 后台定时调度服务仍未做；如要做长期定时，需要单独设计 worker/队列和告警策略。
- 趋势分析是基于 operation memory 的轻量摘要，还不是完整 BI 或时间序列分析。
- 公开图文、视频发布、平台定时发布仍未实现，执行前必须重新确认真实写入风险。
- M5 GraphRAG 与 M6 软广/达人能力仍未开始。

下一步建议：
- 如果继续收口 M4，可优先做后台调度设计或工作台批量选择。
- 如果转主线，可进入 M5 GraphRAG 前的数据入库/查询设计。

## 2026-06-13 平台指标自动抓取初版

本轮目标是在用户更新 creator cookie 后，先确认真实只读访问是否恢复，再把“作品列表指标快照 -> /performance -> operation memory/run state/performance_records”做成模块化的手动触发能力。

已完成：
- 更新后 cookie 只读复验通过：
  - `scripts/check_creator_platform.py --mode spider_xhs --check-only` -> `ok=true`
  - `scripts/check_creator_platform.py --mode spider_xhs --list --limit 5` -> `source=creator_v2`
  - 最近作品列表可读到 `creator_note_id=6a2d186a000000003503829c` 和历史私密笔记。
- 定位旧闭环脚本失败根因：
  - `check_real_performance_closure.py` 默认查 `data/api_runs/<run_id>.json`
  - 最新 LangGraph-first 真实复验 run 实际保存在隔离 SQLite `data/langgraph_private_publish_20260613.sqlite3`
  - 失败不是 cookie 问题，而是旧脚本只适配 JSON run 文件。
- 新增模块化服务：
  - `app/creator_performance_sync.py`
  - 负责解析 `creator_note_id`、从 `run_id` 解析平台笔记 ID、校验 creator 状态、构造 performance payload。
  - 通过依赖注入接收 run loader、status reader、performance recorder，不直接绑定 HTTP、SQLite 或平台实现。
- 新增 API 薄入口：
  - `app.api.sync_creator_note_performance()`
  - `POST /creator/notes/performance-sync`
  - 支持 `creator_note_id` 或 `run_id`，并支持 `limit`、`wait`、`attempts`、`interval_seconds`、`notes`。
- 新增 CLI：
  - `scripts/sync_creator_note_performance.py`
  - 支持 `--creator-note-id` 或 `--run-id`
  - 支持 `--mode spider_xhs`、`--wait`、`--limit`、`--attempts`、`--interval-seconds`、`--notes`
- 新增测试：
  - `tests/test_creator_performance_sync_service.py`
  - `tests/test_sync_creator_note_performance_script.py`
  - 扩展 `tests/test_api_platform_status.py`

验证结果：
- TDD RED：新增测试先因 `app.creator_performance_sync` 和 `scripts.sync_creator_note_performance` 缺失失败。
- 定点测试通过：`tests/test_creator_performance_sync_service.py tests/test_api_platform_status.py::test_http_creator_note_performance_sync_endpoint_passes_parameters tests/test_sync_creator_note_performance_script.py` -> `8 passed`。
- 相关回归通过：自动抓取服务/API/CLI、`/performance` 反向同步、真实闭环工具和历史补偿组合 -> `27 passed`。
- 编译检查通过：`D:\Anaconda\envs\ContentShare\python.exe -m compileall app scripts tests`。
- 全量测试通过：`D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` -> `255 passed`。
- 真实只读自动抓取复验通过：
  - 使用隔离 SQLite `data/langgraph_private_publish_20260613.sqlite3`
  - 命令：`scripts/sync_creator_note_performance.py --run-id run_877b49f35f98 --mode spider_xhs --limit 50 --wait --attempts 3 --interval-seconds 1`
  - `synced=true`
  - `resolved_target.source=run_state`
  - `creator_note_id=6a2d186a000000003503829c`
  - `creator_note_status.status=synced`
  - `visibility_label=仅自己可见`
  - 平台指标快照仍为 0：`views=0`、`likes=0`、`collects=0`、`comments=0`
  - 本地回填成功：`performance_result.business_sync.status=success`
  - 业务表计数包含 `performance_records=1`

当前效果：
- M4 的“平台指标自动抓取”已有手动触发初版：可以从 creator 作品列表快照自动生成 `/performance` payload，并复用现有表现回填链路。
- 新入口支持 SQLite run store，不再依赖 JSON run 文件，因此可复验最新 LangGraph-first 隔离 DB run。
- 该能力只读访问真实平台，不触发发布、编辑、删除、公开或定时发布。

当前限制：
- 这还不是后台定时轮询或批量调度，只是手动触发的单条同步能力。
- 当前指标来源仍是 creator 作品列表返回的快照字段；如果平台未来拆分更详细的数据接口，还需要新增只读适配器。
- 公开视频、公开图文、定时发布仍未实现。
- M5 GraphRAG 入库和 M6 阶段二软广/达人能力仍未开始。

下一步建议：
- 可把该脚本纳入真实平台日常巡检：先按 `--run-id` 同步指定私密笔记，再查看业务表和运营记忆。
- 后续再评估是否做批量同步、后台定时任务、工作台按钮或指标趋势分析。

## 2026-06-13 LangGraph-first 真实私密发布端到端复验

本轮目标是在只读闭环复验通过后，执行一条低风险真实写入复验，确认 LangGraph-first 主路径能完成：`waiting_review -> 绑定真实图片 -> creator 私密发布 -> 作品列表只读同步 -> /performance 回填`。

执行环境：
- 启动专用本地 API：`http://127.0.0.1:8028`，执行结束后已停止进程。
- 使用隔离 SQLite DB：`data/langgraph_private_publish_20260613.sqlite3`。
- `COLLECTOR_MODE=mock`，`LLM_MODEL_NAME=mock`，避免额外真实采集和真实 LLM 干扰。
- `CREATOR_MODE=spider_xhs`，真实写入仅发生在 creator 私密发布步骤。
- 启用 SQLite run store、SQLite operation memory、foundation business tables。

执行结果：
- 平台状态预检通过：
  - `collector_runtime.ok=true`
  - `creator_runtime.ok=true`
  - `creator_publish_guardrail.allowed=true`
  - 发布前隔离 DB 内日计数 `0/3`
- 提交 LangGraph run：
  - `run_id=run_877b49f35f98`
  - `run_status=waiting_review`
  - `content_format=image_text`
  - `content_type=avoid_mistakes`
  - `compliance_risk_level=low`
- 绑定本地真实图片素材成功：
  - `creator_images_count=1`
  - 绑定文件：`data/creator_assets/run_877b49f35f98/01_langgraph_private_publish_cover.png`
- 审核通过并触发真实 creator 私密发布成功：
  - `creator_publish_status=success`
  - `creator_publish_mode=spider_xhs`
  - `creator_note_id=6a2d186a000000003503829c`
  - `operation_record_id=op_f680d04a3e7d`
- 只读作品状态等待成功：
  - `status=synced`
  - 标题：`小红书新手选题避坑方法先别急着判断，这几个坑要避开`
  - `visibility_label=仅自己可见`
  - `attempts=1`
  - 平台指标快照：曝光、点赞、收藏、评论均为 0。
- `/performance` 回填成功：
  - `record_id=op_f680d04a3e7d`
  - `status=performance_recorded`
  - `performance_score=0`
  - `business_sync.status=success`
  - `performance_records=1`
- 收口读取确认：
  - run 最终 `summary.run_status=published`
  - `publish_status=success`
  - `human_approved=true`
  - 业务表计数包含 `creator_assets=1`、`creator_notes=1`、`performance_records=1`、`audit_events=3`。
  - 发布后隔离 DB 内 guardrail 计数为 `1/3`。

当前限制：
- 本次仍是私密图文，不是公开发布、视频发布或定时发布。
- 本次使用 mock 采集和 mock LLM，验证重点是 LangGraph-first 审核恢复、图片绑定、真实 creator 私密发布、只读状态同步和表现回填链路。
- 平台指标为 0 是当前快照结果，不代表回填链路失败。
- 生成的 SQLite DB、图片素材和 Markdown 草稿均为本地忽略文件，不进入 Git。

下一步建议：
- 把本次复验结果作为 M4 私密图文真实主链稳定性的最新基线。
- 后续主线转向平台指标自动抓取、公开图文/视频/定时发布评估，或进入 M5 GraphRAG 前的查询/入库准备。

## 2026-06-13 项目记忆收口与真实闭环预检

本轮目标是在列出未完成任务后，开始按优先级收口：先校准项目记忆，再准备真实 Cookie 小流量复验前的只读闭环检查。

已完成：
- 更新 `AGENTS.md`，把固定回复前缀校准为 `锋宝：`。
- 校准 `AGENTS.md` 中已滞后的阶段描述：
  - `human_review` 已升级为 LangGraph interrupt/resume。
  - M25 平台安全护栏已完成。
  - M26 发布状态等待已完成。
  - 默认运行时已收敛为 LangGraph-first。
  - 最新验证状态更新为全量测试 `247 passed`。
- 提交项目记忆更新：
  - `29d190d docs: refresh xhs project memory`
- 运行轻量验证：
  - `git diff --check` 通过。
  - `tests/test_api_langgraph_resume.py` 通过：`4 passed`。
- 运行 `scripts/check_runtime_config.py --profile local` 通过，提示本地 API token 为空，符合当前本地开发状态。
- 尝试运行只读真实表现闭环工具：
  - `scripts/check_real_performance_closure.py --run-id run_fda76a64a278 --creator-note-id 6a2bce0b000000003502c564 --limit 50 --use-platform-metrics`
  - 本地 run state、operation memory 和 `performance_records` 同步检查通过。
  - `business_sync.status=success`，业务表快照包含 `performance_records=1`。

当前阻塞：
- 沙箱网络代理指向 `127.0.0.1:9`，导致第一次 creator 作品列表只读请求无法访问真实平台，`platform_note_found=false`。
- 用户明确授权非沙箱网络后，已重跑同一条只读检查，结果为 `ok=true`、`platform_note_found=true`。

当前影响：
- 本地表现闭环工具链可用，真实 creator 作品列表只读匹配也已完成最新复验。
- 生成的临时 SQLite 文件位于 `data/` 下，并被 `.gitignore` 忽略，不会进入版本提交。

下一步建议：
- 下一步进入 LangGraph-first 小流量端到端复验：`waiting_review -> 绑定真实图片 -> creator 私密发布 -> 作品列表只读同步 -> /performance 回填`。
- 该步骤会触发真实 creator 私密发布，执行前需要单独确认写入平台权限。

## 2026-06-11 creator 发布状态只读同步

本轮目标是在真实 creator v2 作品列表和表现回填烟测之后，补上只读发布状态同步能力。

已完成：
- 新增 `platforms.creator.get_published_note_status()`，可按 `creator_note_id` 从 creator v2 作品列表中匹配平台笔记并归一化状态。
- 状态同步复用 creator v2 作品列表，不触发发布、修改、公开、删除或重试。
- 状态结果包含 `synced` / `not_found` / `unavailable`、可见性提示、权限字段和指标快照。
- 新增 `app.api.get_creator_note_status()` 和只读 `GET /creator/notes/status?creator_note_id=...` 路由。
- 工作台作品列表展示平台状态摘要和浏览/赞/藏/评快照，同时保持点击作品填入 `creator_note_id` 的行为。

已验证：
- `tests/test_creator_platform.py`、`tests/test_creator_note_performance_sync.py`、`tests/test_workbench_creator_notes_static.py` 聚焦测试通过。
- 全量测试通过：`127 passed`。
- `compileall app nodes routers platforms memory scripts llm` 通过。
- `node --check app/static/app.js` 通过。
- 真实只读状态同步可找到 `creator_note_id=6a2abffc0000000022027f7a`，返回 `status=synced`、标题 `M25 私密发布链路验证`、`visibility_label=仅自己可见`，当前指标快照均为 0。

当前限制：
- 本轮不是后台自动轮询，不写回主运营记忆。
- 表现数据仍需通过现有人工表现录入入口写入。
- 普通沙箱网络会被代理拦截，真实 creator 只读验证需要提权执行；这不影响本地 mock/单元测试。

## 2026-06-11 真实 creator_note_id 表现回填烟测

本轮目标是在 creator v2 作品列表同步修复后，继续验证真实 `creator_note_id` 是否能走通“作品列表 -> 表现回填”的本地闭环。

已验证：
- 当前主运营记忆中没有 `creator_note_id=6a2abffc0000000022027f7a` 的记录，因为这条真实私密发布是适配层小流量验证，不是通过完整 run 审核链路产生的记录。
- 使用真实 creator v2 作品列表只读同步，能找到目标笔记：
  - `creator_note_id=6a2abffc0000000022027f7a`
  - 标题：`M25 私密发布链路验证`
- 在系统临时目录创建临时运营记忆文件，登记同一个真实 `creator_note_id` 后调用 `record_performance()`，可按平台笔记 ID 匹配并更新记录。
- 烟测结果为 `status=performance_recorded`，`performance_data={views:0, likes:0, collects:0, comments:0, follows:0}`，`performance_score=0`。
- 表现分为 0 是因为当前平台返回该私密笔记指标均为 0，不是回填链路失败。

当前判断：
- M21 的 `creator_note_id` 表现回填能力对真实平台 ID 可用。
- 若希望主运营记忆中长期保留这条真实笔记，需要后续通过完整 run 审核发布链路生成记录，或明确允许把本次适配层小流量验证登记为一条运营记忆记录。
- 下一步可以继续进入主要链路后续任务；优先建议补发布状态轮询或主链路真实 run 发布验证，二者都属于 M4 真实平台端到端的后半段。

## 2026-06-11 creator 作品列表 v2 同步修复

本轮目标是在真实私密发布成功后，继续排查 creator 作品列表同步失败，恢复“平台作品列表 -> creator_note_id -> 表现回填”的只读链路。

已完成：
- 参考了 `D:\codex\project\小红书内容分享\referrence\Spider_XHS-master`，确认参考版 Spider_XHS 的 creator 列表实现仍使用旧 `/api/galaxy/creator/note/user/posted`，不能直接解决当前真实平台列表失败。
- 从 creator 前端 JS 确认当前真实页面使用 `GET /api/galaxy/v2/creator/note/user/posted`，参数为 `tab=1`、`page=0` 起，响应中的 `page=-1` 表示没有下一页。
- `platforms/creator.py` 的真实作品列表读取改为优先使用 creator v2 接口，旧 vendor 列表接口仅作为兜底，避免旧接口空正文导致成功结果后仍打印 JSONDecode traceback。
- 兼容 v2 响应字段：`id`、`displayTitle` / `display_title`、`type`，并继续归一化为 `note_id`、`title`、`visibility`。
- 作品列表返回的 `raw` 已复用现有敏感字段脱敏工具，避免 `xsec_token`、cookie 等字段暴露到脚本输出或工作台 API。
- 新增 creator 平台测试覆盖 v2 优先、旧接口失败后的 v2 路径、v2 字段归一化和 raw 脱敏。

已验证：
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py -q` 通过，当前该文件 14 个测试全部通过。
- `D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode spider_xhs --list --limit 5` 通过，返回 `source=creator_v2`。
- 真实作品列表已包含刚发布的私密笔记 `creator_note_id=6a2abffc0000000022027f7a`，标题为 `M25 私密发布链路验证`，并显示 `permission_msg=仅自己可见`。
- 同一次真实列表输出中 `xsec_token` 已显示为 `<redacted>`，没有再输出原始 token。

当前限制：
- 作品列表同步仍是只读能力，不自动抓取表现指标，不做发布状态轮询。
- 旧 vendor 接口仅保留兜底，后续如果 Spider_XHS 更新，可再评估是否收敛实现。
- 下一步可用真实 `creator_note_id` 做表现回填验证，然后继续进入主要链路后续任务。

## 2026-06-11 真实平台小流量验证记录

本轮目标是在 M25 平台安全护栏完成后，先做真实平台小流量验证。当前只执行只读采集验证，没有执行 creator 真实写入。

已验证：
- 工作树干净，M20-M25 两个提交已落地。
- `scripts/check_runtime_config.py --profile local` 通过：核心模块可导入、日志目录可写、run store 为 JSON、run queue 为 local；仅提示本地 API token 为空。
- `scripts/check_collector.py` 预检通过：`.env` 存在、PC Cookie 存在、vendor 路径存在、`XHS_Apis` 可导入。
- `scripts/check_creator_platform.py --mode spider_xhs --check-only` 未通过：缺少 `XHS_CREATOR_COOKIES`，因此没有执行真实 creator 私密发布。
- 真实只读搜索通过：主题 `小红书新手选题方法`，limit=1，返回 1 条脱敏笔记。
- 真实评论读取通过：对 1 条笔记读取 10 条评论，保留 1 条、过滤 9 条，并生成 1 条 comment insight / pain point。
- 首次未提权执行真实搜索时失败，原因是沙箱代理指向 `127.0.0.1:9`；提权后网络链路正常。

暴露问题：
- 保留的 1 条评论仍明显像“提升成长地方/无偿分享/看下面进4”这类引流噪声，说明评论噪声过滤还需补充规则。
- creator 真实链路目前缺少 `XHS_CREATOR_COOKIES`，只能完成预检失败确认，不能做真实私密发布验证。

下一步建议：
1. 补充评论噪声过滤规则，覆盖“优秀上进的伙伴们、无偿分享、位置不多、自行把握、看下面进”等引流表达。
2. 配置 `XHS_CREATOR_COOKIES` 后，再执行 1 条 creator 私密图文发布小流量验证。
3. 私密发布验证成功后，同步作品列表，确认真实 `creator_note_id` 能用于表现回填。

补充进展：
- 已补充评论噪声过滤规则，新增覆盖“优秀上进的伙伴、提升成长的地方、小红书项目礼物、无偿分享位置不多、自行把握、看下面进”等引流表达。
- 新增 `tests/test_comment_noise_filtering.py`，锁定真实引流样本不再进入 fallback insight。
- 复测真实只读采集：搜索和评论读取仍可执行；本次返回 1 条笔记、0 条评论，最终走主题级默认痛点兜底。
- 再次脱敏检查确认：当前 `实施/xhs-agent/.env`、上级 `.env` 和系统环境中仍没有 `XHS_CREATOR_COOKIES` / `CREATOR_COOKIES`，因此 creator 真实私密发布继续阻塞，尚未执行写入验证。
- 已验证：全量测试 `119 passed`，compileall 通过，`node --check app/static/app.js` 通过。
- 之后发现 creator Cookie 被误写入可提交模板 `.env.example`，已将其移入本地 `.env` 的 `XHS_CREATOR_COOKIES`，并清理 `.env.example`，未提交 Cookie。
- creator 真实模式预检通过：`check_creator_platform.py --mode spider_xhs --check-only` 返回 `ok=true`。
- 已执行 1 条真实 creator 私密图文发布验证，使用本地 JPEG 素材，返回 `mode=spider_xhs`、`visibility=private`、`note_id=6a2abffc0000000022027f7a`。
- M25 本地护栏文件 `data/platform_guardrails.json` 已记录当日 `success_count=1`、`stopped=false`。
- creator 作品列表同步验证未通过：`check_creator_platform.py --mode spider_xhs --list --limit 5` 返回 HTML 404 导致 JSON 解析失败，发布成功但列表同步入口需要后续排查 Spider_XHS creator 列表接口。

## 2026-06-11 M25 平台安全护栏补齐

本轮目标是在 M20-M24 已经打通 creator 私密发布、图片素材绑定、作品同步、表现回填和失败诊断后，回到从0手册主线，补齐真实平台操作前的最小安全护栏。本轮不扩大公开发布、视频发布、定时发布，也不进入 GraphRAG。

已完成：
- 新增 `platforms/platform_guardrails.py`，记录真实 creator 发布当日成功次数、同日停手原因和发布前随机延时。
- creator 真实 `spider_xhs` 发布前会先执行 runtime 自检、当日发布许可检查和随机延时。
- creator 真实发布成功后会累计当日成功次数。
- creator 真实发布 `success=False` 或异常后会记录停手原因，阻止同日后续连续发布。
- creator 日发布限制默认 `3`，并在代码层限制为个位数最大 `9`。
- 新增 collector runtime 自检：mock 直接通过，`spider_xhs` 模式检查 PC Cookie 和 Spider_XHS API 导入能力。
- 统一 collector 入口在 `spider_xhs` 模式下会先执行 runtime 自检，避免缺 Cookie 时半路失败。
- `.env.example` 新增 M25 护栏配置：`XHS_PLATFORM_GUARDRAIL_PATH`、`XHS_CREATOR_DAILY_LIMIT`、`XHS_CREATOR_MIN_DELAY_SECONDS`、`XHS_CREATOR_MAX_DELAY_SECONDS`。
- 新增 `tests/test_platform_safety_guardrails.py`，覆盖当日发布限制、失败停手、creator Cookie 前置自检、发布前延时和 collector Cookie 自检。
- 新增中文设计与计划文档：
  - `docs/superpowers/specs/2026-06-11-platform-safety-guardrails-design.md`
  - `docs/superpowers/plans/2026-06-11-platform-safety-guardrails.md`

当前限制：
- 停手状态是本地 JSON 护栏，不是平台端状态轮询。
- 停手按自然日隔离，下一日自动进入新日期计数。
- Cookie 自检只确认本地配置和导入能力，不发真实登录态探测请求；真实 Cookie 是否已过期仍需后续真实小流量验证。
- 真实发布状态轮询、公开发布、视频发布和定时发布仍未完成。

用户自测建议：
1. mock 模式下运行全量测试，确认本地链路不受护栏影响。
2. 真实采集前配置 `COLLECTOR_MODE=spider_xhs` 和 `XHS_COOKIES_PC`，先运行采集检查脚本。
3. 真实 creator 私密发布前配置 `CREATOR_MODE=spider_xhs` 和 `XHS_CREATOR_COOKIES`。
4. 保持 `XHS_CREATOR_DAILY_LIMIT=3` 或更低，先只做 1 条私密发布验证。
5. 如果出现 `success=False`、风控或异常，先查看 `data/platform_guardrails.json` 和 run 失败诊断，不要连续重试。

## 2026-06-11 M24 结构化失败分类

本轮目标是在 M23 工作台运行诊断的基础上，把失败诊断从前端文本判断升级为后端结构化字段，让 API、运行记录和前端共用同一套失败分类。

已完成：
- 后端新增结构化失败分类字段：`failure_category` 和 `failure_category_label`。
- 顶层 run 失败会根据 `error` 生成失败分类。
- summary 会在 creator publish 失败或高风险合规结果时生成失败分类。
- `/runs` 列表和 `/runs/{run_id}` 详情会对旧记录做响应时补齐，不强制迁移历史 JSON/SQLite 数据。
- 工作台 `diagnoseRunFailure()` 优先使用后端 `failure_category_label`，旧文本关键词判断只保留为兼容兜底。
- 新增 `tests/test_run_failure_category.py`，覆盖分类规则、新 run 写入、summary 写入和旧记录补齐。
- 更新 `tests/test_workbench_run_diagnostics_static.py`，确保前端使用后端分类字段。
- 新增中文实施计划：`docs/superpowers/plans/2026-06-11-structured-failure-category.md`。

当前分类：
- `creator_publish`：创作者平台或发布素材问题。
- `llm_generation`：LLM 生成或解析问题。
- `collection`：采集或 Cookie 问题。
- `compliance`：合规拦截。
- `unknown`：未分类失败，请查看错误详情。
- `null`：没有失败。

当前限制：
- M24 只做结构化失败分类，不做完整链路日志追踪。
- 不做队列级自动重试，也不做真实 creator 发布重试。
- 分类仍基于当前错误文本和状态字段，不是全节点事件审计。

用户自测建议：
1. 启动本地 API 并打开工作台。
2. 点击一条失败或 creator publish failed 的运行记录。
3. 查看“运行诊断”中的失败分类。
4. 如需确认 API 字段，可打开 JSON 标签页查看 `failure_category` 与 `failure_category_label`。
5. 旧记录也应能显示兜底分类，不需要手动迁移历史 run 文件。

## 2026-06-11 M23 工作台运行历史详情与失败诊断

本轮目标是在 M22 已经把运营闭环状态展示清楚后，继续补工作台可用性：让用户点击运行记录后，不必翻 JSON，也能直接看到该任务的请求参数、时间、状态、失败诊断和错误详情，并能用同一组任务参数重新提交一个新 run。

已完成：
- 任务结果区新增“运行诊断”面板，展示任务状态、主题、目标用户、形式、引擎、采集数量、创建时间、更新时间和任务 ID。
- 失败任务会根据错误文本做最小分类提示：创作者平台或发布素材问题、LLM 生成或解析问题、采集或 Cookie 问题、合规拦截，无法分类时提示查看错误详情。
- 诊断面板展示错误详情，优先读取 run error，也兼容 creator publish 错误字段。
- 新增“用此任务参数重新提交”按钮，复用当前 run 的 request 参数调用现有 `POST /runs` 创建新任务，并自动切换到新任务轮询。
- 新增 `tests/test_workbench_run_diagnostics_static.py`，覆盖诊断容器、失败分类、重新提交 payload 和响应式样式契约。
- 新增中文实施计划：`docs/superpowers/plans/2026-06-11-workbench-run-diagnostics.md`。

当前限制：
- M23 只做“复制参数重新提交”，不是队列级自动重试；不会复用原 run ID，也不会恢复原任务内部状态。
- 不做 creator 发布失败的真实平台重试，避免误触发写入类平台操作。
- 失败分类是基于错误文本的最小提示，不替代完整日志和链路追踪。

用户自测建议：
1. 启动本地 API 并打开工作台。
2. 点击任意一条运行记录。
3. 在任务结果区查看“运行诊断”，确认能看到请求参数和运行时间。
4. 如果该任务失败，确认能看到失败分类和错误详情。
5. 点击“用此任务参数重新提交”，确认生成一个新任务并开始轮询。

## 2026-06-11 M22 工作台闭环可视化

本轮目标是在 M20/M21 已经打通“图片绑定 -> 私密发布 -> 作品列表 -> 表现回填”的基础上，把闭环关键状态直接显示在工作台运营记忆列表中，减少用户查找 `creator_note_id` 和确认表现录入状态的成本。本轮不新增真实平台写入行为、不做发布重试、不自动抓取表现指标。

已完成：
- 运营记忆卡片新增创作发布状态、平台笔记 ID、表现状态和表现分的紧凑展示。
- 运营记忆卡片展示已录入的表现数据摘要：曝光、点赞、收藏、评论和关注。
- 运营记忆卡片新增“用这条记录录入表现”按钮，点击后自动把该记录的 `post_id` 和 `creator_note_id` 填入表现录入表单。
- 新增 `tests/test_workbench_memory_visibility_static.py`，覆盖运营记忆状态展示、快捷填表行为和响应式样式契约。

当前限制：
- M22 只做工作台可视化和快捷填表，不自动同步平台表现数据。
- 如果某条运营记忆没有 `creator_note_id`，快捷填表只会填入本地 `post_id`。
- 真实平台发布失败后的重试、状态刷新和定时提醒仍后置。

用户自测建议：
1. 启动本地 API 并打开工作台。
2. 完成一条图文 run 的图片绑定和创作者平台私密发布，让运营记忆中产生 `creator_note_id`。
3. 查看“运营记忆”列表，确认能直接看到“创作发布”“平台笔记”“表现状态”“表现分”。
4. 点击该卡片里的“用这条记录录入表现”。
5. 确认“表现录入”表单自动填入 `post_id` 和 `creator_note_id`。
6. 填入表现数据并点击“录入表现”，确认运营记忆卡片刷新为已录入状态且表现分更新。

## 2026-06-11 M21 作品列表同步后的表现数据回填入口

本轮目标是在 M19/M20 已经具备 creator 发布和图片素材绑定后，补上“平台作品列表 -> 表现录入”的最小闭环。当前不自动抓取点赞/收藏/评论等表现数据，只让用户从作品列表选择 `creator_note_id`，再人工录入表现。

已完成：
- 新增 `GET /creator/notes?limit=20`，复用 `platforms.creator.list_published_notes()` 返回 mock 或真实 creator 作品列表。
- `POST /performance` 支持 `creator_note_id`，现在可以按本地 `post_id` 或平台 `creator_note_id` 查找运营记忆记录并更新表现数据。
- `memory.operation_store.update_record_performance()` 支持 `creator_note_id` 查找，同时保持原有 `post_id` 路径优先。
- 工作台表现录入区新增 `creator_note_id` 输入框和“同步作品列表”按钮。
- 同步出的作品列表可点击，点击后自动填入表现录入表单的 `creator_note_id`。
- 新增 `tests/test_creator_note_performance_sync.py`，覆盖作品列表 API、按 `creator_note_id` 录表现、缺少标识时报错。
- 新增 `tests/test_workbench_creator_notes_static.py`，覆盖前端同步入口、作品渲染和表现 payload 契约。

当前限制：
- 作品列表同步只返回平台已有字段，不自动抓取表现指标。
- 表现数据仍需人工录入曝光、点赞、收藏、评论和关注。
- `creator_note_id` 必须已经写入某条运营记忆，才能用它回填表现；否则后端会提示找不到对应记录。

用户自测建议：
1. 先用 mock creator 发布一条图文 run，让运营记忆里产生 `creator_note_id`。
2. 到工作台“表现录入”区点击“同步作品列表”。
3. 点击同步出来的一条作品，确认 `creator_note_id` 自动填入。
4. 填入曝光、点赞、收藏、评论、关注。
5. 点击“录入表现”，确认提示更新成功。
6. 在运营记忆列表中确认该记录状态变为 `performance_recorded`，表现分不再是 0。

## 2026-06-11 M20 真实图片素材输入/选择链路

本轮目标是在不引入新 Web 框架、不做图片生成和排版的前提下，让已生成的图文 run 可以绑定真实本地图片素材，并在审核勾选“同时私密发布到创作者平台”时，把真实图片 bytes 交给 creator adapter。

已完成：
- 新增 run 级图片素材绑定能力：`POST /runs/{run_id}/creator-assets` 接收浏览器传来的 base64 图片 JSON。
- 后端会校验图片数量、base64 内容和图片魔数，只接受 PNG/JPG/GIF/BMP/WebP 等有效图片 bytes。
- 图片文件保存到 `data/creator_assets/<run_id>/`，run JSON 里只保存文件路径、图片数量和更新时间，避免把图片 bytes 直接塞进 run state。
- 审核触发 creator publish 时，后端会优先读取已绑定图片文件并传入 `publish_private_image_text()`。
- 工作台审核区新增图片选择框和“绑定发布图片”按钮；绑定成功后摘要区展示“发布图片”数量。
- 绑定入口只在成功生成、待审核、图文内容时可用；视频和已审核 run 不支持绑定。
- 新增 `tests/test_creator_asset_binding.py` 覆盖后端绑定、真实模式发布读取 bytes、非法图片拒绝。
- 新增 `tests/test_workbench_creator_assets_static.py` 覆盖前端入口、payload 契约和摘要展示。

当前限制：
- M20 只解决真实素材输入/选择，不生成图片、不做多图排版、不做封面图渲染。
- 仍只支持图文私密发布；视频发布、公开发布、定时发布、失败重试继续后置。
- 工作台通过浏览器文件选择上传图片内容；没有做素材库管理、删除、重排和预览。

用户自测建议：
1. 启动本地 API。
2. 打开工作台并提交一个图文 run。
3. run 成功后，在审核区选择 1 张或多张本地 PNG/JPG/WebP 图片。
4. 点击“绑定发布图片”，确认摘要区“发布图片”数量变为对应数量。
5. 勾选“同时私密发布到创作者平台”。
6. 点击“审核通过并保存”。
7. mock 模式下确认“创作发布”为成功，并出现平台笔记 ID。
8. 真实 `spider_xhs` 模式下，先配置 creator Cookie，再重复以上步骤；如果失败，预期不应再是缺少 `image bytes`。

## 2026-06-11 M19c 工作台创作者平台发布入口

本轮目标是把 M19b 已完成的审核后私密发布能力接到工作台前端，让用户在审核区显式勾选后，才请求创作者平台私密发布。

已完成：
- 工作台审核区新增“同时私密发布到创作者平台”勾选项，默认不勾选，不改变原有本地保存 Markdown 和写入运营记忆行为。
- 勾选后点击“审核通过并保存”会向后端发送 `creator_publish=true`、`creator_publish_private=true`、`creator_human_confirmed=true`。
- 未勾选时，审核通过 payload 仍只执行原有本地审核保存链路。
- 摘要区新增创作发布状态展示：未请求、成功、失败。
- 摘要区新增平台笔记 ID 展示，后端返回 `creator_note_id` 时可直接看到。
- 审核提示区会展示后端已经脱敏的 `creator_publish_error`，便于确认创作者平台发布失败原因。
- 新增 `tests/test_workbench_creator_publish_static.py`，覆盖前端入口、payload 条件和展示契约。

当前限制：
- 真实 `spider_xhs` 私密发布仍要求 run state 内有真实图片字节；当前工作台还没有图片素材上传或选择入口。
- 暂不支持视频发布、公开发布、定时发布和失败重试。
- 当前测试是静态契约测试，尚未额外跑浏览器 UI smoke。

建议下一步：
1. 进入真实图片素材输入/选择链路，让 `spider_xhs` 私密图文发布具备真实素材来源。
2. 或先补作品列表同步后的表现数据回填入口，为后续复盘闭环做准备。

## 2026-06-11 M19b 审核通过后私密发布接入

本轮目标是在不改变前端默认行为的前提下，把创作者平台私密发布接入审核 API。默认审核仍只保存本地 Markdown 和写入运营记忆；只有审批请求显式带 `creator_publish=true`、`creator_publish_private=true`、`creator_human_confirmed=true` 时，才触发创作者平台私密发布。

已完成：
- `approve_run()` 支持显式 creator publish 参数。
- 默认审核不调用创作者平台，保持本地 Markdown 草稿保存和运营记忆写入行为。
- mock 模式私密发布结果会回填 `creator_note_id`、`creator_publish_mode` 和 `creator_publish_status`。
- 视频内容请求 creator publish 时会保存本地草稿，但 creator publish 标记为失败且不调用适配器。
- 创作者平台异常不会抹掉本地草稿保存结果，运营记忆仍会写入失败状态。
- 运营记忆记录 creator publish 元数据：请求状态、发布状态、模式、note ID 和脱敏后的错误。
- 真实 `spider_xhs` 模式要求有效图片字节；缺图片、非 bytes 占位和假 bytes 会在调用真实适配器前失败。
- creator publish 错误进入 run summary、state 和 operation memory 前会做基础脱敏，避免 cookie、token、authorization、password、api key 等值直接落盘。
- 新增 Windows pytest 临时目录权限兼容处理，将测试临时目录切到 `data/pytest_tmp_safe`，并只在该目录范围内放宽 pytest 的 `0o700` mkdir 模式。

已验证：
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_creator_review_publish.py -q` 通过，12 个审核发布测试全部通过。
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py -q` 通过，11 个创作者平台测试全部通过。
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` 通过，当前 82 个测试全部通过。
- 规格复核通过：M19b Tasks 1-4 符合设计。
- 代码质量复核通过：真实模式假图片字节、错误脱敏和 pytest Windows 临时目录补丁问题均已修复。

当前限制：
- 前端暂未新增“同时私密发布到创作者平台”的勾选项；目前需要直接调用审批 API 参数触发。
- 真实 `spider_xhs` 发布还需要 run state 里有真实图片字节，当前主链路尚未生成或选择实际图片素材。
- 暂不支持视频、公开发布、定时发布和失败重试。

建议下一步：
1. 进入 M19c：前端增加“同时私密发布到创作者平台”的明确勾选项，并展示 creator 发布状态。
2. 或先补真实图片字节生成/选择链路，让 `spider_xhs` 真实私密发布具备素材输入。
3. 公开发布、视频发布、蒲公英和千帆继续后置。

## 2026-06-11 M19a 创作者平台连接：私密发布与作品列表基础适配

本轮目标是在不自动公开发布、不引入新平台流程的前提下，先把小红书创作者平台连接封装成低风险适配层：默认 mock，自测可运行；真实 `spider_xhs` 模式必须显式提供创作者 Cookie，且当前只开放私密图文发布和作品列表读取入口。

已完成：
- 新增 `platforms/creator.py`，集中封装创作者平台适配逻辑，支持 `mock` 与 `spider_xhs` 两种模式。
- 新增 `publish_private_image_text()`，仅允许私密图文草稿/私密笔记发布，并要求 `human_confirmed=True` 作为写入类操作硬门槛。
- 新增 `list_published_notes()`，用于作品列表同步的基础读取，返回统一的 `note_id`、`title`、`visibility` 和原始数据。
- 新增 `check_creator_runtime()`，用于在真实平台模式下预检 `XHS_CREATOR_COOKIES`、vendor 目录、`NODE_PATH` 和创作者 API 导入能力。
- 新增 `scripts/check_creator_platform.py`，提供命令行自测入口：`--check-only`、`--publish-private`、`--list`。
- 新增 `tests/test_creator_platform.py`，覆盖 mock 发布、人工确认门槛、图片数量限制、真实模式缺 Cookie 保护、真实模式导入错误暴露、mock 列表同步和脚本退出码。
- 更新 `.env.example`，补充 `CREATOR_MODE` 和 `XHS_CREATOR_COOKIES`。
- 新增 `docs/m19a-creator-platform-connection.md`，说明 mock 自测、真实平台预检、私密发布边界和当前限制。

已验证：
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py -q` 通过，10 个创作者平台测试全部通过。
- `D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode mock --publish-private --human-confirmed` 通过，返回 mock 私密笔记 ID。
- `D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode mock --list --limit 2` 通过，返回 2 条 mock 作品记录。
- `D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode spider_xhs --check-only` 在未配置 `XHS_CREATOR_COOKIES` 时按预期退出 1，并提示必须提供 Cookie。
- 使用临时 `XHS_CREATOR_COOKIES=a1=fake` 执行 `--mode spider_xhs --check-only` 通过，确认当前 `ContentShare` 环境可以导入 Spider_XHS 创作者 API；该检查不发发布请求。
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` 通过，当前 69 个测试全部通过。
- `D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm` 通过。

当前阶段判断：
- 当前系统已经从“只能生成内容并人工发布”推进到“具备创作者平台连接的基础封装和低风险自测入口”。
- 真实平台写入仍受到人工确认、Cookie 预检和私密发布边界限制，暂不做自动公开发布。
- 这一步还没有接入主工作流，生成内容后不会自动调用创作者平台发布；当前只是先把平台边界和自测能力做出来。

尚未完成：
- 主链路中的人工审核通过后，自动调用私密发布适配器。
- 发布结果回填到 run、运营记忆和作品表现记录。
- 图片上传、视频上传和真实素材路径管理的完整验证。
- 公开发布、定时发布、失败重试、发布状态轮询。
- 蒲公英、千帆等其他小红书生态平台的数据连接。

建议下一步：
1. 进入 M19b：把 M19a 适配器接入现有审核/运行结果链路，但仍保持私密发布和人工确认。
2. 发布成功后，把 `note_id`、发布时间、发布模式写回 run store 与运营记忆。
3. 暂不处理公开发布和其他平台，等私密发布闭环稳定后再扩展。

## 2026-06-11 M17b 启动模板与部署清单

本轮目标是在不引入 Docker、Nginx、systemd、Redis 或新进程管理器的前提下，把当前 API/worker 的启动方式固化为可重复执行的 Windows/PowerShell 模板，并明确使用 `ContentShare` Python 环境。

已完成：
- 新增 `scripts/start_local_api.ps1`，用于本地开发模式启动 API，默认 `COLLECTOR_MODE=mock`、`LLM_MODEL_NAME=mock`、`XHS_AGENT_RUN_QUEUE=local`。
- 新增 `scripts/start_sqlite_api.ps1`，用于 SQLite 分进程模式启动 API，统一设置 run store、run queue、operation memory 到同一个 SQLite DB 路径。
- 新增 `scripts/start_sqlite_worker.ps1`，用于 SQLite 分进程模式启动 worker，支持 `-Once` 单步处理。
- 三个启动模板都支持 `-CheckOnly`，可只运行配置检查，不启动长时间运行进程。
- 三个启动模板都按顺序选择 Python：`-Python` 参数、`XHS_AGENT_PYTHON`、`D:\Anaconda\envs\ContentShare\python.exe`、最后才回退到裸 `python`。
- 新增 `docs/m17b-startup-templates.md`，说明本地模式、SQLite 分进程模式、带 token 模式、production-lite preflight、日志位置和当前限制。
- 新增 `tests/test_startup_templates.py`，覆盖启动模板存在性、`CheckOnly` 支持、`ContentShare` Python 选择逻辑提示和 SQLite DB 路径一致性要求。
- 新增设计与计划文档：
  - `docs/superpowers/specs/2026-06-11-startup-templates-design.md`
  - `docs/superpowers/plans/2026-06-11-startup-templates.md`

已验证：
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_startup_templates.py -q` 通过，3 个启动模板测试通过。
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_local_api.ps1 -CheckOnly -Python D:\Anaconda\envs\ContentShare\python.exe` 通过，local profile 检查退出 0。
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_sqlite_api.ps1 -CheckOnly -Python D:\Anaconda\envs\ContentShare\python.exe` 通过，sqlite-worker profile 检查退出 0。
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_sqlite_worker.ps1 -CheckOnly -Python D:\Anaconda\envs\ContentShare\python.exe` 通过，sqlite-worker profile 检查退出 0。
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` 通过，当前 59 个测试全部通过。
- `D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm` 通过。

当前阶段判断：
- 当前 API/worker 已有可重复启动模板，后续自测不必再手动复制大量环境变量。
- 本轮仍不等于完整生产部署；公网部署前仍需要 HTTPS、反向代理、进程守护、备份、账号权限和更完整的密钥治理。

建议下一步：
1. 如继续工程主线，进入 M18：更高并发队列能力评估和 Redis/RQ 或 Celery 的取舍。
2. 如继续产品功能主线，进入 M19：创作者平台私密发布和作品列表同步的低风险验证。
3. 规则泛化和硬编码问题已记录，暂不阻塞当前主功能推进。

## 2026-06-11 后续待处理：规则泛化与硬编码问题记录

本轮只记录问题，不立即进入修复。当前优先级仍是继续推进主要工程功能；内容审核、评论洞察、模板 fallback 和跨领域记忆过滤的泛化问题，后续按阶段逐步改善。

已确认的后续问题：
- 合规规则仍偏单层，当前主要覆盖健康/母婴与小红书增长承诺；法律、金融、教育、职场、医美、减肥等主题还没有独立风险分层。
- `config/compliance_rules.json` 中已配置 `avoid_promise_words`，但 `nodes/compliance_node.py` 当前审核流程没有实际拦截 `爆款`、`必火`、`暴涨`、`快速涨粉` 等过度承诺词。
- 全局 `safety_note` 目前是健康类提示，如果后续直接扩展金融/法律等敏感主题，可能出现提示语错配，需要改成按领域匹配。
- `memory/operation_store.py` 的跨领域污染过滤目前只针对健康护理旧记录，不是通用领域隔离机制。
- `config/comment_insight_rules.json` 已有通用规则和 `baby_skin_care` 领域组，但领域覆盖仍窄，后续需要逐步补法律、金融、教育、职场、医美、内容创作等高频主题规则。
- 图文和视频 fallback 模板仍有较多“小红书运营/知识分享/内容创作”默认表达；真实 LLM 路径影响较小，但 mock 或 LLM 失败时会带偏输出。

后续建议：
1. 先继续主功能开发，不让这些细节阻塞当前工程主线。
2. 后续单独开一轮规则治理，把合规规则改成多领域规则组，并补充对应测试。
3. 再逐步处理模板 fallback、评论洞察领域扩展和历史记忆跨领域复用边界。

## 2026-06-11 M17a 最小生产护栏

本轮目标是在不引入 Docker、Nginx、systemd、Redis 或新 Web 框架的前提下，给当前 API/worker 增加最小生产护栏。

已完成：
- API token 鉴权支持，默认本地开发关闭，设置 `XHS_AGENT_API_TOKEN` 后保护 `/runs`、`/queue`、审核、表现录入和记忆查询等非公开 API。
- `/health`、`/`、`/static/*` 和 `OPTIONS` 保持公开，便于健康检查、页面加载和 CORS preflight。
- 修复静态目录公开边界，避免 `/static/../static_evil/...` 这类 sibling 目录被误判为公开静态资源。
- API 与 worker 增加日志落盘，默认写入 `data/logs/api.log` 和 `data/logs/worker.log`。
- 增加敏感字段脱敏工具，避免 token、cookie、api key、authorization、password 等值进入结构化日志。
- API access log 不再记录 query string 和 fragment，避免 URL 参数泄露。
- 新增 `scripts/check_runtime_config.py`，支持 `local`、`sqlite-worker`、`production-lite` 三种配置检查。
- 自检脚本使用唯一临时探针检查目录可写性，不会覆盖或删除已有 `.write_check` 文件。
- `scripts/check_api_run.py` 支持 `--api-token`，可验证带鉴权的 API。
- `.env.example` 补充 API token 和日志配置。
- 新增 `docs/m17a-production-guardrails.md`，说明本地、带鉴权模式、运行配置检查和日志位置。

已验证：
- `python -m pytest -q` 通过，当前 56 个测试全部通过。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- `python .\scripts\check_runtime_config.py --profile local` 通过，输出 `WARN api token empty: auth disabled`。
- `python .\scripts\check_runtime_config.py --profile production-lite` 在 token 为空时按预期退出 1，并输出 `FAIL production-lite requires XHS_AGENT_API_TOKEN`。
- 带 `XHS_AGENT_API_TOKEN=test-token` 的 API 烟测通过：未带 token 的 `POST /runs` 返回 `401`，带 `--api-token test-token` 的 `check_api_run.py` 能完成 mock LangGraph run，并从 `queued/running` 变为 `success`。

验证环境说明：
- 当前工具默认 `python` 指向 `D:\Anaconda\python.exe`，该环境没有直接安装 `langgraph`。
- `requirements.txt` 已声明 `langgraph==1.2.1`，`D:\Anaconda\envs\ContentShare\python.exe` 可以导入 `langgraph`。
- 本轮最终测试使用 `PYTHONPATH=D:\Anaconda\envs\ContentShare\Lib\site-packages` 让当前工具默认 Python 读取 ContentShare 依赖后通过。用户在已激活 `(ContentShare)` 的终端里执行时不需要额外设置该 `PYTHONPATH`。
- Windows 下 pytest 临时目录偶尔会残留不可访问 ACL；本轮已清理 `data\pytest_tmp` 和 M17a 临时 SQLite/pytest 文件。

当前阶段判断：
- 当前系统仍不是完整生产部署，但已经具备最小 server-facing 护栏：鉴权、日志、脱敏、自检和带 token 烟测。
- 仅设置 `XHS_AGENT_API_TOKEN` 不等于可以直接公网暴露；真正对公网部署前仍需要 HTTPS、反向代理、进程守护、备份、账号体系和更完整的密钥治理。

建议下一步：
1. M17b：补进程启动模板和部署清单，继续保持不引入重型新组件。
2. M18：需要更高并发时再进入 Redis/RQ 或 Celery。
3. M19：基础部署稳定后，再推进小红书创作者平台私密发布和作品列表同步。

## 2026-06-11 M16b API / worker 启动与自测说明

本轮目标是把 M16a 已经实现的 SQLite 队列和独立 worker 入口整理成可操作说明，避免后续只停留在“代码能跑”，但用户不知道如何分别启动 API 和 worker。

已完成：
- 新增 `docs/m16b-api-worker-startup.md`。
- 区分默认本地模式和 SQLite 分进程模式。
- 写明 cmd 与 PowerShell 两套环境变量写法，避免在 cmd 里误用 `$env:...`。
- 写明 API 进程和 worker 进程必须使用同一组 SQLite DB 路径。
- 补充 `/queue` 队列状态检查命令。
- 说明 `run_worker.py --once` 没有任务时返回非零退出码是预期行为。
- 补充常见问题：任务一直 queued、worker 未设置 SQLite 队列、真实采集 Cookie 要求。
- 补充 pytest 临时目录权限残留的清理方式。

已验证：
- `python .\scripts\run_api.py --help` 通过。
- `python .\scripts\run_worker.py --help` 通过。
- `python .\scripts\check_api_run.py --help` 通过。
- `python -m pytest tests/test_sqlite_queue_worker_integration.py -q` 通过。
- `python -m pytest -q` 通过，当前 27 个测试全部通过。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- 使用临时 SQLite DB 启动 API 进程和 worker 进程，`check_api_run.py --engine langgraph` 提交任务后从 `queued` 变为 `success`。

当前阶段判断：
- 本地开发可以继续用默认 `local` 队列。
- 需要验证 API/worker 分进程时，使用 `XHS_AGENT_RUN_QUEUE=sqlite` 并分别启动 API 和 worker。
- 工程链路调试优先使用 `COLLECTOR_MODE=mock` 与 `LLM_MODEL_NAME=mock`，避免真实采集和真实 LLM 干扰基础链路判断。

建议下一步：
1. M17：补生产部署准备，包括日志落盘、进程守护、基础鉴权和敏感配置治理。
2. M19：等基础部署能力稳定后，再进入创作者平台私密发布和小红书生态扩展。

## 2026-06-11 M16a SQLite 持久化运行队列与 worker 入口

本轮目标是在不引入 Redis/RQ/Celery 的前提下，把运行队列从 API 进程内存迁移到 SQLite，并新增独立 worker 脚本，为后续 API/worker 进程拆分铺路。

已完成：
- 新增 `SQLiteRunQueue`，通过 `run_queue_jobs` 表持久化队列任务。
- 保留 `LocalRunQueue` 默认行为，只有设置 `XHS_AGENT_RUN_QUEUE=sqlite` 时启用 SQLite 队列。
- API 提交流程仍创建 `queued` run，再写入队列；SQLite 队列模式下 API 不启动后端 worker 线程。
- 新增 `scripts/run_worker.py`，支持 worker 从 SQLite 队列领取任务并调用现有 `_execute_run(run_id)`。
- 队列支持入队去重、领取锁、成功完成、失败重试、终态失败和过期锁重新领取。
- `.env.example` 新增 SQLite 队列相关配置。
- 新增 `pytest.ini`，将 pytest 收集范围固定到 `tests`，并把临时目录放到已忽略的 `data/pytest_tmp`，避免 Windows 用户临时目录权限残留影响测试。

已验证：
- SQLite 队列单元测试通过。
- API 队列后端选择测试通过。
- worker 单步执行测试通过。
- SQLite 队列 + SQLite run store + mock LangGraph 集成测试通过。
- `python -m pytest -q` 通过。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。

当前阶段判断：
- API 和 worker 已具备分进程运行基础。
- SQLite 队列适合当前本地和轻量部署阶段。
- Redis/RQ/Celery、部署守护、鉴权、取消任务和前端队列管理仍不在本轮范围内。
- 当前环境已验证 `langgraph` 可用，M16a 集成烟测使用 `engine=langgraph` 验证队列/worker 链路。

建议下一步：
1. M16b：补启动说明和自测命令，明确 API 进程与 worker 进程如何分别启动。
2. M17：进入生产部署准备，补日志、进程守护和基础鉴权。
3. M18：在需要更高并发时再替换为 Redis/RQ 或 Celery。
4. M19：小红书生态平台连接扩展，先评估创作者平台私密发布和作品列表同步，再调研蒲公英/千帆数据价值。

## 2026-06-11 M19 规划补充：小红书生态平台连接扩展

本轮只补规划，不实现平台写入能力。`Spider_XHS技术路线分析.md` 显示 Spider_XHS 除 PC 端只读采集外，还包含创作者平台、蒲公英和千帆等小红书生态入口。当前系统实际完成的是 PC 端搜索、笔记详情和评论采集，尚未接入创作者平台发布、蒲公英达人数据或千帆分销数据。

已写入路线图：
- 创作者平台登录状态和 Cookie 管理。
- 创作者平台私密发布测试。
- 图文/视频上传能力封装。
- 已发布作品列表同步。
- 发布状态回填到 run 和运营记忆。
- 蒲公英达人/KOL 数据调研。
- 千帆分销/商品数据调研。
- 写入类操作必须保留人工确认硬门槛。

当前阶段判断：
- 这部分能力可以让系统从“生成草稿 + 人工发布”逐步升级到“半自动发布 + 发布后回填”。
- 自动公开发布涉及平台风控和账号安全，不应作为第一步。
- 最稳顺序是先做创作者平台私密发布和作品列表同步；蒲公英、千帆先做业务价值调研。

建议顺序：
1. M16b：先完成 API/worker 启动说明和自测流程。
2. M17：补部署、安全、日志和基础鉴权。
3. M19：进入小红书生态平台连接扩展，先做低风险私密发布验证。

## 2026-06-10 M15 运营记忆 SQLite 后端

本轮目标是在保留 `memory/operation_history.json` 默认行为的前提下，给运营记忆增加 SQLite 可切换后端，为后续数据库化和 API/worker 拆分继续铺路。

已完成：
- 新增 `memory.operation_store` 内部后端边界：
  - `JsonOperationMemoryBackend`
  - `SQLiteOperationMemoryBackend`
  - `_memory_backend()`
  - `operation_memory_path()`
- `load_history()`、`save_history()`、`upsert_record_from_state()`、`find_relevant_records()`、`find_successful_patterns()`、`update_record_performance()` 保持公开函数 API 不变，默认调用会根据环境变量选择后端。
- 新增 SQLite 表 `operation_records`，完整记录保存在 `record_json`，同时保留 `topic`、`post_id`、`content_type`、`performance_score`、`created_at`、`updated_at` 等索引字段。
- 新增环境变量：
  - `XHS_AGENT_MEMORY_STORE=json|sqlite`
  - `XHS_AGENT_MEMORY_DB_PATH=data/xhs_agent.sqlite3`
- 更新 `nodes/memory_node.py`、`app/api.py`、`scripts/record_performance.py`，展示当前选中后端的记忆路径。
- 新增 `tests/test_operation_store_sqlite.py`，覆盖 SQLite 运营记忆写入、更新、检索、成功模式提取、表现录入和跨领域健康污染过滤。

已验证：
- `python -m pytest -q` 通过，当前 14 个测试全部通过。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- 使用临时 SQLite DB 的运营记忆烟测通过：
  - 写入一条 operation record。
  - 能按主题检索到相关记录。
  - 能录入表现数据并更新为 `performance_recorded`。
- 临时测试 DB 已清理。

当前阶段判断：
- M14 RunStore SQLite 可切换后端已完成。
- M15 Operation Memory SQLite 可切换后端已完成。
- 默认行为仍是 JSON，只有显式设置环境变量时才启用 SQLite。
- 还没有做历史 JSON 自动迁移；后续如需要，应单独实现迁移脚本并做数据校验。

建议下一步：
1. M16：设计并接入真正的外部队列后端，优先评估 Redis/RQ 与现有 `LocalRunQueue` 的接口差异。
2. M17：拆分 API 进程和 worker 进程，让耗时采集/LLM 任务从 API 服务中移出。
3. M18：补数据库迁移脚本，把 `data/api_runs/*.json` 和 `memory/operation_history.json` 可控迁移到 SQLite。

## 2026-06-10 M9 配置治理

本轮目标是修正节点里业务规则和提示词硬编码的问题，让后续迭代优先改配置，而不是反复进入节点代码。

已完成：
- 新增 `app/rules.py`，统一读取 `config/*.json` 业务规则。
- 新增 `config/content_structures.json`，承载内容结构、图文页规划、标题模板等规则。
- 新增 `config/compliance_rules.json`，承载绝对词、敏感主题、免责声明词、安全提示和承诺类禁用词。
- 新增 `config/strategy_rules.json`，承载内容策略判断关键词和默认策略。
- 新增 `config/comment_insight_rules.json`，承载评论痛点归类规则。
- 新增 `config/text_replacements.json`，承载风险词替换规则。
- 新增 `config/performance_rules.json`，承载表现分权重。
- 新增 `config/llm_prompts.json`，承载图文生成、视频脚本生成、运营复盘的系统提示词、用户提示词模板和 expected JSON。
- 新增 `llm/prompts.py`，负责把外置提示词模板渲染成 `ChatMessage`。
- 改造 `content_node.py`、`video_node.py`、`review_node.py`，节点只组织业务输入，不再直接拼大段 LLM prompt。
- 改造 `compliance_node.py`、`strategy_node.py`、`pattern_utils.py`、`comment_analysis.py`、`operation_store.py`、`review_node.py`，规则来源改为配置文件。
- 修复 `publish_node.py` 中输出目录依赖当前工作目录的问题，改为项目根目录下的 `output/markdown_exports`。
- 修复 `publish_node.py` 中 `state.get("body" or "")` 的错误写法。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- `llm.prompts.build_json_prompt()` 能正确加载并渲染外置提示词。
- mock 模式下图文 LangGraph 主流程通过。
- mock 模式下视频 LangGraph 主流程通过。

当前阶段判断：
- M9A 业务规则配置化：完成。
- M9B LLM 提示词配置化：完成基础版。
- 当前仍不是生产部署完成态，下一阶段应处理任务状态、人审流程、存储可靠性和部署安全。

建议下一步：
1. M10：把现在的 `--approve` 假人工确认，升级为真实的前端人审状态流。
2. M11：把 JSON 文件读写加锁、原子写入和异常恢复做扎实。
3. M12：补前端失败任务展示、运行记录详情、表现录入后的记忆刷新。
4. M13：整理部署配置，包括生产 `.env`、日志、进程守护、启动脚本和反向代理。

## 2026-06-10 M10 人工审核入口

本轮目标是让工作台支持“先生成待审草稿，再人工审核通过或驳回”，不再只能靠提交任务时的 `approve` 参数决定是否保存。

已完成：
- `app/api.py` 的 run 记录开始保存完整 `state`，用于后续审核动作继续执行发布、复盘和写运营记忆。
- 新增 `approve_run(run_id, payload)`：
  - 只允许对已经生成成功的 run 操作。
  - 高合规风险内容不能直接通过。
  - 审核通过后调用 `publish_or_schedule()` 保存 Markdown。
  - 随后调用 `review_performance()` 生成复盘摘要。
  - 最后调用 `write_operation_memory()` 写入运营记忆。
- 新增 `reject_run(run_id, payload)`：
  - 审核驳回后设置 `publish_status=rejected`。
  - 不保存 Markdown。
  - 不写运营记忆。
- 新增 HTTP 接口：
  - `POST /runs/{run_id}/approve`
  - `POST /runs/{run_id}/reject`
- 前端工作台新增审核区：
  - `审核通过并保存`
  - `审核不通过`
  - 显示待审、已保存、已驳回、高风险不可直接通过等状态。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- `node --check app/static/app.js` 通过。
- 函数级审核通过链路通过：`pending -> success`，并触发运营记忆字段。
- 函数级审核驳回链路通过：`pending -> rejected`，不写运营记忆。
- 临时 mock API 服务下，桌面端 Playwright 工作台提交链路通过，无 console error。
- 临时 mock API 服务下，移动端 Playwright 工作台检查通过，无 console error。

当前阶段判断：
- M9 配置治理：完成基础版。
- M10 人工审核入口：完成基础版。
- 当前人审仍是 API 层继续执行，不是 LangGraph 原生 interrupt/resume；这对当前 MVP 足够，但生产级人审可以后续再升级。

建议下一步：
1. M11：增强 JSON 存储可靠性，重点是原子写入、损坏备份、运行记录和运营记忆的文件锁。
2. M12：优化前端运行记录详情、失败任务展示、审核反馈输入框、表现录入后的记忆刷新体验。
3. M13：进入部署准备，整理 `.env.example`、启动脚本、日志落盘、进程守护和反向代理。

## 2026-06-10 M11 本地存储可靠性

本轮目标是降低 JSON 文件在断电、进程中断或并发写入时损坏的风险。

已完成：
- 新增 `app/json_store.py`：
  - `write_json_atomic()`：先写同目录临时文件，刷新到磁盘，再用 `os.replace()` 原子替换目标文件。
  - `write_text_atomic()`：给 Markdown 等文本产物复用同样的原子写入机制。
  - `read_json_file()`：读取 JSON 时校验根类型。
  - `move_corrupt_file()`：发现损坏 JSON 或根类型不符合预期时，移入同目录 `corrupt/` 备份目录。
- 改造 `app/api.py`：
  - `data/api_runs/*.json` 改为原子写入。
  - 读取 run JSON 时发现损坏文件会隔离到 `data/api_runs/corrupt/`。
- 改造 `memory/operation_store.py`：
  - `operation_history.json` 改为原子写入。
  - 新增 `HISTORY_LOCK`，保护运营记忆的读改写流程。
  - 损坏的运营记忆文件会隔离到 `memory/corrupt/`。
- 改造 `platforms/spider_xhs_collector.py`：
  - 采集快照 `data/collector_runs/*.json` 改为原子写入。
- 改造 `nodes/publish_node.py`：
  - Markdown 草稿保存改为原子写入。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- 存储工具正常写入、读取、损坏 JSON 自动隔离通过。
- 临时 API run 目录下，mock LangGraph run 保存和读取通过。
- 临时 operation history 文件下，新增记录和录入表现数据通过。
- 临时 mock API 服务下，工作台提交链路通过，无 console error。

当前阶段判断：
- M11 本地存储可靠性：完成基础版。
- 当前锁是单进程内线程锁，适合现在的单 API 进程和单 worker 队列。
- 如果未来多进程部署，需要升级到数据库、Redis 队列，或引入跨进程文件锁。

建议下一步：
1. M12：优化前端可用性，重点是失败任务详情、审核反馈输入框、运行记录详情、表现录入后的自动刷新。
2. M13：部署准备，补 `.env.example`、启动脚本、日志落盘和进程守护。

## 2026-06-10 M14 高并发改造第一步：队列和存储边界拆分

本轮目标不是立刻接入 Redis/PostgreSQL，而是先把 `app/api.py` 中耦合在一起的 HTTP、run 存储、队列、worker 逻辑拆出可替换边界。这样后续替换成 Redis 队列、Celery worker、PostgreSQL 存储时，不需要重写整个 API 层。

已完成：
- 新增 `app/run_store.py`：
  - `LocalRunStore` 封装 `data/api_runs/*.json` 的保存、读取、列表查询。
  - 当前仍使用本地 JSON 文件，但 API 层不再直接关心文件读写细节。
  - 后续可替换为 `PostgresRunStore`。
- 新增 `app/run_queue.py`：
  - `LocalRunQueue` 封装入队、pending 恢复、worker 启动、队列状态。
  - 当前仍是本进程内队列，但 API 层不再直接持有 `Queue`、worker 线程和去重集合。
  - 后续可替换为 Redis/Celery/RQ。
- 改造 `app/api.py`：
  - `_save_run()`、`_load_run()`、`_list_runs()` 改为委托 `LocalRunStore`。
  - `_enqueue_run()`、`_recover_pending_runs()`、`queue_status()` 改为委托 `LocalRunQueue`。
  - 移除 API 层直接管理 `RUN_QUEUE`、`QUEUE_LOCK`、`ENQUEUED_RUN_IDS`、`WORKER_STARTED` 的逻辑。
- 新增环境变量：
  - `XHS_AGENT_LOCAL_WORKERS`
  - 默认值为 `1`。
  - 本地模式可临时调高 worker 数，但这仍不是最终生产级高并发方案。
- `GET /queue` 返回中新增：
  - `worker_backend`
  - `worker_count`

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- 函数级 mock run 保存和读取通过。
- `queue_status()` 正常返回队列状态。
- `XHS_AGENT_LOCAL_WORKERS=3` 时，`queue_status()` 能看到 `worker_count=3`。
- 临时 mock API 服务下，工作台提交链路通过，无 console error。

当前阶段判断：
- 高并发改造的第一步完成：边界拆出来了。
- 当前仍不是生产级高并发，因为任务状态仍在本地 JSON，队列仍在单进程内存。
- 下一步必须进入真正的外部基础设施：Redis 队列和 PostgreSQL 存储。

建议下一步：
1. M15：设计并落地数据库模型，先用 SQLite/PostgreSQL 兼容方式替换 run 存储。
2. M16：引入 Redis 队列或 Celery/RQ，替换 `LocalRunQueue`。
3. M17：把 API 进程和 worker 进程拆开，支持多 worker 横向扩容。

## 2026-06-10 M14.5 评论洞察泛化修复

本轮目标是修复真实测试中暴露出的内容质量问题：主题为“小红书新手选题方法”时，评论洞察错误输出“对护理方法存在疑问，担心建议不靠谱”。

问题原因：
- 原 `config/comment_insight_rules.json` 中的 6 条规则全部来自“宝宝湿疹护理”场景。
- 规则关键词中包含“真的可以”“步骤”“流程”“靠谱吗”等通用词，导致非健康主题也被归到护理痛点。
- 采集评论中存在大量互粉、数字、引流、炫耀收入类噪声，影响痛点提取。

已完成：
- 重构 `config/comment_insight_rules.json`：
  - 新增 `generic_insight_rules`，用于通用主题。
  - 新增 `domain_rule_groups`，只有主题命中领域关键词时才启用专用规则。
  - 将宝宝湿疹相关规则放入 `baby_skin_care` 领域组。
  - 新增 `noise_comment_keywords` 和 `low_value_comments`。
- 改造 `platforms/comment_analysis.py`：
  - 根据 topic 选择通用规则和领域专用规则。
  - 支持 `pain_template`，让痛点文案绑定当前主题。
  - 增加评论噪声过滤。
  - 避免同一条评论重复作为多条 insight 的证据。
  - 无匹配时仍回退到主题级通用痛点。
- 改造 `nodes/content_node.py`：
  - 非健康主题的兜底模板不再固定输出“不替代诊断”。
  - 只有敏感健康上下文才使用诊断边界提示。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- “小红书新手选题方法”样本输出：
  - 对主题是否真实可行存在怀疑，需要可信案例和边界说明。
  - 不知道从哪里开始，需要清晰的入门步骤。
  - 担心投入成本或试错风险，需要避坑提醒。
- “宝宝湿疹护理”样本仍能输出：
  - 分不清湿疹、热疹、过敏等相似皮肤问题。
  - 担心是否需要用药、擦药或就医处理。
- 使用真实 run `run_03aaaf930533` 的 raw_comments 回放后，不再出现护理痛点污染。
- mock 图文主流程通过。
- 非健康主题兜底正文不再包含“不替代诊断”。

当前阶段判断：
- 评论洞察从“单领域规则”升级为“通用规则 + 领域规则”基础版。
- 这仍然是规则系统，不是最终智能分类；后续可以引入 LLM/embedding 做评论聚类和主题适配。

建议下一步：
1. 用真实采集再跑一次“小红书新手选题方法”，确认新洞察能带动生成内容变好。
2. 继续补通用评论洞察规则，尤其是学习、职场、电商、母婴、内容创作等高频领域。
3. 稳定后再回到高并发主线：数据库模型和 Redis 队列。

## 2026-06-10 M14.6 内容记忆污染修复

本轮目标是修复真实 API 测试中继续出现的跨领域内容污染：主题为“小红书新手选题方法”时，结果里仍然出现“对护理方法存在疑问，担心建议不靠谱”等健康护理类痛点。

问题判断：
- 当前代码层面的评论洞察规则已经修复，但正在运行的 API 服务不会热更新，需要重启后才会加载新代码。
- `memory/operation_history.json` 中存在历史脏记录，旧的“小红书新手选题方法”记录里已经写入了护理类痛点和标题。
- 这些历史记录会通过 `retrieved_memory` 和 `successful_patterns` 被重新喂给生成链路，导致新内容继续被旧记忆污染。

已完成：
- 在 `memory/operation_store.py` 增加跨领域健康污染过滤。
  - 非健康主题检索历史记忆时，如果记录中含有湿疹、热疹、擦药、用药、就医、诊断、护理方法等健康领域残留，会跳过该记录。
  - 健康主题本身不受影响，例如“宝宝湿疹护理”仍然可以读取健康护理相关历史。
- 新增 `scripts/repair_operation_memory.py`。
  - 默认 dry-run，只报告将修复哪些记录。
  - 使用 `--apply` 时会先备份 `operation_history.json`，再写入修复后的历史记忆。
- 已执行一次修复：
  - 修复 6 条“小红书新手选题方法”历史记录。
  - 备份文件：`memory/operation_history.json.backup_20260610_160400`。
  - 修复后 dry-run 显示 `changed_records_count: 0`。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- 评论样本“真的可以做到吗？需要干货...”现在输出：
  - `对「小红书新手选题方法」是否真实可行存在怀疑，需要可信案例和边界说明`
- `find_successful_patterns("小红书新手选题方法")` 不再返回护理类痛点。
- `find_successful_patterns("宝宝湿疹护理")` 仍能返回健康护理主题记录。

下一步：
1. 重启正在运行的 API 服务，否则 `127.0.0.1:8010` 仍可能使用旧代码。
2. 重新运行 `scripts/check_api_run.py`，确认返回结果中的 `insights.pain_points` 不再出现护理类表达。
3. 如果内容质量稳定，再回到高并发主线，继续推进数据库模型和外部队列。

## 2026-06-10 M14.7 内容结构与安全替换修复

本轮目标是处理真实 LLM 输出中的两个新问题：
- `content_type` 显示为 `avoid_mistakes`，但正文实际是步骤教程，摘要与内容结构不一致。
- 安全替换把“不要保证/一定”等表达替坏，出现“不尽量你照做就建议有结果”这类病句。

问题判断：
- `strategy_node` 会先根据痛点命中“避坑”，得到 `avoid_mistakes`。
- `pattern_utils.structure_profile()` 会优先复用高表现历史结构，实际生成时使用了 `step_tutorial`。
- 图文/视频生成节点之前没有把实际使用的结构类型回写到 state，导致最终摘要仍显示旧的策略类型。
- `text_replacements.json` 只有单词级替换，例如 `保证 -> 尽量`、`一定 -> 建议`，破坏了“不保证你照做就一定有结果”的句子结构。

已完成：
- 更新 `config/text_replacements.json`：
  - 新增 `phrase_replacements`，先处理完整短语。
  - 将“不保证你照做就一定有结果”修正为“不是说照做就会直接出结果”。
  - 调整部分单词兜底替换，降低病句概率。
- 更新 `nodes/content_node.py`：
  - 安全替换顺序改为：短语替换 -> 绝对词替换 -> 质量词替换。
  - LLM 图文结果和模板图文结果都会回写实际 `content_type`。
- 更新 `nodes/video_node.py`：
  - 同步使用短语优先的安全替换。
  - LLM 视频结果和模板视频结果都会回写实际 `content_type`。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- 替换样本：
  - 输入：`这篇不保证你照做就一定有结果，但能帮你避开一定会踩的坑。`
  - 输出：`这篇不是说照做就会直接出结果，但能帮你避开可能会踩的坑。`
- mock LangGraph 主流程通过。
- mock 结果中 `content_type` 已变为 `step_tutorial`，与步骤正文一致。

下一步：
1. 重启 API 服务。
2. 用真实 LLM 再跑一次“小红书新手选题方法”，重点检查正文最后一段是否仍有病句。
3. 如果内容质量稳定，再继续高并发主线。

## 2026-06-10 M14.8 采集噪声与中文空格清洗

本轮目标是处理 cookie 恢复后真实采集暴露出的两个小问题：
- `raw_comments` 中仍保留“互粉、回复 1、加粉”等噪声评论。
- LLM 正文偶尔出现“再 处理”这类中文词中间异常空格。

已完成：
- 更新 `platforms/comment_analysis.py`：
  - 将噪声评论判断暴露为 `is_noise_comment_text()`。
  - 噪声关键词匹配改为压缩空白后判断，避免换行和空格绕过过滤。
- 更新 `platforms/spider_xhs_collector.py`：
  - 采集层复用评论洞察层的噪声判断，避免两套过滤标准不一致。
- 更新 `nodes/content_node.py` 和 `nodes/video_node.py`：
  - 生成文本清洗阶段移除中文字符之间的异常空格。
  - 保留数字与中文之间的正常空格，例如 `30 篇`、`5-10 个`。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- “不够1000人的告诉我 / 让我们成为彼此的粉丝”会被判定为噪声。
- “1”会被判定为噪声。
- “真的可以做到吗？需要干货”会保留。
- “第三步：再 处理。”会被清洗为“第三步：再处理。”。

下一步：
1. 重启 API 服务。
2. 重新跑真实采集，确认 `raw_comments_count` 会下降，但 `comment_insights_count` 仍能稳定保持。
3. 如果采集质量稳定，再回到高并发主线。

补充修复：
- 真实测试中仍发现少量中文异常空格，例如“不匹配 、无法”“一开始 就”“新手穿搭  小个子通勤”。
- 已收紧中文空格清洗规则：
  - 保留段落换行。
  - 删除中文之间的单个异常空格。
  - 删除标点前后的异常空格。
  - 两段中文之间的两个以上空格转成中文逗号，避免直接粘成病句。
  - 保留数字与单位之间的正常空格，例如 `30 篇`、`5-10 个`。
- 已验证：
  - `不匹配 、无法` -> `不匹配、无法`
  - `一开始 就` -> `一开始就`
  - `新手穿搭  小个子通勤` -> `新手穿搭，小个子通勤`

## 2026-06-10 M14.9 可信表达收敛

本轮目标是处理真实 LLM 输出中的“虚构背书”和“过度承诺”表达。

问题表现：
- 标题中出现 `实测可行`、`照着做就行`、`刷了100篇才懂`、`直接抄作业`、`少走半年弯路`。
- 这些表达虽然不一定触发合规风险，但会降低内容可信度；在没有真实输入证据时，不能让模型伪装成已有个人经历或明确承诺结果。

已完成：
- 更新 `config/text_replacements.json`：
  - `照着做就行` -> `可以照着步骤先试`
  - `直接抄作业` -> `可以参考这个步骤`
  - `亲测有效` -> `有参考价值`
  - `实测可行/实测可用` -> `可以按步骤验证`
  - `刷了100篇才懂` -> `看了很多案例后整理`
  - `少走半年弯路` -> `少走一些弯路`
  - `瞎找` -> `盲目找`
- 更新 `config/llm_prompts.json`：
  - 图文和视频系统提示中加入：不要虚构个人经历、验证次数、收益结果或亲测背书。
  - 无输入证据时禁止写 `亲测`、`实测`、`刷了100篇`、`少走半年弯路`、`照着做就行`、`直接抄作业`。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- 安全替换样本通过：
  - `实测可行｜...` -> `可以按步骤验证｜...`
  - `照着做就行` -> `可以照着步骤先试`
  - `刷了100篇才懂` -> `看了很多案例后整理`
  - `直接抄作业` -> `可以参考这个步骤`
- LLM prompt 可正常加载，系统提示已包含“不要虚构个人经历”。

下一步：
1. 重启 API 服务。
2. 再跑一次真实 LLM 测试，确认标题不再出现虚构背书和强承诺表达。
3. 若通过，内容质量修复阶段可以收尾，回到高并发主线。

## 2026-06-10 全局进度与工程路线图整理

已新增 `memory/project_status_and_roadmap.md`，用于记录：
- 当前项目总体目标。
- 已完成的主链路能力。
- 当前系统架构。
- 期待的生产级工程形态。
- 尚未实现的关键环节。
- 后续优先级排序。

该文件是后续 `/resume` 或重新进入项目时的全局上下文入口；`current_progress.md` 继续用于记录每轮小步变更。

## 2026-06-11 主链真实采集 + LangGraph 验证

本轮目标是把验证重心从 mock 和前端补洞拉回主链：真实 PC 采集、LangGraph 编排、真实 LLM、日志落盘。

执行过程：
- 先检查 `.env`：`COLLECTOR_MODE=spider_xhs`，`LLM_MODEL_NAME=deepseek-v4-pro`，`LLM_BASE_URL=https://api.deepseek.com`，PC Cookie 和 creator Cookie 均已存在。
- 发现旧 8010 API 进程实际继承了 mock 环境变量，导致 run 虽然成功但 `llm_generation.error=LLM is in mock mode`，采集结果也是 mock 样本。
- 在 8012 用显式真实环境变量启动 API 后，确认不再回到 mock，但普通沙箱网络会把外部请求导向 `127.0.0.1:9`，导致小红书和 DeepSeek 都出现 `ProxyError`。
- 按权限规则提权后，在 8013 启动真实网络 API，重新提交同一条 LangGraph 主链。

真实主链验证结果：
- API：`http://127.0.0.1:8013`
- run：`run_c91c97a1d502`
- 状态：`success`
- 引擎：`langgraph`
- 采集：`raw_notes_count=1`，`raw_comments_count=9`，`comment_fetch_errors_count=0`
- 评论洞察：`comment_insights_count=1`，`pain_points_count=1`
- 运营记忆召回：`retrieved_memory_count=5`
- LLM：`enabled=true`，`provider_mode=openai_compatible`，`model=deepseek-v4-pro`
- token：`prompt_tokens=987`，`completion_tokens=2328`，`total_tokens=3315`
- 合规：`compliance_risk_level=low`
- 首条真实笔记标题：`新人起号靠的不是日更而是关键词`
- 生成首标题：`小红书选题先别急着判断，这几个坑要避开`
- 日志：`data/logs/api.log` 已记录 8013 启动和 `run_c91c97a1d502` 轮询请求。

额外发现：
- `scripts/check_api_run.py` 在 Windows GBK 控制台打印包含 `⭐` 的 JSON 时会触发 `UnicodeEncodeError`。主链本身已成功，后续建议单独修复该脚本的输出编码，避免真实结果包含 emoji 时误报命令失败。
- 后续验证真实网络链路时，应优先使用非沙箱网络启动 API；普通沙箱只适合 mock 或本地接口验证。

下一步建议：
1. 旧的 8010/8012 API 进程已停止，目前只保留 8013 真实网络实例，防止误连到 mock 或沙箱网络实例。
2. 修复 `scripts/check_api_run.py` 的 Windows 输出编码问题。
3. 基于 8013 继续做“审核通过保存草稿 -> 人工确认 -> 私密发布/表现回填”的主链后半段验证。

## 2026-06-11 check_api_run Windows 输出编码修复

本轮目标是修复 `scripts/check_api_run.py` 在 Windows GBK 控制台打印真实 run JSON 时，遇到 emoji 等非 GBK 字符会抛出 `UnicodeEncodeError` 的问题。

已完成：
- 在 `tests/test_check_api_run_auth.py` 增加回归测试，模拟 `encoding="gbk"`、`errors="strict"` 的 stdout，打印包含 `⭐` 的 JSON。
- 在 `scripts/check_api_run.py` 增加 `_print_line()`，脚本输出优先按原文本写出；如果 stdout 编码不支持某些字符，则用 `backslashreplace` 转义不可编码字符，避免脚本崩溃。
- 将脚本内直接 `print()` 的地方切换为 `_print_line()`，覆盖提交状态、轮询状态、错误文本和最终 JSON。

已验证：
- RED：新增测试在旧实现下复现 `UnicodeEncodeError`。
- GREEN：`D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_check_api_run_auth.py::test_print_json_handles_gbk_stdout_with_emoji -q` 通过。
- 相关测试：`D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_check_api_run_auth.py -q`，4 passed。
- 编译：`D:\Anaconda\envs\ContentShare\python.exe -m compileall scripts\check_api_run.py` 通过。

当前仍需注意：
- 真实小红书和真实 LLM 验证需要非沙箱网络，否则会出现 `127.0.0.1:9` 代理失败。
- 8013 是当前保留的真实网络 API 实例；不要误连旧的 8010/8012。
- 下一步主链后半段建议继续验证：审核保存草稿 -> 私密发布/状态同步 -> 表现回填。

## 2026-06-11 采集策略与后续 RAG 基础记录

讨论结论：
- 数据采集不应简单选择评论数、点赞数、收藏数最多的笔记。
- 高互动指标应作为重要排序因子，但不是唯一标准。
- 后续更适合作为 RAG 基础的采集策略是“高相关 + 高质量互动”候选池。

建议采集逻辑：
1. 搜索关键词后先形成候选池，例如前 20-50 篇。
2. 先按主题相关度过滤偏题笔记。
3. 再综合评论数、点赞数、收藏数、近期程度、账号体量等指标排序。
4. 对前 5-10 篇抓评论。
5. 评论层过滤互粉、引流、水军、抽奖、低价值情绪噪声。
6. 最终把“真实问题密度高”的评论和笔记沉淀为后续 RAG 记忆输入。

后续实现时机：
- 不建议立刻进入复杂 GraphRAG。
- 当前优先继续跑通主链后半段：审核保存草稿 -> 私密发布/状态同步 -> 表现回填。
- 等真实主链稳定后，再做采集候选池评分与 RAG 数据结构，这样沉淀的数据才可靠。

## 2026-06-11 主链后半段：审核保存草稿验证

本轮继续主链后半段的第一步：对真实采集 + LangGraph + 真实 LLM 生成的 run 执行人工审核通过，但不触发创作者平台发布。

验证对象：
- API：`http://127.0.0.1:8013`
- run：`run_c91c97a1d502`
- 审核前状态：`status=success`，`publish_status=pending`，`human_approved=false`

执行结果：
- 审核接口：`POST /runs/run_c91c97a1d502/approve`
- 返回：`ok=true`
- `publish_status=success`
- `human_approved=true`
- `operation_memory_written=true`
- `operation_record_id=op_32545c8a8d31`
- `creator_publish_requested=false`
- `creator_publish_status=not_requested`
- Markdown 草稿：`output/markdown_exports/20260611_235133_小红书选题先别急着判断，这几个坑要避开.md`
- API 日志：`data/logs/api.log` 已记录 `run_approved run_id=run_c91c97a1d502`

当前判断：
- 主链已从“待人工审核”推进到“审核通过并保存本地草稿/运营记忆”。
- 因本次未绑定创作者图片素材、也未请求 creator 发布，所以没有触发私密发布。
- 下一条主链任务应使用新 run 做“绑定真实图片素材 -> 审核通过并请求私密发布 -> 状态同步 -> 表现回填”，因为已保存的 run 不能再绑定 creator assets。

## 2026-06-12 主链后半段：真实私密发布、状态同步、表现回填

本轮目标是验证完整的后半段真实闭环：新 run -> 绑定图片素材 -> 审核通过并请求创作者平台私密发布 -> 作品状态同步 -> 按 creator_note_id 表现回填。

执行前提：
- `scripts/check_creator_platform.py --mode spider_xhs` 预检通过：`ok=true`。
- 重新启动 8014 API，并显式设置：
  - `COLLECTOR_MODE=spider_xhs`
  - `CREATOR_MODE=spider_xhs`
  - `LLM_MODEL_NAME=deepseek-v4-pro`
- 8014 运行在非沙箱网络环境，避免真实小红书/LLM 请求走 `127.0.0.1:9`。

执行结果：
- 新 run：`run_d2572a74de62`
- run 状态：`success`
- 真实采集：`raw_notes_count=1`，`raw_comments_count=0`
- LLM：`enabled=true`，`model=deepseek-v4-pro`
- 本地生成中性测试封面：`data/manual_creator_assets/run_d2572a74de62_cover.png`
- 图片绑定接口：`POST /runs/run_d2572a74de62/creator-assets`
- 绑定结果：`creator_images_count=1`
- 审核发布接口：`POST /runs/run_d2572a74de62/approve`
- 发布结果：
  - `publish_status=success`
  - `creator_publish_requested=true`
  - `creator_publish_status=success`
  - `creator_publish_mode=spider_xhs`
  - `creator_note_id=6a2adc0c000000003502cd53`
  - `operation_record_id=op_247efc20de96`
- 状态同步：
  - `GET /creator/notes/status?creator_note_id=6a2adc0c000000003502cd53`
  - `status=synced`
  - `visibility_label=仅自己可见`
  - `metrics_snapshot={views:0, likes:0, collects:0, comments:0}`
- 表现回填：
  - `POST /performance`
  - `updated_record.record_id=op_247efc20de96`
  - `status=performance_recorded`
  - `creator_note_id=6a2adc0c000000003502cd53`
  - `performance_score=0`

重要观察：
- 这次真实采集命中的笔记互动为 0，导致 `raw_comments_count=0`。这再次证明后续必须做“候选池 + 综合评分 + 评论质量评分”，不能只取搜索结果第一条或低互动候选。
- 状态同步第一次请求曾短暂返回 `not_found`，随后作品列表和状态接口均能查到新笔记，说明平台发布后列表可能存在短暂同步延迟；后续应做轮询/等待。
- 当前测试图片是本地生成的中性测试图，不是最终内容生产素材。下一阶段可尝试根据生成文本内容调用 GPT-image 系列模型生成图片，再走同一套 `creator-assets` 绑定和私密发布流程。

下一步建议：
1. 调研并确认 OpenAI 图片生成 API 和实际模型名/API Key 配置，不要直接假设 `GPT-image-2` 可用。
2. 做“文本内容 -> 图片提示词 -> 生成图片 -> 保存到 data/generated_assets -> 绑定 creator-assets”的独立最小链路。
3. 图片生成链路通过后，再替换当前手动/本地测试图素材绑定。

补充调研：
- 本地 `.env` 目前没有 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_IMAGE_MODEL` 或 `GPT_IMAGE_MODEL`。
- 当前代码中没有 OpenAI 图片生成集成，只有 OpenAI-compatible 文本 LLM 配置，且目前指向 DeepSeek。
- 官方 OpenAI 文档显示图片生成可通过 Image API `images.generate` 使用 `gpt-image-2`，但该模型可能需要组织验证。
- 旧 8013 API 已停止，目前保留 8014 真实 creator 模式 API。

## 2026-06-12 GPT-image-2 生图素材链路：代码就绪，真实请求被 key 拒绝

本轮目标是在已跑通的私密发布闭环基础上，尝试用 OpenAI 图片模型根据 run 文本内容生成封面图，再复用 `creator-assets` 绑定流程。

已完成工程改动：
- 新增 `platforms/openai_image.py`，封装 OpenAI Images API 配置读取、提示词构造、图片请求、base64 解码和本地保存。
- 新增 `scripts/generate_creator_image_asset.py`，支持从 `GET /runs/{run_id}` 读取内容，生成图片，保存到 `data/generated_assets/`，并可选绑定到 `/runs/{run_id}/creator-assets`。
- `.env.example` 增加 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_IMAGE_MODEL`、`OPENAI_IMAGE_SIZE` 等图片生成配置模板。
- 修复脚本 `--prompt-out` 写入时父目录不存在的问题，新增 `write_prompt()`。
- 新增 OpenAI 图片错误脱敏，避免 HTTP 错误体回显 `sk-...` key 片段。

验证结果：
- 单测与编译：
  - `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_openai_image_generation.py tests\test_generate_creator_image_asset.py tests\test_creator_asset_binding.py tests\test_check_api_run_auth.py -q`
  - 结果：`16 passed`
  - `D:\Anaconda\envs\ContentShare\python.exe -m compileall platforms\openai_image.py scripts\generate_creator_image_asset.py`
  - 结果：通过
- 配置来源检查：
  - `.env` 已存在 `OPENAI_API_KEY`
  - 脚本实际加载的是 `.env` 中的 key，未被系统环境变量覆盖
  - `OPENAI_IMAGE_MODEL=gpt-image-2`
  - `OPENAI_BASE_URL=https://api.openai.com/v1`
- 真实命令：
  - `D:\Anaconda\envs\ContentShare\python.exe .\scripts\generate_creator_image_asset.py --base-url http://127.0.0.1:8014 --run-id run_fda76a64a278 --bind --prompt-out data\generated_assets\run_fda76a64a278_prompt.txt`
  - OpenAI 返回：HTTP 401，`code=invalid_api_key`
  - 脱敏复验通过：错误输出中的 key 已替换为 `[REDACTED_OPENAI_KEY]`

当前判断：
- 这一步还没有通过 GPT-image-2 生图测试；没有生成图片，也没有绑定到 `run_fda76a64a278`。
- 代码侧最小链路已就绪，当前卡点是 `.env` 里的 OpenAI key 不被官方 OpenAI endpoint 接受，或该 key 不对应 `https://api.openai.com/v1`。
- 如果使用官方 OpenAI，需要更换/重新生成有效 API key。
- 如果使用中转或代理服务，需要同时设置对应的 `OPENAI_BASE_URL`，不能只填代理 key 并沿用官方 base URL。

下一步建议：
1. 先更新 `.env` 中的 `OPENAI_API_KEY`，或补充正确的 `OPENAI_BASE_URL`。
2. 更新后重新执行同一条 `generate_creator_image_asset.py` 命令。
3. 生图绑定成功后，再检查生成图片质量，并继续执行私密发布、状态同步、表现回填。

## 2026-06-12 GPT-image-2 中转服务新 key 诊断

本轮用户更换图片服务 key 后重新验证生图链路。

当前 `.env` 图片配置：
- `OPENAI_BASE_URL=https://yituoshiai.com/v1`
- `OPENAI_IMAGE_MODEL=gpt-image-2`
- `OPENAI_IMAGE_SIZE=1024x1536`
- `OPENAI_IMAGE_QUALITY=medium`
- `OPENAI_IMAGE_FORMAT=png`
- 新 key 可被脚本加载，未在日志中输出明文。

诊断结果：
- `GET https://yituoshiai.com/v1/models` 返回 `200`，JSON 正常，模型列表包含 `gpt-image-2`。
- 使用主链脚本执行真实生图绑定：
  - `scripts/generate_creator_image_asset.py --base-url http://127.0.0.1:8014 --run-id run_fda76a64a278 --bind`
  - 返回 `HTTP 503`，错误：`No available compatible accounts`。
- 直接调用 `POST /v1/images/generations` 做最小参数诊断：
  - payload 仅包含 `model=gpt-image-2`、`prompt`、`size=1024x1536`
  - 返回同样 `HTTP 503 No available compatible accounts`。
- 将 size 改为 `1024x1024` 后仍返回同样 `HTTP 503 No available compatible accounts`。

当前判断：
- 新 key 不再表现为 `invalid_api_key`，认证和 `/models` 访问是通的。
- 失败不由本项目脚本的 `quality`、`output_format` 或 `1024x1536` 尺寸导致。
- 根因更可能在中转服务侧：`gpt-image-2` 虽然出现在模型列表，但默认分组下没有可用于 `/images/generations` 的兼容账号/通道，或后台没有给当前 key 分配可用图片生成账号。

下一步建议：
1. 在中转服务后台确认当前 key 所属分组是否已绑定可用的 `gpt-image-2` 图片生成通道。
2. 如果后台实际模型名不是 `gpt-image-2`，需要把 `.env` 的 `OPENAI_IMAGE_MODEL` 改成服务商给出的真实可用模型名。
3. 通道可用后再重跑 `generate_creator_image_asset.py`，成功后继续图片质量检查和私密发布链路。

## 2026-06-12 GPT-image-2 第二个中转服务 key 诊断

本轮用户再次更换图片服务 key 后重新验证生图链路。

当前 `.env` 图片配置：
- `OPENAI_BASE_URL=https://api.xingyuzhida.me/v1`
- `OPENAI_IMAGE_MODEL=gpt-image-2`
- `OPENAI_IMAGE_SIZE=1024x1536`
- `OPENAI_IMAGE_QUALITY=medium`
- `OPENAI_IMAGE_FORMAT=png`
- 新 key 可被脚本加载，未在日志中输出明文。

诊断结果：
- `https://api.xingyuzhida.me/models` 返回 HTML，不是 API JSON。
- `https://api.xingyuzhida.me/v1/models` 返回 `200`，JSON 正常。
- `/v1/models` 中包含 `gpt-image-1`、`gpt-image-1.5`、`gpt-image-2`，当前 `OPENAI_IMAGE_MODEL=gpt-image-2` 存在。
- 修正 `.env` 的 `OPENAI_BASE_URL` 为带 `/v1` 后，主链脚本访问 `/v1/images/generations`。
- 主链脚本仍返回 `HTTP 503`：`No available compatible accounts`。
- 直接调用 `/v1/images/generations` 做最小参数诊断：
  - `size=1024x1536` 返回同样 `HTTP 503 No available compatible accounts`。
  - `size=1024x1024` 返回同样 `HTTP 503 No available compatible accounts`。

当前判断：
- 新 key 认证可用，base URL 修正后也能访问模型列表。
- 失败不是由项目脚本额外参数、图片格式、质量参数或竖图尺寸引起。
- 根因仍更可能是中转服务侧：当前 key/分组没有可用于 `gpt-image-2` 图片生成的兼容账号或通道。

下一步建议：
1. 在中转服务后台确认当前 key 的 `gpt-image-2` 图片生成通道是否真的启用。
2. 如果服务商要求使用 `gpt-image-1` 或 `gpt-image-1.5`，可临时把 `.env` 的 `OPENAI_IMAGE_MODEL` 改成对应模型再测。
3. 服务端通道可用后，再重跑 `generate_creator_image_asset.py` 完成图片生成和绑定。

## 2026-06-12 M25 主流程护栏：平台状态只读入口

本轮按用户要求先暂停生图问题，继续主流程。对照现有代码后确认：
- 创作者平台发布日限、失败停手、发布前 Cookie 自检、发布前随机延时已有实现和测试。
- 采集端 PC Cookie 自检已有实现和测试。
- 主流程缺口之一是这些运行状态不够前置可见，工作台或脚本只能在真正提交/发布时才看到问题。

已完成：
- 新增 `app.api.platform_status()`。
- 新增 `GET /platform/status`，返回只读状态，不触发真实采集或真实发布。
- 返回内容包括：
  - `collector_runtime`
  - `creator_runtime`
  - `creator_publish_guardrail`
- 该接口默认走现有 API 鉴权规则，和 `/queue` 一样不是公开健康检查。
- 新增 `tests/test_api_platform_status.py` 覆盖函数聚合和 HTTP 路由。

已验证：
- RED：新增测试在旧代码下失败，缺少 `collector_platform` 和 `/platform/status`。
- GREEN：实现后 `tests/test_api_platform_status.py` 通过。
- 相关回归：
  - `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_api_platform_status.py tests\test_platform_safety_guardrails.py tests\test_api_auth.py tests\test_api_creator_review_publish.py tests\test_creator_platform.py -q`
  - 结果：`47 passed`
- 编译：
  - `D:\Anaconda\envs\ContentShare\python.exe -m compileall app\api.py`
  - 结果：通过

当前判断：
- M25 的底层护栏已部分可用，并且现在有了 API 层只读状态入口。
- 下一步可以把工作台或检查脚本接到 `/platform/status`，让真实主链提交/私密发布前先显示 Cookie、creator 状态和发布日限/停手原因。

## 2026-06-12 M25 主流程护栏：工作台平台状态可视化

本轮继续主流程，承接 `/platform/status` 只读入口，把采集端、创作者端和发布护栏状态前置展示到工作台。

已完成：
- 工作台侧边栏新增“平台状态”面板。
- 前端 `refreshShell()` 并行请求 `GET /platform/status`，并渲染：
  - 采集端 runtime 状态。
  - 创作者端 runtime 状态。
  - 发布护栏允许/暂停状态、当日发布计数或停手原因。
- 状态面板只读，不触发真实采集、真实发布或作品列表同步。
- `scripts/check_workbench_ui.py` 增加平台状态面板 smoke 检查，避免后续 UI 改动漏掉该面板。
- 新增/更新测试：
  - `tests/test_api_platform_status.py`
  - `tests/test_workbench_platform_status_static.py`

已验证：
- TDD RED/GREEN：先让 smoke 脚本平台状态覆盖测试失败，再补脚本检查并转绿。
- 局部回归：`25 passed`。
- 全量测试：`143 passed`。
- 编译检查：`D:\Anaconda\envs\ContentShare\python.exe -m compileall app platforms scripts` 通过。
- 浏览器 smoke：
  - desktop：`ok=true`，`console_errors=[]`
  - mobile：`ok=true`，`console_errors=[]`
- `git diff --check` 返回 0，仅有 Git 换行提示。

当前判断：
- M25 平台护栏已经从底层检查推进到 API 和工作台可见。
- 下一条主链任务建议做“发布状态轮询/等待”，因为真实私密发布后作品列表可能短暂 `not_found`，目前只查一次会造成误判。
- 另一个后续主线是采集候选池评分，解决真实采集时误选低互动/低评论笔记的问题；但它更适合排在发布状态轮询之后。

## 2026-06-12 项目竣工口径复盘与加速路线

本轮讨论结论：之前只按“业务主链是否跑通”复盘是不完整的。项目竣工必须同时覆盖业务主链、数据库、部署、队列/worker、日志监控、安全、数据分析、GraphRAG 和阶段二能力。

当前阶段判断：
- 阶段一 MVP 主链已经基本跑通：真实采集、LangGraph、真实 LLM、人工审核、草稿保存、运营记忆、真实素材绑定、创作者平台私密发布、平台笔记 ID 同步、表现回填都已完成过验证。
- 但系统还没有达到稳定生产化竣工：当前最大缺口已经从“能否闭环”转为“能否稳定、可观测、可部署、可恢复、可扩展地长期运行”。

业务主链未完成：
- 发布状态轮询/等待：私密发布后作品列表可能短暂 `not_found`，当前只查一次容易误判。
- 采集候选池评分：不能只取搜索第一条，需要按主题相关度、评论数、点赞/收藏、近期性、评论质量综合评分。
- 基础数据分析报告：每次 run 应说明为什么选这些笔记、评论质量如何、痛点可信度如何、适合什么内容结构。
- 生图链路：工程代码已就绪，但外部图片通道返回 `503 No available compatible accounts`，不能算真实通过。
- 公开发布、定时发布、视频发布仍未完成，目前只验证私密图文。
- 人工审核还不是 LangGraph 原生 interrupt/resume，目前是 API 层续跑。
- Cookie 过期提示和重取流程还需要更完整的产品化处理。

数据库未完成：
- 正式 schema 仍需补齐，建议至少包含：
  - `runs`
  - `run_events`
  - `drafts`
  - `creator_assets`
  - `creator_notes`
  - `operation_records`
  - `performance_records`
  - `collection_candidates`
  - `raw_notes`
  - `raw_comments`
  - `analysis_reports`
  - `audit_events`
- JSON run store 需要迁移到 SQLite/PostgreSQL。
- operation memory 需要从 JSON 迁移到数据库。
- 图片素材元数据需要入库，不能只依赖文件目录。
- 采集原始数据、清洗后数据、候选评分、评论质量评分需要分层保存。
- 需要数据库迁移工具、索引、唯一约束、幂等键、备份恢复、归档策略。
- Cookie、token、xsec_token、用户标识等敏感数据需要数据库和日志层脱敏。

部署未完成：
- 需要确定 API 服务部署方式：Docker、systemd、Windows 服务或其他方式。
- API 与 worker 需要拆分，API 不应长期承担所有耗时任务。
- 前端静态资源需要明确由 API 托管还是 Nginx/反向代理托管。
- 需要 HTTPS、反向代理、健康检查和启动脚本。
- 需要 `.env.local`、`.env.production`、`.env.example` 分层，并建立 secrets 管理方式。
- 需要持久化目录规划：数据库、run 数据、图片素材、Markdown 草稿、日志、备份。
- 需要重启恢复策略：服务重启后 queued/running 任务如何恢复或标记失败。
- 需要部署文档：从空机器到跑通一条主链的步骤。
- 需要权限边界：谁能提交任务、谁能审核、谁能触发发布。

队列与 worker 未完成：
- API/worker 进程拆分。
- 队列持久化。
- 任务超时、取消、失败记录。
- 可控重试；发布类任务不能自动连续重试。
- 并发限制。
- 不同任务类型拆队列：采集、生成、发布、分析。
- worker 心跳和卡死检测。

日志和监控未完成：
- 每个 run 的事件时间线。
- 每个节点耗时。
- LLM token 与成本统计。
- 采集成功率、评论命中率、Cookie 失败率。
- 发布成功率、状态同步延迟。
- 错误聚合和查询入口。
- 告警：Cookie 失效、发布失败、队列堆积、LLM 失败、数据库写入失败。

数据分析与 GraphRAG 的顺序：
- 数据分析不能等 GraphRAG 之后做，应该前置。
- 推荐顺序：
  1. 数据库基础表。
  2. 采集候选池评分。
  3. 基础数据分析报告。
  4. 表现数据结构化沉淀。
  5. GraphRAG。
- GraphRAG 是增强层，不是数据分析的前置；否则会把未清洗、未评分、未结构化的数据沉淀进图谱，后续返工成本高。

阶段二未完成：
- 千帆。
- 蒲公英。
- 商品卖点匹配。
- 软广生成节点。
- 商业合规审核。
- 70/30 内容比例。
- 单周软广限制。
- 不连发软广。
- 达人匹配和邀约。

加速路线建议：
- 不要一条线慢慢磨，改成三条主线并行推进。
- 主链稳定线，预计 2-4 天：
  - 发布状态轮询。
  - 采集候选池评分。
  - 基础数据分析。
- 工程化数据线，预计 4-7 天：
  - SQLite schema。
  - run store / operation memory 迁移。
  - 事件表、素材表、表现表。
- 部署可运行线，预计 3-6 天：
  - API/worker 启动模板。
  - 环境配置。
  - 日志目录。
  - 健康检查。
  - 部署文档。

工期判断：
- 如果定义为阶段一“可稳定本地/单机部署运行”，还需要约 7-12 天。
- 如果包含 GraphRAG，需要再加约 5-8 天。
- 如果包含阶段二软广、达人、千帆、蒲公英和生产化部署，整体竣工更接近 4-6 周。

当前优先级调整：
- 下一步不应直接进入复杂 GraphRAG。
- 优先做发布状态轮询和数据库基础表设计。
- 数据库应在 GraphRAG 前完成，否则后续图谱和向量检索会建立在松散 JSON 与临时文件上，迁移成本过高。

## 2026-06-12 工作区无用文件清理

本轮按用户要求检查并清理当前项目目录中的无用文件。

已删除：
- `.codex/`：未跟踪目录，且 `config.toml` 中含明文小红书 Cookie，不适合留在项目工作区。
- `.pytest_cache/`
- 各模块 `__pycache__/`
- 测试临时目录：`data/pytest_tmp*`
- 浏览器 smoke 截图目录：`data/ui_checks/`
- 旧 API server 输出日志：`data/api_server.err.log`、`data/api_server.out.log`
- 临时 SQLite 文件：`data/self_test.sqlite3`、`data/tmp_integration_debug.sqlite3`

明确保留：
- `.env`：本地真实配置，不提交但运行需要。
- `data/api_runs`、`data/collector_runs`、`data/creator_assets`、`data/generated_assets`、`data/manual_creator_assets`、`data/logs`：真实 run、素材、日志或调试数据。
- `memory/operation_history.json` 及备份：运营记忆数据。
- `output/markdown_exports`：生成草稿。
- `.worktrees/`：Git 注册工作树 `m16a-sqlite-run-queue`，不能当缓存删除。
- `vendor/Spider_XHS/node_modules/`：第三方依赖目录，未确认无用前保留。
- `AGENTS.md`：当前协作指令文件，虽未跟踪但不视为无用文件。

清理后验证：
- `.codex=False`
- `.pytest_cache=False`
- `__pycache__=False`
- `data/pytest_tmp=False`
- `data/ui_checks=False`
- `data/self_test.sqlite3=False`
- `data/tmp_integration_debug.sqlite3=False`

## 2026-06-12 GPT-image-2 生图链路恢复验证

本轮目标是在用户更换正确图片服务 Key 后，收尾此前 GPT-image-2 生图链路无法通过的历史遗留问题。

根因确认：
- 之前的 Key 不具备 `gpt-image-2` 权限，服务端返回 `This token has no access to model gpt-image-2`。
- 当前新 Key 可通过 `https://api.xrouter.dev/v1/models` 看到 `gpt-image-2`。
- `OPENAI_BASE_URL` 必须配置为 `https://api.xrouter.dev/v1`，如果少 `/v1`，项目脚本会请求到 HTML 页面并报 `OpenAI image response is not valid JSON`。

已完成：
- 将本地 `.env` 的 `OPENAI_BASE_URL` 修正为 `https://api.xrouter.dev/v1`。
- 使用现有成功 run `run_fda76a64a278` 执行生图绑定脚本。
- 成功生成图片：`data/generated_assets/run_fda76a64a278/20260612_162936_openai_cover.png`。
- 成功绑定到 creator assets：`data/creator_assets/run_fda76a64a278/01_20260612_162936_openai_cover.png`。
- run summary 中 `creator_images_count=1`。
- 视觉检查确认生成图不是空白/损坏图，内容为“小红书选题避坑指南”风格封面。

验证结果：
- 生图脚本返回 `ok=true`、`model=gpt-image-2`、`provider_mode=openai_images`、`bound=true`。
- 生成图片与绑定图片文件大小一致，均为 `2388510` bytes。
- 相关回归通过：`12 passed`。

当前限制：
- 本轮只验证“生图 -> 保存 -> 绑定 run”，没有触发真实 creator 私密发布。
- `.env` 是本地忽略文件，Key 与 base URL 修正不会进入 Git。

下一步建议：
- 如需继续完整主链，可基于已绑定图片的 `run_fda76a64a278` 执行一次人工确认后的 creator 私密发布验证。
- 若暂不做真实写入，回到主线优先任务：发布状态轮询/等待。

## 2026-06-12 M26 发布状态轮询/等待

本轮目标是沿“发布状态”主线一次性推进一批稳定性任务，解决真实 creator 私密发布后作品列表可能短暂 `not_found`，从而导致状态同步误判的问题。

已完成：
- 新增 `platforms.creator.wait_for_published_note_status()`。
- 等待函数复用现有只读 `get_published_note_status()`，只查询作品列表，不触发发布、公开、修改或删除。
- 仅当状态为 `not_found` 时按配置等待并重查；状态为 `synced` 立即返回，状态为 `unavailable` 立即停止。
- 轮询结果会返回 `attempts` 和 `waited_seconds`，便于前端和诊断区解释等待过程。
- `GET /creator/notes/status` 支持查询参数：
  - `wait=true`
  - `attempts`
  - `interval_seconds`
  - `limit`
- `app.api.get_creator_note_status()` 支持普通单次查询和等待查询两种路径。
- 工作台作品列表新增单条作品的“刷新状态”按钮。
- “刷新状态”调用只读等待接口：`/creator/notes/status?...&wait=true&attempts=5&interval_seconds=2`。
- 刷新后只更新当前作品卡片的状态摘要和表现录入区提示，不自动录入表现，也不触发真实写入。

验证结果：
- TDD RED：新增 6 个聚焦测试在旧代码下失败，失败点集中在等待函数缺失、API 参数未透传、前端刷新入口缺失。
- TDD GREEN：聚焦测试通过，`6 passed`。
- 相关回归通过：`37 passed`。
- JS 语法检查通过：`node --check app\static\app.js`。
- Python 编译通过：`compileall platforms\creator.py app\api.py`。
- 浏览器 smoke：
  - desktop：`ok=true`，`console_errors=[]`。
  - mobile：`ok=true`，`console_errors=[]`。
- 全量测试通过：`149 passed`。

当前限制：
- 本轮是“按需刷新/等待”，不是后台自动定时轮询，也不写回运营记忆。
- 真实 creator 私密发布后的状态轮询尚未用新发布笔记做真实端到端验证；当前验证覆盖本地单元、API、工作台和浏览器 smoke。
- `wait=true` 会让该 HTTP 请求等待一段时间，默认工作台只在用户点击“刷新状态”时触发。

下一步建议：
- 可基于已恢复的生图素材链路和当前发布状态等待能力，做一次“已绑定图片 run -> 人工确认私密发布 -> 等待状态同步 -> 表现回填”的真实后半段验证。
- 或继续进入采集候选池评分，为后续数据分析和 GraphRAG 入库打基础。

## 2026-06-12 真实后半段闭环验证：生图素材 -> 私密发布 -> 状态等待 -> 表现回填

本轮目标是按用户要求沿发布状态主线继续推进，基于已绑定 GPT-image-2 图片素材的 run，做一次真实 creator 私密发布、等待平台状态同步，并按真实 `creator_note_id` 完成表现回填。

前置状态：
- 8014 API 是旧代码启动，`/platform/status` 返回 404，不适合验证 M26 发布状态等待能力。
- 新启动 8017 API，临时设置 `CREATOR_MODE=spider_xhs`。
- 8017 `/platform/status` 通过：
  - `collector_runtime.ok=true`
  - `creator_runtime.ok=true`
  - `creator_publish_guardrail.allowed=true`
  - 当日 creator 成功计数从 `1/3` 开始。
- 目标 run：`run_fda76a64a278`。
- 目标 run 已绑定真实生成图：`creator_images_count=1`。

执行结果：
- 人工确认私密发布成功：
  - `publish_status=success`
  - `creator_publish_status=success`
  - `creator_publish_mode=spider_xhs`
  - `creator_note_id=6a2bce0b000000003502c564`
  - `operation_record_id=op_3ad88ee563ba`
- 使用 M26 等待接口查询状态：
  - `GET /creator/notes/status?creator_note_id=6a2bce0b000000003502c564&limit=50&wait=true&attempts=6&interval_seconds=2`
  - 返回 `status=synced`
  - 标题：`小红书选题先别急着判断，这几个坑要避开`
  - `visibility_label=仅自己可见`
  - `attempts=6`
  - `waited_seconds=10.0`
  - 指标快照均为 0。
- 表现回填成功：
  - `record_id=op_3ad88ee563ba`
  - `status=performance_recorded`
  - `performance_score=0`
  - `views/likes/collects/comments/follows` 均为 0。

收口验证：
- `GET /runs/run_fda76a64a278` 显示 `creator_publish_status=success`，同一个 `creator_note_id`。
- `GET /creator/notes/status` 单次状态查询返回 `status=synced` 和 `visibility_label=仅自己可见`。
- `GET /memory/records?limit=10` 可找到同一个 `creator_note_id`，记录状态为 `performance_recorded`。

当前效果：
- 已验证真实后半段主链可用：真实生成图片素材 -> 绑定 run -> 人工确认私密发布 -> 平台状态等待同步 -> 真实平台笔记 ID 表现回填。
- M26 发布状态等待能力在真实平台同步延迟场景中有效；本次第 6 次查询才同步成功，说明等待机制确实避免了短暂 `not_found` 误判。

当前限制：
- 本次发布是私密图文，未做公开发布、定时发布或视频发布。
- 表现指标为 0 是平台当前快照结果，不是回填链路失败。
- 8017 API 是本轮验证用临时真实 creator 模式服务，用户验证完成后可手动停止该进程。

下一步建议：
- 进入采集候选池评分，解决真实采集时误选低互动或低评论笔记的问题。
- 之后补基础数据分析报告，为数据库结构化沉淀和 GraphRAG 入库打基础。

## 2026-06-12 采集候选池评分初版

本轮目标是在发布状态主线完成真实后半段验证后，继续补齐采集质量上游能力：不再只依赖搜索结果前几条，而是先形成候选池，再按主题相关度、互动质量和评论质量综合排序，降低误选低互动/低评论笔记的概率。

已完成：
- `spider_xhs` 真实采集新增候选池评分，搜索阶段先按配置扩大候选池，再按评分选出进入后续评论分析的笔记。
- 候选评分综合考虑主题命中、标题相关度、评论数、点赞/收藏等互动信号，并对低相关、无标题、低价值候选做惩罚。
- 采集结果新增 `collection_candidates`，保存候选评分、排名、是否被选中以及评分摘要，便于后续解释“为什么选这些笔记”。
- `XHSState`、insight 节点兜底、API insight payload 和 mock collector 已兼容 `collection_candidates`。
- `scripts/check_collector.py --search` 增加候选池评分输出，同时修复 Windows GBK 控制台遇到 emoji 标题时的 `UnicodeEncodeError`，改为安全 JSON 输出。
- `.env.example` 新增候选池配置：
  - `XHS_CANDIDATE_POOL_MULTIPLIER=3`
  - `XHS_CANDIDATE_POOL_LIMIT=20`
- 新增测试覆盖候选评分排序、候选池返回字段、mock 兼容和脚本输出。

真实搜索诊断：
- 命令：`D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_collector.py --search --topic "小红书新手选题方法" --limit 5`
- 返回 `raw_notes=9`、`selected_notes=3`。
- 候选第 1 为 `威风整理｜小红书新手21天起号手册`，评分 `164`，被选中。
- 其它高分候选包括 `小红书的8种变现方式，你知道几个`、`9分钟讲清，小红书从0-1完整运营攻略！`。
- emoji 标题会被转义输出，不再导致 GBK 控制台崩溃。

验证结果：
- 聚焦候选池测试通过：`tests/test_collector_candidate_scoring.py`。
- 脚本输出测试通过：`tests/test_check_collector_output.py`。
- 相关回归通过：候选池评分、评论噪声过滤、平台安全护栏。
- Python 编译检查通过：`platforms/spider_xhs_collector.py`、`platforms/mock_collector.py`、`scripts/check_collector.py`、`app/api.py`、`app/state.py`、`nodes/insight_node.py`。
- 全量测试通过：`153 passed`。

当前效果：
- 采集链路从“拿搜索结果前几条”升级为“候选池 -> 评分排序 -> 选择样本”。
- API/run 结果里可以看到 `collection_candidates`，后续基础数据分析报告可以直接解释样本来源和置信度。
- 真实采集诊断脚本可以直接查看候选评分、入选笔记和被淘汰候选，方便人工判断采集质量。

当前限制：
- 评分仍是规则初版，不是语义 embedding 或 LLM 评审。
- 评论质量评分目前主要依赖现有噪声过滤与评论命中情况，后续还需要更细的“真实问题/反对意见/使用场景”质量分。
- 候选池结果仍依赖小红书搜索接口和 Cookie 状态；Cookie 失效时仍需要走现有自检与错误诊断。

下一步建议：
- 进入基础数据分析报告，让每次 run 能说明样本为什么被选中、评论质量如何、痛点可信度如何、适合什么内容结构。
- 或继续细化评论质量评分，为后续数据库结构化沉淀和 GraphRAG 入库做更干净的数据层。

## 2026-06-12 基础数据分析报告初版

本轮目标是在采集候选池评分初版之后，继续补齐主线的“可解释数据分析”能力：让每次 run 不只返回候选、评论和痛点，还能直接说明样本为什么被选中、评论质量如何、痛点可信度如何，以及适合什么内容结构。

已完成：
- 新增 `platforms.analysis_report.build_analysis_report()`，使用确定性规则生成 `analysis_report`，不调用 LLM、不触发网络请求、不写平台。
- 报告包含：
  - `sample_selection`：候选数量、入选数量、最高分、入选标题、选择说明。
  - `comment_quality`：评论数、洞察数、痛点数、证据数、质量等级和原因。
  - `pain_point_confidence`：0-100 分、`high/medium/low` 等级和原因。
  - `content_structure_hint`：建议内容结构与原因。
  - `risks`：候选少、评论少、证据不足、评论抓取失败等风险。
  - `summary`：一句话总览。
- `nodes/insight_node.py` 在采集成功和采集异常兜底两条路径都会返回 `analysis_report`。
- `app/state.py` 和 `app/api.py` 已透传 `analysis_report`，run/API 的 `insights.analysis_report` 可直接查看。
- `scripts/check_collector.py` 已输出同一套 `analysis_report`，真实采集诊断可以直接观察样本质量和风险。
- 新增设计规格与实施计划：
  - `docs/superpowers/specs/2026-06-12-basic-analysis-report-design.md`
  - `docs/superpowers/plans/2026-06-12-basic-analysis-report.md`
- 新增测试：
  - `tests/test_analysis_report.py`
  - `tests/test_analysis_report_integration.py`
  - 扩展 `tests/test_check_collector_output.py`

验证结果：
- TDD RED：
  - 核心测试先因 `platforms.analysis_report` 缺失失败。
  - 集成测试先因节点/API 未透传 `analysis_report` 失败。
  - 脚本测试先因 `build_collection_diagnostic_payload` 缺失失败。
- 聚焦回归通过：`12 passed`。
- Python 编译检查通过：`platforms/analysis_report.py`、`nodes/insight_node.py`、`app/api.py`、`app/state.py`、`scripts/check_collector.py`。
- 全量测试通过：`161 passed`。

当前效果：
- 每次采集 run 可以在 `insights.analysis_report` 里看到基础分析报告。
- `check_collector.py --search` 现在会打印 `analysis_report`，如果加 `--comments`，报告会同时结合评论洞察与痛点证据。
- 这一步为后续数据库 `analysis_reports` 表和 GraphRAG 入库质量打了稳定的结构基础。

当前限制：
- 报告仍是规则初版，不是 LLM/embedding 语义评审。
- 内容结构建议只是分析提示，不覆盖现有 strategy 节点的最终内容类型决策。
- 评论质量评分还需要继续细化“真实问题、反对意见、使用场景、引流/水军惩罚”等维度。

下一步建议：
- 进入数据库基础表设计，把 `runs`、`collection_candidates`、`analysis_reports`、`raw_notes`、`raw_comments` 等结构化落库。
- 或继续做评论质量评分细化，让 `analysis_report` 的可信度更接近真实运营判断。

## 2026-06-12 数据库基础业务表 schema 初始化

本轮目标是在既有 `SQLiteRunStore`、`SQLiteRunQueue`、`SQLiteOperationMemoryBackend` 兼容后端之上，补齐第一轮基础业务表 schema。按用户确认，本轮只做当前可预见的主链基础表，后续如果业务需要其它表再追加，不做过度设计。

已完成：
- 新增 `app/database_schema.py`，提供 `initialize_foundation_schema(db_path)`。
- 新增 foundation 业务表：
  - `run_events`
  - `raw_notes`
  - `collection_candidates`
  - `raw_comments`
  - `analysis_reports`
  - `drafts`
  - `creator_assets`
  - `creator_notes`
  - `performance_records`
  - `audit_events`
- 新增对应关键索引，覆盖 run 查询、topic 查询、候选排序、分析报告质量、素材/平台笔记/表现快照和审计动作。
- 初始化函数幂等，重复执行不会报错。
- 已验证 foundation schema 能和现有 `runs`、`run_queue_jobs`、`operation_records` 共存在同一 SQLite 数据库，不破坏已有 run store、queue、operation memory 行为。
- `.env.example` 新增配置说明：
  - `XHS_AGENT_DB_SCHEMA=foundation`
  - `XHS_AGENT_BUSINESS_TABLES_ENABLED=false`
- 新增设计规格与实施计划：
  - `docs/superpowers/specs/2026-06-12-foundation-database-schema-design.md`
  - `docs/superpowers/plans/2026-06-12-foundation-database-schema.md`
- 新增测试：
  - `tests/test_foundation_database_schema.py`

验证结果：
- TDD RED：`tests/test_foundation_database_schema.py` 初始因 `app.database_schema` 缺失失败。
- TDD GREEN：foundation schema 测试通过。
- SQLite 兼容聚焦回归通过：`22 passed`。
- Python 编译检查通过：`app/database_schema.py`。
- 全量测试通过：`164 passed`。

当前效果：
- 项目现在有统一的基础业务表 schema 初始化入口。
- 第一轮只建表和索引，不改变当前默认 JSON 行为，不改变 API 响应结构，不迁移历史数据。
- 后续可以在同一数据库内逐步旁路写入采集候选、原始笔记、评论、分析报告、草稿、素材、平台笔记、表现和审计事件。

当前限制：
- 当前还没有把 run state 自动同步到这些业务表。
- 当前还没有迁移历史 `data/api_runs/*.json` 或 `memory/operation_history.json`。
- `XHS_AGENT_BUSINESS_TABLES_ENABLED=false` 仍表示业务表写入默认不开启，下一轮需要单独实现写入器。

下一步建议：
- 实现 `app/business_store.py`，先旁路写入核心四张表：`raw_notes`、`collection_candidates`、`raw_comments`、`analysis_reports`。
- 新增手动补偿脚本 `scripts/sync_run_to_business_tables.py`，用于把已有 run 同步到业务表。

## 2026-06-12 业务表核心快照旁路写入初版

本轮目标是在 foundation schema 已经落地之后，继续推进数据库主线的第二步：先把现有 run state 中最核心的采集与分析数据同步到结构化业务表，但不改变当前 API/JSON 默认行为。

已完成：
- 新增 `app/business_store.py`，提供显式同步入口 `sync_run_business_tables(db_path, run_record)`。
- 同步函数会自动调用 `initialize_foundation_schema(db_path)`，确保目标数据库已有 foundation 业务表。
- 初版旁路写入核心四张表：
  - `raw_notes`
  - `collection_candidates`
  - `raw_comments`
  - `analysis_reports`
- 写入使用稳定 hash ID 和 SQLite upsert，重复同步同一个 run 不会产生重复行。
- `collection_candidates.note_row_id` 会优先通过 `original_index`、笔记 ID、URL 或标题关联到 `raw_notes`。
- `raw_comments.note_row_id` 会通过来源笔记 ID、URL 或 `source_note_title` 尽量关联到 `raw_notes`。
- JSON 兜底字段会递归过滤敏感字段，避免 Cookie、token、api key、authorization、xsec_token、用户昵称、头像、用户 ID、评论 ID 等进入业务表 JSON。
- URL 中的敏感查询参数也会过滤，降低 `xsec_token` 随 `note_url` 落库的风险。
- 新增实施计划：
  - `docs/superpowers/plans/2026-06-12-business-table-snapshot-writer.md`
- 新增测试：
  - `tests/test_business_store.py`

验证结果：
- TDD RED：`tests/test_business_store.py` 初始因 `app.business_store` 缺失失败。
- 聚焦回归通过：`tests/test_business_store.py tests/test_foundation_database_schema.py`，共 `6 passed`。
- Python 编译检查通过：`app/business_store.py app/database_schema.py`。
- 全量回归通过：`167 passed`。

当前效果：
- 现在可以把一个已有 run record 显式同步到 SQLite foundation 业务表。
- 采集笔记、候选池评分、评论样本和分析报告已经具备结构化沉淀入口。
- 现有 API 响应、run JSON、operation memory 和发布链路仍保持原行为，不会因为本轮改动自动写业务表。

当前限制：
- 当前还没有把同步函数挂到 API/worker 成功保存流程。
- 当前还没有手动补偿脚本同步历史 `data/api_runs/*.json`。
- 当前只写核心四张表，`drafts`、`creator_assets`、`creator_notes`、`performance_records`、`audit_events` 仍待后续逐步接入。
- `XHS_AGENT_BUSINESS_TABLES_ENABLED=false` 仍表示默认不自动旁路写入；下一步需要在配置开启时调用同步函数。

下一步建议：
- 把 `sync_run_business_tables()` 接到 run 成功保存流程后面，并受 `XHS_AGENT_BUSINESS_TABLES_ENABLED` 控制。
- 新增手动补偿脚本 `scripts/sync_run_to_business_tables.py`，用于把已有 run 同步到业务表。
- 之后扩展草稿、素材、平台笔记、表现和审计表的旁路写入。

## 2026-06-12 业务表自动同步与历史补偿脚本

本轮目标是在核心四表显式同步函数已经完成后，继续推进数据库主线：让成功 run 可以在配置开启时自动旁路写入业务表，并提供历史 run 的手动补偿脚本。

已完成：
- `app.config.Settings` 新增：
  - `db_schema`
  - `business_tables_enabled`
- `XHS_AGENT_DB_SCHEMA` 默认读取为 `foundation`。
- `XHS_AGENT_BUSINESS_TABLES_ENABLED` 默认 `false`，只有设置为 true/on/yes/1 时才启用自动写入。
- `app.api._save_run()` 增加自动同步 hook：
  - 只在 `business_tables_enabled=true` 时工作。
  - 只处理 `status=success` 的 run。
  - 只在 run store 是 `SQLiteRunStore` 时写业务表。
  - queued/running/failed 和 JSON run store 都不会自动写业务表。
- 自动同步成功后，会在 run summary 写入：
  - `business_table_sync_status=success`
  - `business_table_sync_counts`
  - `business_table_sync_error=None`
- 自动同步失败不会阻断 run 保存，会在 run summary 写入：
  - `business_table_sync_status=failed`
  - `business_table_sync_error`
  - 错误文本会复用敏感信息脱敏逻辑。
- 新增 `scripts/sync_run_to_business_tables.py`：
  - 支持 `--run-id` 同步单个 run。
  - 支持 `--limit` 同步最近 N 个 run。
  - 支持 `--dry-run` 只输出将同步/跳过的结果，不写业务表。
  - 输出 JSON summary，包含 `synced`、`skipped`、`errors`、`dry_run`。
- `scripts/check_runtime_config.py` 新增业务表配置检查：
  - 默认显示业务表写入关闭。
  - SQLite run store + enabled 时为 PASS。
  - JSON run store + enabled 时为 WARN。
- 新增实施计划：
  - `docs/superpowers/plans/2026-06-12-business-table-auto-sync.md`
- 新增测试：
  - `tests/test_api_business_table_sync.py`
  - `tests/test_sync_run_to_business_tables_script.py`
- 扩展测试：
  - `tests/test_m17a_config.py`
  - `tests/test_runtime_config_check.py`

验证结果：
- TDD RED：补偿脚本测试初始因 `scripts.sync_run_to_business_tables` 缺失失败。
- 配置/API/脚本/运行时检查聚焦测试通过：`16 passed`。
- 数据库相关回归通过：`34 passed`。
- Python 编译检查通过：`app/api.py`、`app/config.py`、`app/business_store.py`、`app/database_schema.py`、`scripts/sync_run_to_business_tables.py`、`scripts/check_runtime_config.py`。
- 全量回归通过：`175 passed`。

当前效果：
- 只要使用 SQLite run store，并设置 `XHS_AGENT_BUSINESS_TABLES_ENABLED=true`，成功 run 保存后会自动把采集笔记、候选池、评论和分析报告同步到业务表。
- 现有默认配置仍不自动写业务表，避免影响当前 JSON/本地开发路径。
- 已有历史 run 可以用补偿脚本手动同步，不需要重新跑采集/生成链路。

当前限制：
- 自动同步当前只覆盖四张核心表：`raw_notes`、`collection_candidates`、`raw_comments`、`analysis_reports`。
- `drafts`、`creator_assets`、`creator_notes`、`performance_records`、`audit_events` 仍未接入旁路写入。
- 补偿脚本当前读取配置中的 run store；如果历史 run 分散在多个目录或多个 DB，需要分批指定环境或后续增加目录参数。

下一步建议：
- 扩展业务表写入到 `drafts`、`creator_assets`、`creator_notes`、`performance_records`、`audit_events`。
- 给工作台/API 增加只读查询入口，方便直接验证业务表是否同步成功。
- 后续再考虑把部分分析查询从 run JSON 切到业务表。

## 2026-06-12 业务表剩余快照旁路写入

本轮目标是在核心四表自动同步和历史补偿脚本完成后，继续推进数据库主线：把同一个成功 run 中可确定的草稿、素材、平台笔记、表现快照和审计事件同步到 foundation 业务表，仍不改变当前 API/JSON 默认行为。

已完成：
- `app.business_store.sync_run_business_tables()` 从核心四表扩展为 9 张业务表 counts：
  - `raw_notes`
  - `collection_candidates`
  - `raw_comments`
  - `analysis_reports`
  - `drafts`
  - `creator_assets`
  - `creator_notes`
  - `performance_records`
  - `audit_events`
- 新增 `drafts` 写入：
  - 从 run `state` / `content` 读取图文或视频草稿字段。
  - 写入标题、正文、封面文案、图文页规划、图片 prompt、视频脚本、标签、评论引导、Markdown 路径和 `operation_record_id`。
  - 使用 `draft_<hash>` 稳定 ID，重复同步同一 run 不重复插入。
- 新增 `creator_assets` 写入：
  - 从 `state.creator_image_files` 读取已绑定图片路径。
  - 写入文件名、mime、文件大小、绑定顺序、对应图片 prompt 和素材状态。
  - 关联同 run 的 `draft_id`。
- 新增 `creator_notes` 写入：
  - 从 `state.creator_note_id` 和 `state.creator_publish_result` 读取平台笔记信息。
  - 写入发布模式、发布状态、可见性、平台类型、指标快照和脱敏后的发布响应 JSON。
- 新增 `performance_records` 写入：
  - 当 run state 中存在 `performance_data` 时写入曝光、点赞、收藏、评论、关注和表现分。
  - 关联 `operation_record_id`、`creator_note_id` 和 `run_id`。
- 新增 `audit_events` 写入：
  - 当前记录三类可追踪事件：`human_review`、`creator_publish`、`operation_memory_write`。
  - 审计事件使用稳定 hash ID，重复同步保持幂等。
- 继续复用现有敏感字段脱敏逻辑，避免 `token`、`cookie`、`authorization`、`xsec_token`、用户身份字段等进入 JSON 兜底字段。
- 新增实施计划：
  - `docs/superpowers/plans/2026-06-12-business-table-extended-writer.md`
- 扩展测试：
  - `tests/test_business_store.py`
  - `tests/test_api_business_table_sync.py`
  - `tests/test_sync_run_to_business_tables_script.py`

验证结果：
- TDD RED：新增业务表测试先因 `summary["drafts"]` 缺失、`drafts` 表无行而失败。
- 聚焦业务表回归通过：`12 passed`。
- Python 编译检查通过：`compileall app tests`。
- 全量回归通过：`177 passed`。

当前效果：
- SQLite run store 且 `XHS_AGENT_BUSINESS_TABLES_ENABLED=true` 时，成功 run 保存后会自动旁路同步 9 张业务表。
- 历史补偿脚本同步成功 run 时，也会写入可从 run record 还原出的 9 张业务表快照。
- 业务表写入继续保持旁路性质，不影响现有 run JSON、API 响应、运营记忆和发布链路。

当前限制：
- `performance_records` 当前只从 run state 中已有的 `performance_data` 写入；通过 `/performance` 更新到运营记忆后的历史表现记录，还没有自动反向同步到业务表。
- `audit_events` 是快照级审计，不是完整节点事件时间线；`run_events` 仍未接入真实节点耗时和事件流。
- 业务表只读查询入口还没做，验证仍主要依赖 SQLite 表检查和补偿脚本输出。
- 还没有把分析查询从 run JSON 切换到业务表，也没有进入 GraphRAG 入库。

下一步建议：
- 给工作台/API 增加只读查询入口，方便直接查看业务表同步结果。
- 或先补 `run_events` 节点时间线，把队列、节点耗时、失败诊断和审计事件串起来。
- 后续再评估把分析查询从 run JSON 切到业务表，并为 GraphRAG 入库准备查询层。

## 2026-06-12 业务表只读查询 API

本轮目标是在 9 张 foundation 业务表旁路写入完成后，继续补齐数据库主线的验证入口：按 `run_id` 从 SQLite 业务表直接读取结构化快照，方便确认自动同步和历史补偿是否真实落库。本轮不做前端工作台展示，不把现有 `/runs/{run_id}` 切换到业务表。

已完成：
- 新增 `app/business_queries.py`：
  - 提供 `get_business_run_snapshot(db_path, run_id)`。
  - 自动初始化 foundation schema，保证空库查询也能返回稳定结构。
  - 按 `run_id` 查询 9 张业务表：
    - `raw_notes`
    - `collection_candidates`
    - `raw_comments`
    - `analysis_reports`
    - `drafts`
    - `creator_assets`
    - `creator_notes`
    - `performance_records`
    - `audit_events`
  - 返回每张表的紧凑列表和 `counts` 汇总。
  - 对 JSON 字段做安全解析，例如 `reasons_json` -> `reasons`、`payload_json` -> `payload`。
- `app.api.get_business_run_snapshot(run_id)` 新增 API 层入口：
  - 只允许 SQLite run store。
  - JSON run store 下返回明确错误：业务表查询需要 SQLite run store。
- HTTP 新增只读路由：
  - `GET /business/runs/{run_id}`
  - 返回 `{"ok": true, "business_run": ...}`。
- 新增实施计划：
  - `docs/superpowers/plans/2026-06-12-business-table-read-api.md`
- 新增/扩展测试：
  - `tests/test_business_queries.py`
  - `tests/test_api_business_table_sync.py`
  - `tests/test_api_platform_status.py`

验证结果：
- TDD RED：新增测试先因 `app.business_queries` 模块缺失失败。
- 聚焦 API/查询测试通过：`12 passed`。
- 数据库相关回归通过：`25 passed`。
- Python 编译检查通过：`compileall app tests`。
- 全量回归通过：`182 passed`。

当前效果：
- 配置 SQLite run store 后，可以通过 `/business/runs/{run_id}` 直接查看该 run 的业务表同步快照。
- 不存在的 run 会返回空 counts 和空列表，便于排查“未同步”与“同步为空”的状态。
- JSON run store 路径保持原行为，不额外模拟业务表查询。

当前限制：
- 本轮只做 API/函数入口，没有做工作台页面展示。
- 返回的是快照级紧凑数据，不包含所有 raw JSON 明细。
- 仍未接入 `run_events` 节点时间线。
- `/performance` 写入运营记忆后的表现记录仍未自动反向同步到 `performance_records`。

下一步建议：
- 给工作台增加一个只读“业务表快照”查看入口，直接调用 `/business/runs/{run_id}`。
- 或继续补 `run_events` 节点时间线，为队列、节点耗时、失败诊断和后续监控打基础。

## 2026-06-12 run_events 节点事件时间线

本轮目标是在 foundation 业务表和只读查询 API 已经落地后，继续补齐数据库主线里的可观测性基础：把 run 生命周期事件和 local graph 节点耗时写入 `run_events`，并让 `/business/runs/{run_id}` 能直接返回这些事件。

已完成：
- 新增 `app/run_events.py`：
  - 提供 `record_run_event(db_path, ...)` 统一写入入口。
  - 自动初始化 foundation schema。
  - 写入 `queued`、`running`、`success`、`failed`、`node_finished`、`node_failed` 等事件。
  - 事件 ID 使用 run、事件类型、节点名和事件时间生成稳定 hash，同一事件时间重复写入会 upsert。
  - `payload_json` 使用结构化 JSON 存储，时间精度保留到 microseconds。
- `app.api._save_run()` 接入 run 生命周期事件：
  - SQLite run store、`XHS_AGENT_BUSINESS_TABLES_ENABLED=true`、`XHS_AGENT_DB_SCHEMA=foundation` 时记录生命周期。
  - 事件写入失败只记录 warning，不阻断 run 保存。
- `app.api._run_workflow()` 统一封装 workflow 调用：
  - local engine 会把 `run_id` 和 SQLite DB 路径传给 `run_local_graph()`。
  - langgraph engine 当前只保留 API 生命周期事件，不做节点级事件。
- `app.graph.run_local_graph()` 支持可选 `run_id` 和 `event_db_path`：
  - 每个本地节点通过 `_run_node()` 包装。
  - 成功节点记录 `node_finished`、节点名、开始/结束时间、耗时和更新字段。
  - 异常节点记录 `node_failed`、节点名、耗时和错误文本，然后继续抛出原异常。
  - 节点名显式传入，不依赖函数 `__name__`，避免测试 monkeypatch 或 lambda 破坏可观测性。
- `app.business_queries.get_business_run_snapshot()` 已把 `run_events` 纳入业务快照：
  - `/business/runs/{run_id}` 返回 `run_events` 列表。
  - `counts.run_events` 同步返回事件数量。
- 新增实施计划：
  - `docs/superpowers/plans/2026-06-12-run-events-timeline.md`
- 新增/扩展测试：
  - `tests/test_run_events.py`
  - `tests/test_graph_run_events.py`
  - `tests/test_business_queries.py`
  - `tests/test_api_business_table_sync.py`
  - `tests/test_api_platform_status.py`

验证结果：
- 聚焦事件/API 回归通过：`18 passed`。
- Python 编译检查通过：`D:\Anaconda\envs\ContentShare\python.exe -m compileall app tests`。
- 全量回归通过：`188 passed`。

当前效果：
- SQLite run store 且业务表开关启用时，run 从排队、运行到成功/失败会形成基础生命周期时间线。
- local graph 能沉淀节点级耗时，后续可用于失败诊断、慢节点定位和监控统计。
- 业务表只读 API 已能把 `run_events` 和其它业务表快照放在同一个 run 视图里返回。

当前限制：
- 节点级事件当前只覆盖 local graph；langgraph 路径暂只有 API 生命周期事件。
- `run_events` 仍是基础时间线，不包含 LLM token、采集成功率、Cookie 状态、发布状态同步延迟等聚合监控指标。
- 当前没有工作台页面展示事件时间线，仍通过 `/business/runs/{run_id}` 或 SQLite 查询验证。
- `/performance` 写入运营记忆后的表现记录仍未自动反向同步到 `performance_records`。

下一步建议：
- 给工作台增加只读“业务表快照/事件时间线”面板，直接展示 `/business/runs/{run_id}` 的 `run_events`。
- 后续补队列持久化恢复、任务超时/取消/重试事件，把 `run_events` 用作监控和失败诊断基础。
- 继续评估 `/performance` 到 `performance_records` 的反向同步，完善表现链路闭环。

## 2026-06-12 SQLite 队列事件可观测性

本轮目标是在数据库基础主线阶段性收口后，转入队列/worker 工程化主线：把 SQLite 队列关键状态变化接入 `run_events`，让任务排队、领取、stale 恢复、重试、成功和终态失败可以和 run 生命周期、local graph 节点耗时放在同一条时间线里诊断。

已完成：
- 新增 `app/queue_events.py`：
  - 提供 `record_queue_event()`，把队列语义转换为 `record_run_event()`。
  - 提供 `record_queue_event_safely()`，事件写入失败只记录 warning，不阻断队列状态变化。
  - 统一队列事件 payload：`worker_id`、`attempts`、`max_attempts`、前置锁信息和错误文本。
- `app.run_queue.SQLiteRunQueue` 新增可选 `event_db_path`：
  - 默认不记录事件，保持直接使用队列类的旧行为。
  - 开启后记录 `queue_enqueued`。
  - worker 正常领取 queued job 时记录 `queue_claimed`。
  - stale running job 被重新领取时记录 `queue_reclaimed`。
  - job 失败但未达到最大尝试次数时记录 `queue_requeued`。
  - job 成功时记录 `queue_succeeded`。
  - job 达到最大尝试次数或队列记录缺失时记录 `queue_failed`。
- `SQLiteRunQueue.status()` 增加 `jobs` 明细：
  - 返回 active/failed job 的 `run_id`、`status`、`attempts`、`max_attempts`、`locked_by`、`last_error`。
  - 现有 `queued_count`、`running_count`、`failed_count` 和 ID 列表保持不变。
- `app.api._run_queue_service()` 接入事件 DB：
  - 只有 SQLite run store、foundation schema、`XHS_AGENT_BUSINESS_TABLES_ENABLED=true` 同时满足时，才给 SQLite queue 传入 run DB 路径。
  - 如果 queue DB 和 run DB 分离，事件仍写入 run DB，便于 `/business/runs/{run_id}` 统一查询。
- `scripts.run_worker.run_once()` 不需要改接口；它调用 `mark_succeeded()` / `mark_failed()` 时会自然触发队列事件。
- `.env.example` 补充说明：队列事件复用现有业务表开关，不新增独立开关。
- 新增实施计划：
  - `docs/superpowers/plans/2026-06-12-sqlite-queue-events-observability.md`
- 新增/扩展测试：
  - `tests/test_queue_events.py`
  - `tests/test_sqlite_run_queue.py`
  - `tests/test_api_run_queue_selection.py`
  - `tests/test_run_worker.py`

验证结果：
- TDD RED：新增队列事件测试先因 `app.queue_events` 缺失失败。
- 队列/worker 聚焦回归通过：`20 passed`。
- 队列 + 事件 + 业务查询聚焦回归通过：`32 passed`。
- Python 编译检查通过：`D:\Anaconda\envs\ContentShare\python.exe -m compileall app scripts tests`。
- 全量回归通过：`194 passed`。

当前效果：
- SQLite queue 的关键状态变化现在能进入 `run_events`，和 run 生命周期、local graph 节点事件放在同一个业务快照里查看。
- `/queue` 状态结果在 SQLite backend 下包含更细的 job 明细，便于排查卡住、重试和终态失败任务。
- worker 进程不需要了解事件表；它只调用队列状态机，事件由队列模块旁路记录。

当前限制：
- 本轮只做 SQLite queue 的可观测性，不做任务取消、业务超时中断、优先级队列或多队列拆分。
- local in-process queue 仍只返回基础状态，不记录队列事件。
- 真实 creator 发布类副作用任务不会因为本轮改动自动重试；本轮只记录队列重试状态。
- 工作台尚未展示 queue events，需要后续通过业务快照/事件时间线面板呈现。

下一步建议：
- 给工作台增加只读“事件时间线/队列诊断”面板，展示 run 生命周期、queue events 和 graph 节点耗时。
- 或继续做队列工程化增强：任务取消、超时标记、running 任务恢复策略和 worker 心跳。
- 后续再补 `/performance` 到 `performance_records` 的反向同步。

## 2026-06-12 工作台事件时间线与任务控制

本轮目标是把上一轮留下的两个工程化方向一起推进：工作台只读“事件时间线/队列诊断”面板，以及任务取消、超时标记和恢复保护策略。实现仍基于现有 SQLite queue 和 `run_events`，不引入新队列技术。

已完成：
- `SQLiteRunQueue` 新增显式控制方法：
  - `cancel(run_id, worker_id=None, reason=...)`
  - `mark_timed_out(run_id, worker_id=None, reason=...)`
- 队列状态新增终态：
  - `cancelled`
  - `timed_out`
- 队列事件新增：
  - `queue_cancelled`
  - `queue_timed_out`
- `/queue` 在 SQLite backend 下新增诊断字段：
  - `cancelled_count`
  - `cancelled_run_ids`
  - `timed_out_count`
  - `timed_out_run_ids`
  - `jobs` 明细继续包含 attempts、max_attempts、locked_by、last_error。
- API 新增任务控制函数：
  - `cancel_run(run_id, payload)`
  - `timeout_run(run_id, payload)`
- HTTP 新增显式控制路由：
  - `POST /runs/{run_id}/cancel`
  - `POST /runs/{run_id}/timeout`
- run lifecycle 事件扩展支持：
  - `cancelled`
  - `timed_out`
- `_finish_run()` 增加保护：如果 worker 后续结束时发现 run 已被标记为 `cancelled` 或 `timed_out`，不会再覆盖成 success/failed。
- 工作台任务结果区新增只读 `runTimeline`：
  - 调用 `/business/runs/{run_id}`。
  - 展示 run lifecycle、queue events 和 local graph node events。
  - SQLite/业务表未启用时显示“未启用”提示，不影响现有 `/runs/{run_id}`。
- 工作台队列区新增 job 诊断：
  - 展示 job 状态、尝试次数、worker、last_error。
  - 对非终态 job 提供“取消”和“标记超时”按钮。
- 新增实施计划：
  - `docs/superpowers/plans/2026-06-12-workbench-timeline-and-run-control.md`
- 新增/扩展测试：
  - `tests/test_api_run_control.py`
  - `tests/test_workbench_event_timeline_static.py`
  - `tests/test_sqlite_run_queue.py`

验证结果：
- TDD RED：新增测试先因 `SQLiteRunQueue.cancel()`、`mark_timed_out()`、`api.cancel_run()`、`api.timeout_run()`、前端 `runTimeline` 缺失而失败。
- 队列控制聚焦回归通过：`12 passed`。
- API 控制 + 队列聚焦回归通过：`15 passed`。
- 前端静态和诊断回归通过：`8 passed`。
- 综合聚焦回归通过：`35 passed`。
- `node --check app/static/app.js` 通过。

当前效果：
- 对 queued/running 任务可以通过 API 或工作台显式取消。
- 对 queued/running 任务可以通过 API 或工作台显式标记超时。
- 取消/超时会同时写 run record、SQLite queue job 和 `run_events`。
- 工作台现在能直接看到所选 run 的结构化事件时间线。
- worker 不需要知道前端控制逻辑；它完成时会尊重已取消/已超时 run，不再覆盖终态。

当前限制：
- 本轮不强杀正在运行的 Python 线程。
- 本轮不撤销或中断已经发出的真实 creator 平台请求。
- 本轮超时是显式标记，不是后台 watchdog 自动扫描。
- local in-process queue 没有 queue job 表，因此工作台队列诊断明细主要服务 SQLite backend。

下一步建议：
- 增加 worker 心跳和 watchdog：自动发现长时间 running 且无心跳的任务，按策略标记 stale 或 timed_out。
- 增加更完整的运行配置检查，提示 SQLite queue + run store + business table events 的组合状态。
- 继续补 `/performance` 到 `performance_records` 的反向同步，完善表现链路数据沉淀。

## 2026-06-12 工作台事件时间线排序与时区显示修复
本轮目标是处理工作台浏览器反馈：“事件时间线是不是不太对”。排查后确认问题有两层：队列事件由 `run_events` 以 UTC `+00:00` 写入，run 生命周期事件使用本地时间字符串；`/business/runs/{run_id}` 原先按原始 `created_at` 文本排序，前端也直接展示原始时间，导致同一条时间线里既有 `15:19:48+00:00`，又有本地 `23:19:48`，顺序和观感都不对。

已完成：
- `app.business_queries` 对 `run_events` 增加读出归一排序：
  - 带时区时间转换为本地时间。
  - 按秒级时间桶排序。
  - 同一秒内保留 SQLite `rowid` 写入顺序，避免旧数据因为生命周期事件只有秒级精度而错排。
  - `_rowid` 仅用于内部排序，不暴露给 API 响应。
- `app/static/app.js` 增强 `compactTime()`：
  - 带时区 ISO 时间显示成本地 `YYYY-MM-DD HH:mm:ss`。
  - 无法解析的旧字符串仍回退为原始文本替换 `T`，避免破坏未知格式。
- `app/static/app.js` 增加前端时间线本地排序：
  - 即使 8024 上的 Python API 进程尚未重启、仍返回旧顺序，工作台也会按时间桶和事件阶段重新排序。
  - 当前浏览器验证顺序为：进入队列 -> 队列入队 -> 队列领取 -> 开始运行 -> 运行成功 -> 队列成功。
- 扩展测试：
  - `tests/test_business_queries.py` 覆盖 UTC 队列事件和本地生命周期事件混排时的快照排序。
  - `tests/test_workbench_event_timeline_static.py` 覆盖前端本地时间显示和旧 API 顺序下的前端排序。

验证结果：
- TDD RED：新增两个定点测试先按预期失败。
- 定点测试修复后通过。
- 相关回归通过：`38 passed`。
- JS 语法检查通过：`node --check app/static/app.js`。
- 浏览器复查通过：当前 `http://127.0.0.1:8024/` 的 `run_46dc74c9c7b1` 时间线不再显示 `+00:00` 原文，顺序已修正。

当前效果：
- 工作台事件时间线现在对用户显示本地秒级时间，避免 UTC 原文造成“早 8 小时”的误解。
- 历史 SQLite 数据无需迁移即可被读出和展示为合理顺序。
- 后端 API 重启后会返回更合理的事件顺序；前端也能兼容尚未重启的旧 API 进程返回。

当前限制：
- 当前没有统一改造所有写入端的时间来源，系统内部仍可能存在 UTC aware 和本地 naive 字符串混用；本轮通过读出归一和展示归一解决用户可见问题。
- 生命周期事件秒级精度会导致同一秒内只能依赖写入顺序和事件阶段排序，后续可考虑统一事件写入精度到 microseconds。

下一步建议：
- 继续主线时，优先做 worker 心跳 + watchdog 自动超时扫描。
- 同时增强运行配置检查，提示 SQLite run store、queue、business tables 和 events 的组合是否完整。
- 后续可统一事件写入时间规范，减少读出层兼容逻辑。

## 2026-06-13 worker 心跳与 watchdog 自动超时扫描

本轮目标是承接队列/worker 工程化主线，在现有 SQLite queue、`run_events` 和工作台事件时间线基础上，补齐 worker 心跳信号和显式 watchdog 扫描入口，让长时间 running 且心跳过期的任务可以自动标记为 `timed_out`。

已完成：
- 新增设计文档：
  - `docs/superpowers/specs/2026-06-13-worker-heartbeat-watchdog-design.md`
- 新增实施计划：
  - `docs/superpowers/plans/2026-06-13-worker-heartbeat-watchdog.md`
- `SQLiteRunQueue` 的 `run_queue_jobs` 增加 `heartbeat_at` 字段：
  - 新库建表时直接包含字段。
  - 旧库通过 `_init_db()` 幂等补列。
  - `/queue` 的 SQLite job 明细会返回 `heartbeat_at`。
- `claim_next()` 领取任务时会初始化 `heartbeat_at`。
- 新增 `SQLiteRunQueue.heartbeat(run_id, worker_id)`：
  - 只更新 `running` 且 `locked_by` 匹配的 job。
  - 更新 `heartbeat_at` 和 `updated_at`。
  - 写入 `queue_heartbeat` 事件。
- 新增 `SQLiteRunQueue.mark_stale_running_as_timed_out(...)`：
  - 通过 `heartbeat_at` 判断过期。
  - 历史 running job 没有 heartbeat 时回退到 `locked_at`。
  - 复用现有 `mark_timed_out()`，因此会写入 `queue_timed_out` 事件。
- `scripts/run_worker.py` 更新：
  - `run_once()` 领取任务后会对支持心跳的队列写一次 heartbeat。
  - 新增 `run_watchdog_once()`。
  - CLI 新增 `--watchdog-once`，用于显式执行一次 watchdog 扫描。
- 配置新增：
  - `XHS_AGENT_QUEUE_HEARTBEAT_TIMEOUT_SECONDS=1800`
  - `Settings.queue_heartbeat_timeout_seconds`
- `scripts/check_runtime_config.py --profile sqlite-worker` 会检查 heartbeat timeout 是否为正数。
- 工作台事件时间线新增 `queue_heartbeat` 标签和排序：
  - 显示为“队列心跳”。
  - 排序在“队列领取”和“开始运行”之间。

验证结果：
- TDD RED：新增测试先因缺少 `heartbeat_at`、`heartbeat()`、watchdog 方法、worker 入口、配置检查和前端事件映射而失败。
- 定点 RED->GREEN 通过：`8 passed`。
- 相关聚焦回归通过：`39 passed`。
- `node --check app/static/app.js` 通过。
- Python 编译检查通过：`D:\Anaconda\envs\ContentShare\python.exe -m compileall app scripts tests`。
- 全量回归通过：`214 passed`。

当前效果：
- SQLite worker 领取任务后会留下可查询的心跳时间。
- watchdog 可以显式扫描并自动把心跳过期的 running job 标记为 `timed_out`。
- 队列心跳和自动超时可以进入现有 `run_events` 时间线，并在工作台中以中文事件展示。
- 配置检查可以发现 heartbeat timeout 被禁用或配置异常。

当前限制：
- 本轮仍不强杀正在运行的 Python 线程。
- 本轮不撤销或中断已经发出的真实 creator 平台请求。
- 当前 worker 只在领取任务后写一次心跳；长任务执行期间的周期心跳线程尚未实现。
- watchdog 是显式 `--watchdog-once` 扫描入口，还不是常驻后台调度。

下一步建议：
- 增加 worker 周期心跳线程，让长时间执行的采集/LLM/发布任务能持续刷新 `heartbeat_at`。
- 增加常驻 watchdog 或启动模板中的定期调用策略。
- 继续补运行配置组合检查，提示 SQLite run store、queue、business tables、events 和 watchdog 是否完整启用。
- 后续再补 `/performance` 到 `performance_records` 的反向同步。

## 2026-06-13 worker 周期心跳与 watchdog loop

本轮目标是在上一轮 worker 心跳/watchdog 初版基础上，补齐长任务执行期间的周期 heartbeat 和常驻 watchdog 扫描入口，让 SQLite worker 工程化能力更接近长期运行形态。

已完成：
- 新增设计文档：
  - `docs/superpowers/specs/2026-06-13-worker-periodic-heartbeat-watchdog-loop-design.md`
- 新增实施计划：
  - `docs/superpowers/plans/2026-06-13-worker-periodic-heartbeat-watchdog-loop.md`
- `scripts/run_worker.py` 的 `run_once()` 新增 `heartbeat_interval_seconds`：
  - 领取任务后仍立即写一次 heartbeat。
  - 当 interval 大于 0 时，启动 daemon 心跳线程。
  - 任务结束或异常后停止心跳线程。
  - 心跳异常只记录 warning，不改变任务主流程。
- 新增 `run_watchdog_loop()`：
  - 循环调用 `run_watchdog_once()`。
  - 支持测试用 `scan_limit`。
  - CLI 新增 `--watchdog-loop`。
- 配置新增：
  - `XHS_AGENT_QUEUE_HEARTBEAT_INTERVAL_SECONDS=30`
  - `Settings.queue_heartbeat_interval_seconds`
- `scripts/check_runtime_config.py --profile sqlite-worker` 增强：
  - 检查 heartbeat interval 为正数。
  - 检查 heartbeat interval 小于 heartbeat timeout。
  - 提示 queue event timeline 是否完整启用。
- `scripts/start_sqlite_worker.ps1` 增强：
  - 新增 `HeartbeatIntervalSeconds`。
  - 新增 `HeartbeatTimeoutSeconds`。
  - 新增 `-Watchdog` 模式，启动 `run_worker.py --watchdog-loop`。

验证结果：
- TDD RED：新增测试先因 `run_once()` 不支持周期心跳、`run_watchdog_loop()` 缺失、配置检查缺 interval/events 组合、启动模板缺 watchdog loop 而失败。
- 定点 RED->GREEN 通过：`6 passed`。
- 聚焦回归通过：`25 passed`。

当前效果：
- 长任务执行期间 worker 可以持续刷新 `heartbeat_at`。
- watchdog 可以作为常驻进程持续扫描 stale running job。
- SQLite worker 启动模板可以一键启动普通 worker 或 watchdog。
- 配置检查能更早发现 interval/timeout 配置不合理和事件时间线未启用。

当前限制：
- 周期 heartbeat 仍是 worker 进程内 daemon 线程，不是跨进程健康探针。
- watchdog 仍只标记本地 run/queue/event 状态，不强杀线程，也不撤销真实平台请求。
- 启动模板提供入口，但还没有把 API、worker、watchdog 组合成统一一键编排脚本。

下一步建议：
- 增加完整运行配置组合检查或 smoke 脚本，一次性验证 SQLite API、worker、watchdog、business tables、events 是否联通。
- 继续补 `/performance` 到 `performance_records` 的反向同步，收口表现数据闭环。
- 在下一次真实端到端小流量验证前，先使用 mock + SQLite + watchdog 模式跑一条任务，确认事件时间线完整。

## 2026-06-13 SQLite stack smoke 组合检查

本轮目标是提高日常开发效率：新增一个一键 smoke 检查，在 mock 模式下验证 SQLite API、SQLite queue、worker、watchdog、business tables 和 run_events 是否完整联通。

已完成：
- 新增设计文档：
  - `docs/superpowers/specs/2026-06-13-sqlite-stack-smoke-design.md`
- 新增实施计划：
  - `docs/superpowers/plans/2026-06-13-sqlite-stack-smoke.md`
- 新增 `scripts/check_sqlite_stack.py`：
  - 临时设置 SQLite run store、SQLite queue、SQLite memory、foundation schema 和 business tables enabled。
  - 强制使用 `COLLECTOR_MODE=mock`、`LLM_MODEL_NAME=mock`、`CREATOR_MODE=mock`。
  - 调用 `api.submit_run()` 提交异步 run。
  - 调用 `run_worker.run_once()` 处理 run。
  - 调用 `run_worker.run_watchdog_once()` 验证 watchdog 入口。
  - 调用 `api.get_business_run_snapshot()` 验证业务表和事件时间线。
  - 输出 JSON 摘要，包含 run、queue、watchdog、business_run、event_types 和 checks。
  - 执行结束后恢复原环境变量并重置 API/operation memory 单例。
- 新增 `tests/test_check_sqlite_stack.py` 覆盖 smoke 成功、环境恢复和 CLI 输出。

验证结果：
- TDD RED：新增测试先因 `scripts.check_sqlite_stack` 缺失失败。
- 定点 RED->GREEN 通过：`tests/test_check_sqlite_stack.py` 为 `4 passed`。
- 重点组合验证通过：`tests/test_check_sqlite_stack.py tests/test_sqlite_queue_worker_integration.py tests/test_run_worker.py tests/test_runtime_config_check.py` 为 `26 passed`。
- CLI smoke 通过：`scripts/check_sqlite_stack.py` 输出 `"ok": true`，run 最终 `status=success`，queue 清空，watchdog 未误标超时。
- 编译检查通过：`python -m compileall app scripts tests`。
- 全量测试通过：`224 passed`。

当前效果：
- 现在可以用一条命令快速验证 mock + SQLite 工程底座是否可用：
  - `D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_sqlite_stack.py`
- 默认使用 `data/` 下被 Git 忽略的唯一 smoke DB 文件，便于排查。
- 传入 `--db-path` 时可以指定 DB 位置。

当前限制：
- 本脚本不启动真实 HTTP API 服务，不做端口级检查。
- 本脚本不访问真实小红书平台，不验证真实 Cookie。
- 本脚本只跑一次 worker 和一次 watchdog，不替代长时间稳定性测试。

下一步建议：
- 将该 smoke 纳入每轮开发完成前的固定验证组合。
- 继续补 `/performance` 到 `performance_records` 的反向同步，收口表现数据闭环。
- 之后用真实 Cookie 做小流量端到端复验前，先运行本 smoke 确认工程底座健康。

## 2026-06-13 /performance 到 performance_records 反向同步

本轮目标是收口表现数据闭环：`/performance` 人工录入表现后，运营记忆、SQLite run state 和 `performance_records` 能保持一致。

已完成：
- 新增实施计划：
  - `docs/superpowers/plans/2026-06-13-performance-business-sync.md`
- `/performance` 保持现有入参和运营记忆更新行为，新增返回 `business_sync` 摘要。
- 非 SQLite run store、业务表未启用或找不到匹配 success run 时，返回 `business_sync.status=skipped`，不影响运营记忆更新。
- SQLite run store + foundation business tables 启用时，会按 `operation_record_id`、`creator_note_id`、`post_id` 查找匹配的 success run。
- 匹配成功后，把更新后的表现数据、表现分、复盘摘要和下一步建议合并回 run state。
- 复用 `_save_run()` 和 `sync_run_business_tables()` 刷新 `performance_records`，避免新增旁路写表逻辑。
- 同步异常返回 `business_sync.status=failed`，错误信息复用现有脱敏逻辑。
- `/runs/{run_id}` 的 summary 现在包含 `performance_data` 和 `performance_score`，便于直接查看表现摘要。

验证结果：
- TDD RED：`tests/test_creator_note_performance_sync.py` 先因 `business_sync` 缺失出现 `4 failed, 4 passed`。
- 定点 RED->GREEN 通过：`tests/test_creator_note_performance_sync.py` 为 `8 passed`。
- 相关回归通过：`tests/test_creator_note_performance_sync.py tests/test_api_business_table_sync.py tests/test_business_store.py` 为 `21 passed`。
- SQLite stack smoke 通过：`scripts/check_sqlite_stack.py` 输出 `"ok": true`，run 最终 `status=success`，queue 清空，watchdog 未误标超时，业务快照包含 `performance_records`。
- 编译检查通过：`python -m compileall app scripts tests`。
- 全量测试通过：`227 passed`。

当前效果：
- 真实或 mock 发布后的运营记忆，只要能通过 `creator_note_id`、`post_id` 或 `operation_record_id` 匹配到 SQLite success run，后续人工录入表现会自动刷新 run state 和业务表快照。
- JSON/local 模式保持原有主流程，只额外返回明确的 `business_sync.status=skipped`。

当前限制：
- 本轮不自动抓取小红书平台指标，表现数据仍来自人工录入。
- 本轮不做历史数据批量迁移，历史记录可在后续按需用脚本补偿。
- 匹配 run 时当前扫描最近 500 条 run，足够支撑现阶段工作台和小流量验证，历史大规模迁移后可再优化查询。

下一步建议：
- 在真实 Cookie 小流量复验前，用当前 SQLite stack smoke 加一条真实发布记录验证表现闭环。
- 后续可考虑做历史 operation memory 表现记录到 `performance_records` 的一次性补偿脚本。

## 2026-06-13 表现闭环真实检查与历史补偿

本轮目标是继续收口表现数据闭环，把上一轮手工确认过的真实 `creator_note_id -> /performance -> performance_records` 闭环工具化，并补上历史 operation memory 表现记录的补偿入口。

已完成：
- 新增设计文档：
  - `docs/superpowers/specs/2026-06-13-performance-backfill-and-real-check-design.md`
- 新增实施计划：
  - `docs/superpowers/plans/2026-06-13-performance-backfill-and-real-check.md`
- 新增 `scripts/check_real_performance_closure.py`：
  - 只读调用 creator 作品列表，不触发发布、修改、删除或重试。
  - 将指定 JSON run 导入临时 SQLite run store。
  - 从 run state 登记 operation memory，并把 `operation_record_id` 回写到临时 run state。
  - 调用现有 `api.record_performance()` 验证 run state、operation memory 和 `performance_records` 是否一致。
  - 支持 `--run-id`、`--creator-note-id`、`--db-path`、`--runs-dir`、`--limit`、`--use-platform-metrics` 和手工指标参数。
  - 输出结构化 JSON，包括 `ok`、`platform_note`、`business_sync`、`business_counts`、`performance_record` 和 `checks`。
- 新增 `scripts/backfill_performance_records.py`：
  - 扫描当前 operation memory 中 `status=performance_recorded` 且有表现数据的记录。
  - 默认 dry-run，只列出候选，不写 run store 或业务表。
  - `--apply` 时复用 `api.record_performance()` 补偿 run state 与 `performance_records`，不新增旁路 SQL。
  - 支持 `--record-id`、`--creator-note-id`、`--post-id`、`--limit` 过滤。
  - 多次执行保持幂等，同一 run/operation/creator note 只更新同一条 `performance_records`。
- 新增测试：
  - `tests/test_check_real_performance_closure.py`
  - `tests/test_backfill_performance_records.py`

已验证：
- TDD RED：真实检查脚本测试先因 `scripts.check_real_performance_closure` 缺失失败；CLI `--runs-dir` 测试先因参数缺失失败。
- TDD RED：历史补偿脚本测试先因 `scripts.backfill_performance_records` 缺失失败；apply/幂等测试先因 apply 未实现失败；`limit=0` 边界测试先因误收候选失败。
- 定点新测试通过：`D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_check_real_performance_closure.py tests/test_backfill_performance_records.py -q` -> `7 passed`。
- 相关回归通过：`D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_check_real_performance_closure.py tests/test_backfill_performance_records.py tests/test_creator_note_performance_sync.py tests/test_api_business_table_sync.py tests/test_business_store.py tests/test_sync_run_to_business_tables_script.py -q` -> `31 passed`。
- SQLite stack smoke 通过：`D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_sqlite_stack.py` -> `"ok": true`。
- 编译检查通过：`D:\Anaconda\envs\ContentShare\python.exe -m compileall app scripts tests`。
- 全量测试通过：`D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` -> `234 passed`。

当前效果：
- 下一次真实 Cookie 小流量复验前，可以先用 `check_real_performance_closure.py` 复跑指定真实 run 和 creator note 的本地闭环。
- 历史已经人工录入表现的 operation memory 记录，可以用 `backfill_performance_records.py --apply` 补回 SQLite run state 和 `performance_records`。

当前限制：
- 真实检查脚本只读 creator 作品列表，不自动抓取后台指标，不做真实发布。
- 补偿脚本依赖当前 `/performance` 匹配逻辑；找不到 success run 时会跳过并保留原因。
- 本轮尚未执行真实网络只读验证；如沙箱代理阻断，需要提权运行真实 creator 列表检查。

下一步建议：
- 完成本轮全量验证和提交后，用真实 `run_fda76a64a278` 与 `creator_note_id=6a2bce0b000000003502c564` 运行一次只读闭环工具，确认工具化脚本也能复现上一轮手工闭环。
- 后续再评估是否做平台指标自动抓取、GraphRAG 入库和历史大规模迁移。

## 2026-06-13 LangGraph-first 全盘运行时整改

本轮目标是把默认主路径收敛为 LangGraph-first runtime，让人工审核、审核通过/驳回、发布、creator 私密发布、复盘、写运营记忆和节点事件都回到同一个 LangGraph thread 控制，`local` executor 仅保留为显式兼容路径。

已完成：
- 新增 SQLite-backed LangGraph checkpoint snapshot 封装，`thread_id` 使用 `run_id`。
- 新增 `app.langgraph_runtime` 边界，提供 run、resume、thread config 和 checkpoint state 更新能力。
- `human_review` 改成真正的 LangGraph interrupt/resume 节点。
- 驳回和 creator 发布迁入图内节点：`reject_publish`、`creator_publish_or_skip`。
- API 默认使用 LangGraph runtime；`approve_run()` 和 `reject_run()` 通过同一 thread resume，不再手动拼接发布、复盘和写记忆节点。
- worker 遇到 `waiting_review` 会保存 run 并释放队列任务，不再把等待人工审核当成 worker failure。
- LangGraph 主路径会写入节点级 run events，包含节点完成和 human review interrupt。
- CLI/API 默认 engine 收敛为 `langgraph`，`engine=local` 仅保留为显式兼容。
- 收尾修复：
  - local executor 使用本地审核兼容函数，避免在非 LangGraph runnable 上下文调用 `interrupt()`。
  - creator 素材绑定后会同步 waiting_review LangGraph checkpoint，确保审核通过 resume 时图内 creator 节点能读取已绑定图片文件。

验证结果：
- 编译检查通过：`D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm`。
- 相关回归通过：`tests/test_creator_asset_binding.py tests/test_api_creator_review_publish.py tests/test_api_langgraph_resume.py tests/test_api_engine_defaults.py tests/test_api_run_control.py` -> `24 passed`。
- SQLite smoke 回归通过：`tests/test_check_sqlite_stack.py` -> `4 passed`。
- 全量测试通过：`D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` -> `246 passed`。
- API smoke 通过：启动本地 API 后运行 `scripts/check_api_run.py --engine langgraph --collect-limit 1 --timeout 180`，run `run_71943ff2a887` 最终 `status=success`，`summary.run_status=waiting_review`。

当前效果：
- 默认工作台/API/worker 主链路已经进入 LangGraph-first 形态。
- 人工审核暂停和恢复依赖持久 checkpoint，而不是 API 层临时 state 拼接。
- creator 图片素材绑定、审核确认和图内私密发布之间的 state 现在可以通过 checkpoint 串起来。
- RunStore、业务表和前端仍保留兼容投影，便于工作台查询。

当前限制：
- `run_local_graph()` 仍是兼容执行器，不再作为主路径新增能力。
- 当前 SQLite checkpoint 是项目内 snapshot wrapper，后续如果 LangGraph 官方 SQLite saver 稳定可评估替换。
- 本轮没有新增真实公开发布、视频发布、定时发布、平台指标自动抓取、GraphRAG 入库或阶段二软广/达人能力。

下一步建议：
- 先提交本轮 LangGraph-first runtime 迁移。
- 然后用真实 Cookie 做一条小流量端到端复验：waiting_review -> 绑定真实图片 -> creator 私密发布 -> 作品列表只读同步 -> `/performance` 回填。
- 真实主链稳定后，再进入 M5 GraphRAG 运营记忆增强；阶段二软广和达人能力继续后置。

## 2026-06-13 LangGraph runtime 边界清理

本轮目标是在 LangGraph-first 主流程合并后，先做一轮保守清理，删除 API 层明显无用的迁移残留，同时保留有用的显式兼容路径。

已完成：
- 新增清理设计与计划文档：
  - `docs/superpowers/specs/2026-06-13-langgraph-runtime-boundary-cleanup-design.md`
  - `docs/superpowers/plans/2026-06-13-langgraph-runtime-boundary-cleanup.md`
- 删除 `app/api.py` 中 `approve_run()` / `reject_run()` return 后不可达的旧手动拼流程代码。
- 删除只服务旧流程的 API 层 creator 发布 helper。
- 删除 API 对 `publish_node`、`review_performance`、`write_operation_memory` 和 `run_langgraph` 的无用 import。
- 测试 fixture 改为直接 patch `nodes.publish_node.OUTPUT_DIR`，不再要求 `app.api` 暴露 publish node 模块。
- 新增边界测试，锁定 `app.api` 不再暴露 legacy direct creator publish helper。

保留：
- `run_local_graph()` 和显式 `engine=local` 兼容路径继续保留。
- creator 发布的有效实现保留在 `platforms/creator_publish_flow.py` 和 `nodes/creator_publish_node.py`。
- API 层仍保留 creator 素材绑定、payload 校验和错误脱敏等有用边界。

验证结果：
- RED：`test_api_no_longer_exposes_legacy_direct_creator_publish_helpers` 先因 legacy helper 仍存在失败。
- GREEN：`tests/test_api_langgraph_resume.py` -> `4 passed`。
- 相关回归：`tests/test_api_creator_review_publish.py tests/test_creator_asset_binding.py tests/test_creator_note_performance_sync.py tests/test_api_langgraph_resume.py` -> `27 passed`。
- 编译检查通过：`D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm`。
- 全量测试通过：`D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` -> `247 passed`。

当前限制：
- 本轮只清理 API 层明显死代码，没有拆分 `app/api.py` 大文件。
- 旧 worktree 目录仍需要单独清理或确认。
- 真实平台小流量端到端复验仍未执行。
