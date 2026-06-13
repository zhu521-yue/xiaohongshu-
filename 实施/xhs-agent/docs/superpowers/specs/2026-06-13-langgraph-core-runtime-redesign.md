# LangGraph 核心运行时回正设计

## 背景

当前项目已经具备内容生成、采集、审核、发布、复盘、业务表、API 工作台、SQLite 队列和 worker 等能力，但流程控制权逐步从 LangGraph 转移到了 API、RunStore、SQLite 队列和人工续跑函数中。

这带来两个问题：

1. `langgraph` 引擎存在，但主要只是一次性 `invoke()` 一张图。
2. 人工审核后的发布、复盘和写记忆由 API 手动调用节点函数，不是从同一个 LangGraph thread 恢复。

整改目标不是追求框架纯粹性，而是让最终系统更容易扩展到 GraphRAG、阶段二软广、多个人工决策点、发布状态轮询和运营闭环。

## 总目标

采用“中度回正，分阶段实施”的路线：

- LangGraph 重新成为业务流程主干，负责流程状态、分支、暂停、恢复和后续节点执行。
- API 保留为提交任务、人工操作、前端展示和平台动作入口。
- SQLite RunStore、业务表和队列保留为生产基础设施，不再直接拼接业务流程。
- worker 保留为异步执行外壳，运行的是 LangGraph 主流程，而不是自研流程状态机。

第一轮只做核心回正，不推倒现有 API、worker、RunStore、业务表和前端。

## 第一阶段范围

第一阶段必须完成：

1. `build_langgraph()` 支持可注入 checkpointer。
2. `run_langgraph()` 使用 `run_id` 作为 LangGraph `thread_id`。
3. `human_review` 从占位状态节点改为 LangGraph `interrupt()` 暂停点。
4. API 生成草稿后停在审核点，保存可审核草稿状态。
5. `approve_run()` 通过同一个 LangGraph thread resume，而不是手动调用 `publish_or_schedule()`、creator 发布、`review_performance()`、`write_operation_memory()`。
6. `reject_run()` 仍可记录人工驳回，但不触发后续发布节点。
7. 保持现有工作台和脚本的主要接口兼容。

第一阶段不做：

- 不重写 worker 和 SQLite 队列。
- 不删除 `run_local_graph()`。
- 不重构前端工作台。
- 不引入 Redis、PostgreSQL、Celery 或新的外部服务。
- 不把所有业务表改成 LangGraph checkpoint 投影。
- 不实现 GraphRAG、阶段二软广、达人匹配。

## 架构原则

### 流程控制权

业务流程的下一步由 LangGraph 决定。API 可以提交输入、读取结果、传入人工审核结果，但不直接决定“审核后该调哪个节点”。

审核通过后的标准路径是：

```text
human_review interrupt
-> API approve_run 提供审核结果
-> LangGraph resume
-> publish_or_schedule
-> review_performance
-> write_operation_memory
-> END
```

审核不通过后的标准路径是：

```text
human_review interrupt
-> API reject_run 记录驳回状态
-> 不 resume 发布路径
```

### 基础设施角色

`RunStore` 继续保存 API 视角的 run record，用于前端列表、详情和兼容旧接口。

LangGraph checkpointer 保存图线程状态，用于真实暂停和恢复。

业务表继续作为查询投影，由 `_save_run()` 后的同步逻辑维护。

SQLite 队列和 worker 继续负责异步执行 run，但 worker 不掌握业务流程内部状态。

### 兼容策略

保留 `engine=local`，用于本地调试和现有测试兼容。

`engine=langgraph` 成为默认主路径。新增核心能力优先服务 `engine=langgraph`。

已有内容生成、合规、人审、发布、复盘、写记忆节点尽量复用，避免重写业务逻辑。

## 组件设计

### `app/graph.py`

新增或调整：

- `build_langgraph(checkpointer=None)`：编译图时可接收 checkpointer。
- `build_langgraph_runtime()`：集中创建 LangGraph app 和 checkpointer，避免每次 API 调用散落创建逻辑。
- `run_langgraph(initial_state, run_id=None)`：如果传入 `run_id`，用 `config={"configurable": {"thread_id": run_id}}` 执行。
- `resume_langgraph(run_id, resume_value)`：用 `Command(resume=resume_value)` 恢复同一个 thread。

`run_local_graph()` 保留，不参与第一阶段改造。

### `nodes/human_review_node.py`

`human_review()` 在 `engine=langgraph` 主路径中成为暂停点。

推荐行为：

- 高风险内容直接返回审核不通过，不进入 interrupt。
- 已带明确 `human_approved=True` 的一次性命令行运行可以继续通过，保持已有脚本兼容。
- 普通未审核草稿调用 `interrupt()`，把标题、正文、合规风险、候选封面、标签等审核所需摘要传给 API。
- resume 后根据人工输入更新 `human_approved`、`human_feedback`、`publish_status`。

