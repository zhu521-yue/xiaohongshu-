# LangGraph-first 全盘运行时整改设计

## 背景

当前项目已经具备内容生成、采集、审核、发布、复盘、运营记忆、业务表、API 工作台、SQLite 队列和 worker 等能力。但流程控制权逐步散落到了 API、RunStore、SQLite 队列、人工审核接口和手写 local executor 中。

这导致 `engine=langgraph` 虽然存在，却没有真正成为系统主干。典型表现是：

1. `run_langgraph()` 只是一次性 `invoke()`，没有稳定 thread、checkpoint、interrupt 和 resume。
2. 人工审核后，API 手动调用发布、creator 发布、复盘、写记忆等节点，绕过了 LangGraph 的图恢复。
3. 节点级运行事件主要服务 local executor，LangGraph 路径缺少等价观测。
4. worker 目前是任务执行外壳，但业务流程边界仍由 API 拼接。
5. RunStore 和业务表承担了过多流程状态职责，而不是只做查询投影和兼容存储。

这次整改的目标不是“让代码看起来用了 LangGraph”，而是把项目改成真正的 LangGraph-first 运行时架构。

## 总目标

全盘整改后的系统应满足：

- LangGraph 是唯一的业务流程主干，负责状态流转、分支、暂停、恢复、发布、复盘、写记忆和错误路径。
- API 只负责 HTTP 入口、参数校验、人工操作输入、结果查询和前端兼容。
- worker 只负责 claim 任务、启动或恢复 LangGraph thread、记录 worker 级结果。
- RunStore 只保存 API 兼容 run record 和前端查询摘要，不再决定流程下一步。
- 业务表只做 LangGraph 最终状态和关键中间产物的查询投影。
- `run_local_graph()` 退出主路径，仅保留为兼容测试工具，后续可删除。
- 默认引擎从“local/langgraph 双轨”收敛为 LangGraph 主轨。

## 非目标

本次全盘整改不引入新的外部技术栈：

- 不引入 Redis、Celery、PostgreSQL 或新的服务进程。
- 不实现 GraphRAG 的真实向量检索。
- 不实现阶段二软广、达人匹配、千帆和蒲公英正式接入。
- 不重做前端视觉设计。
- 不重写 Spider_XHS 和 creator 底层适配器。

这些能力应在 LangGraph-first 主干稳定后再扩展。

## 核心架构

整改后的职责边界如下：

```text
API / Workbench
  -> 创建 run、提交人工审核结果、读取 run record

SQLiteRunQueue / worker
  -> claim run、调用 LangGraph runtime、处理 worker heartbeat 和重试

LangGraph runtime
  -> graph thread、checkpoint、interrupt、resume、stream events

Nodes / Routers
  -> 采集、分析、生成、合规、审核、发布、creator 平台动作、复盘、写记忆

RunStore
  -> 保存前端可读 run record，是 LangGraph state 的投影

Business tables
  -> 保存结构化查询投影，不拥有流程控制权
```

## 主流程设计

### LangGraph 主图

主图应覆盖完整闭环：

```text
START
-> load_user_input
-> check_account_stage
-> retrieve_graphrag_memory
-> analyze_topic_and_pain_points
-> decide_content_strategy
-> route_content_format
   -> generate_image_text
   -> generate_video_script
-> check_compliance
-> route_compliance_result
   -> revise_content_for_compliance
   -> human_review
   -> stop_publish
-> human_review interrupt/resume
-> route_human_review
   -> publish_or_schedule
   -> reject_publish
-> creator_publish_or_skip
-> review_performance
-> write_operation_memory
-> END
```

`creator_publish_or_skip` 成为图内节点。它读取人工审核时传入的 creator 发布选项，决定是否调用 creator 适配器。API 不再直接调用 creator 发布。

`reject_publish` 成为图内节点。人工审核驳回时，图内写入 `publish_status=rejected`、`operation_memory_written=False`、`next_action` 和驳回摘要，然后结束。

