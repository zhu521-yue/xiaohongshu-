# run_events 事件时间线实施计划

## 目标

在 foundation 业务表已经可写可查后，补齐 `run_events` 时间线：记录 run 生命周期事件和本地 graph 节点耗时，并让 `/business/runs/{run_id}` 能直接返回这些事件。

## 范围

- 新增 `app/run_events.py`，提供幂等写入 `run_events` 的小型工具函数。
- `app/business_queries.py` 查询结果新增 `run_events`。
- `app/api.py` 在 SQLite run store 且业务表启用时记录生命周期事件：
  - queued
  - running
  - success
  - failed
- `app/graph.py` 的 `run_local_graph()` 支持可选 `run_id`，在每个本地节点前后记录节点事件与耗时。
- `langgraph` 引擎暂不做节点级细粒度事件，只记录 API 生命周期事件。

## 当前不做

- 不新增前端展示。
- 不改变 graph 节点业务逻辑。
- 不改变 `/runs/{run_id}` 响应结构。
- 不做告警和监控聚合。

## 验证

- 新增 `tests/test_run_events.py` 覆盖事件写入器幂等、节点耗时和错误事件。
- 扩展 `tests/test_business_queries.py` 覆盖业务快照包含 `run_events`。
- 扩展 API 测试覆盖 SQLite 自动事件写入。
- 运行聚焦测试、编译检查和全量回归。