### `app/api.py`

生成阶段：

- `_run_workflow()` 对 `engine=langgraph` 调用新的 `run_langgraph(initial_state, run_id=run_id)`。
- 如果图在 human interrupt 暂停，run record 状态仍可保存为 `success` 或更精确的 `waiting_review`。第一阶段推荐使用 `success` 兼容现有工作台，同时在 summary/state 中保留 `publish_status=pending`、`human_approved=False`。

审核通过：

- `approve_run()` 加载 run record 后，不再手动调用发布、creator 发布、复盘、写记忆。
- 对 `engine=langgraph` 的 run，调用 `resume_langgraph(run_id, {"approved": True, "feedback": feedback})`。
- resume 完成后用返回的最终 state 重新生成 run record 并保存。
- creator 私密发布如果仍作为 API 审核通过时的显式动作，第一阶段可以保留在 API 层，但它必须被建模为“发布节点后的平台动作补充”，不能替代图内 `publish_or_schedule`、`review_performance`、`write_operation_memory`。

审核驳回：

- `reject_run()` 不 resume 发布路径。
- 保存 `human_approved=False`、`publish_status=rejected`、`review_action=rejected`、`operation_memory_written=False`。

### `app/run_store.py` 与业务表

第一阶段不改公开接口。

run record 继续保存：

- `request`
- `summary`
- `content`
- `insights`
- `state`
- `paths`
- `error`

后续第二阶段再考虑从 LangGraph stream 或 checkpoint 中投影节点级事件。

### worker 和队列

第一阶段不重写 `SQLiteRunQueue` 和 `scripts/run_worker.py`。

worker 继续 claim run，然后调用 API 层 `_execute_run()`。差异是 `_execute_run()` 内部调用的 `engine=langgraph` 路径会使用 LangGraph thread 和 checkpointer。

## 状态与数据流

### 提交流程

```text
POST /runs
-> submit_run()
-> RunStore 保存 queued
-> SQLiteRunQueue enqueue
-> worker claim
-> _execute_run()
-> run_langgraph(initial_state, run_id)
-> human_review interrupt 或直接 END
-> RunStore 保存草稿状态
-> 前端展示待审核草稿
```

### 审核通过流程

```text
POST /runs/{run_id}/approve
-> approve_run()
-> resume_langgraph(run_id, resume_value)
-> LangGraph 从 human_review 后继续
-> publish_or_schedule
-> review_performance
-> write_operation_memory
-> RunStore 保存最终状态
-> 业务表同步
```

### 审核驳回流程

```text
POST /runs/{run_id}/reject
-> reject_run()
-> RunStore 保存 rejected 状态
-> 不执行发布、复盘、写记忆
```

## 错误处理

- checkpointer 初始化失败时，`engine=langgraph` run 失败并保存错误，不静默回落到 local。
- resume 找不到 thread 时，`approve_run()` 返回明确错误，提示该 run 不是可恢复的 LangGraph 草稿。
- resume 后节点失败时，保存 `status=failed`、`failure_category` 和错误摘要。
- creator 发布失败不应破坏图内本地 markdown 发布与运营记忆写入；它仍作为平台发布补充结果进入 state。

## 测试策略

第一阶段使用 TDD 增补测试：

1. `run_langgraph()` 使用 `run_id` 作为 thread_id，并可在 human_review 暂停。
2. `approve_run()` 对 LangGraph run 调用 resume，而不是直接调用后续节点函数。
3. 审核通过后最终 state 包含 `publish_status=success`、`operation_memory_written=True`。
4. 审核驳回不触发发布和写记忆。
5. `engine=local` 现有行为不变。
6. 现有 creator publish API 测试继续通过，必要时只调整断言以匹配 LangGraph resume 后的 state。

## 验收标准

第一阶段完成后，应能证明：

- 默认 `engine=langgraph` 的人工审核通过路径由 LangGraph resume 触发。
- API 不再手动拼接发布、复盘、写记忆主链路。
- run_id 与 LangGraph thread_id 对齐。
- 现有 API 工作台仍能提交、查看、审核、驳回 run。
- 全量测试通过，或明确列出仍未通过的测试和原因。

## 后续阶段

第二阶段：

- 从 LangGraph stream/update 记录节点级事件。
- 减少 `run_local_graph()` 和 `build_langgraph()` 双轨差异。
- 将 run status 从 `success + pending` 逐步细分为 `waiting_review`、`approved`、`rejected`、`published`。

第三阶段：

- 评估是否废弃手写 local executor。
- 将更多人工决策点、发布状态轮询、GraphRAG 召回和阶段二软广分支纳入 LangGraph 主图。