### 状态模型

`XHSState` 继续作为图状态合同，但需要补齐运行时字段：

- `run_id`
- `run_status`
- `review_action`
- `review_required`
- `review_interrupt_payload`
- `creator_publish_requested`
- `creator_publish_private`
- `creator_human_confirmed`
- `creator_publish_result`
- `failure_category`
- `failure_category_label`
- `node_events`

`run_status` 使用清晰枚举：

- `queued`
- `running`
- `waiting_review`
- `rejected`
- `published`
- `failed`
- `cancelled`
- `timed_out`

旧的 API `status=success` 仅作为兼容输出使用，内部主状态以 `run_status` 为准。

### checkpointer

LangGraph 必须使用持久 checkpointer。优先使用项目已有 SQLite 数据库文件，不新引入外部服务。

设计要求：

- `thread_id = run_id`
- 所有 `engine=langgraph` run 必须带 thread_id
- worker 启动图时写入 checkpoint
- human interrupt 后 checkpoint 保存等待审核状态
- approve/reject 通过同一 thread resume

如果当前安装的 LangGraph 版本没有直接可用的 SQLite checkpointer，实施时应先在项目内封装一个 `app/langgraph_runtime.py` 边界，内部可先使用 LangGraph 官方可用 saver；但外部 API 不依赖具体 saver 类型，后续可替换为 SQLite saver。

## API 改造

### 提交 run

`submit_run()` 仍创建 run record 并入队。

`create_run()` 同步执行时也必须走 LangGraph runtime，不再直接使用手写 local executor。

`_run_workflow()` 对默认引擎只调用 LangGraph runtime。`engine=local` 只保留给显式调试用途。

### 审核通过

`approve_run()` 的职责变为：

1. 校验 run 存在且处于 `waiting_review`。
2. 校验 creator 发布参数。
3. 构造 resume payload。
4. 调用 `resume_langgraph(run_id, payload)`。
5. 将 LangGraph 返回状态保存为 run record。

它不能直接调用：

- `publish_or_schedule()`
- `creator_platform.publish_private_image_text()`
- `review_performance()`
- `write_operation_memory()`

### 审核驳回

`reject_run()` 的职责变为：

1. 校验 run 存在且处于 `waiting_review`。
2. 构造 reject resume payload。
3. 调用 `resume_langgraph(run_id, payload)`。
4. 保存图内 `reject_publish` 生成的最终状态。

驳回也应走 LangGraph resume，而不是 API 自己拼接驳回 state。

### run record

`_run_record()` 继续提供前端兼容结构，但内部必须从 LangGraph state 投影。

推荐映射：

- `record["status"]`: 兼容字段，可保留 `queued/running/success/failed`
- `record["summary"]["run_status"]`: 新主状态
- `record["summary"]["publish_status"]`: 发布状态
- `record["state"]`: LangGraph 最新 state
- `record["content"]`: 从 state 中投影的草稿内容
- `record["insights"]`: 从 state 中投影的洞察

## worker 改造

`scripts/run_worker.py` 保留命令行和心跳机制，但执行语义改为“LangGraph runner”：

```text
claim run
-> mark RunStore running
-> start/resume LangGraph thread
-> 如果 graph interrupt：mark waiting_review，queue job 不再继续占用
-> 如果 graph END：mark published/rejected/failed
-> queue mark_succeeded 或 mark_failed
```

等待人工审核不是 worker failure，也不是长期 running。worker 处理到 interrupt 后应释放队列任务，让 run 进入 `waiting_review`。

审核通过或驳回时由 API 直接 resume 图；后续如果耗时较长，可再入队一个 resume job，但本次整改优先保持 API 同步 resume，避免扩大队列协议。

## 事件与观测

节点级事件统一来自 LangGraph 执行过程，不再只由 local executor 生成。

设计要求：

- `run_events` 继续作为事件表。
- LangGraph `stream(..., stream_mode="updates")` 或等价机制记录节点完成事件。
- interrupt 记录 `node_interrupted`。
- resume 记录 `node_resumed`。
- 节点异常记录 `node_failed`。
- queue 事件继续记录 queue 层动作。

`run_local_graph()` 的 `_run_node()` 事件记录不再作为主路径依据。

## local executor 策略

`run_local_graph()` 暂时保留，但地位降级：

- 只能由 `engine=local` 显式调用。
- 不新增功能。
- 不作为默认工作台或 worker 路径。
- 测试逐步迁移到 LangGraph runtime 后，可以删除 local executor 测试。

## 数据投影

RunStore 和业务表都从 LangGraph state 投影，不反向控制图流程。

保存顺序：

```text
LangGraph state 更新
-> build run record
-> RunStore.save(record)
-> sync_run_business_tables(record)
-> record run_events
```

如果业务表同步失败，不应回滚 LangGraph checkpoint；应保存 audit/error event，并让 run record 保留主结果。

## 错误处理

- checkpointer 初始化失败：LangGraph run 失败，保存明确错误，不回落 local。
- graph interrupt 后缺 checkpoint：approve/reject 返回“不可恢复的 LangGraph thread”错误。
- resume payload 缺少审核动作：human_review 节点返回 failed state 或抛出明确错误。
- creator 发布失败：图继续到复盘和写记忆，但 `creator_publish_status=failed`，错误脱敏后进入 state。
- 高风险合规：图进入 stop/reject 路径，不允许发布。
- worker crash：queue heartbeat/watchdog 继续负责超时和重试，但不得重复执行已经进入 `waiting_review` 的 run。

## 测试策略

本次整改必须用 TDD 推进，优先新增或重写以下测试：

1. LangGraph runtime 使用 `run_id` 作为 `thread_id`。
2. 未审核草稿在 `human_review` 处 interrupt，并投影为 `run_status=waiting_review`。
3. `approve_run()` 通过 LangGraph resume 继续到发布、creator 节点、复盘、写记忆。
4. `approve_run()` 不直接调用发布、creator、复盘、写记忆函数。
5. `reject_run()` 通过 LangGraph resume 进入图内驳回节点。
6. worker 遇到 interrupt 后保存 `waiting_review`，不把 run 标成 failed。
7. LangGraph stream 产生节点级 run events。
8. 业务表同步使用 LangGraph 最终 state 投影。
9. `engine=local` 仍可显式运行，但默认 API 和 worker 使用 LangGraph。
10. creator 发布成功、失败、参数缺失、视频格式限制等旧测试继续成立，只是触发点从 API 层迁移到图内节点。

## 验收标准

全盘整改完成后，应能证明：

- 默认工作台提交使用 LangGraph runtime。
- 人审通过和驳回都通过同一个 LangGraph thread resume。
- API 不再手动拼接发布、creator 发布、复盘、写记忆主链路。
- worker 不再长期占用等待审核的 run。
- RunStore 和业务表是图 state 的投影。
- 节点级事件覆盖 LangGraph 主路径。
- `run_local_graph()` 不再是默认路径。
- 全量测试通过，或明确列出无法通过的外部依赖测试及原因。

## 实施顺序建议

虽然这是全盘改造，但实施仍应按依赖顺序推进：

1. 建立 LangGraph runtime 边界和测试。
2. 改造 human_review interrupt/resume。
3. 将 approve/reject 迁移到 graph resume。
4. 将 creator 发布迁移为图内节点。
5. 改造 run status 和 RunStore 投影。
6. 改造 worker 对 interrupt 的处理。
7. 将节点级事件迁移到 LangGraph stream。
8. 收敛默认 engine 和 local executor 兼容策略。
9. 跑全量测试和 smoke 验证。

这个顺序不是缩小整改范围，而是把全盘改造拆成可运行、可验证的执行批次。
