# M5 第三片：RAG 入库门槛与召回依据展示设计

## 目标

本轮目标是在 M5 已完成“图谱视图初版”和“记忆消费侧初版”之后，补上一个最小可测闭环：用现有 `rag_eligibility` 控制哪些 run 可以写入长期运营记忆，并在工作台展示当前主题的召回依据。

本轮不引入 embedding、向量库、图数据库、新外部服务或新的真实平台写入行为。

## 背景

当前系统已经具备：

- `nodes/insight_node.py` 会在洞察分析后生成 `rag_eligibility`。
- `nodes/memory_node.retrieve_graphrag_memory()` 会读取历史运营记忆并生成 `graphrag_memory`。
- `nodes/strategy_node.py`、`nodes/content_node.py` 和 `nodes/video_node.py` 已经消费 `graphrag_memory`。
- `app/api.py` 已有 `GET /memory/graph?topic=...&limit=...`。
- 工作台已有运营记忆列表，但没有展示召回依据。

当前缺口：

- `write_operation_memory()` 只判断 `publish_status=success`，没有用 `rag_eligibility` 控制长期记忆写入。
- `record_from_state()` 没有保存 `rag_eligibility`，后续无法追溯某条记忆为什么可以进入长期记忆。
- 工作台无法直接看到 GraphRAG 风格召回依据，只能看原始 JSON 或运营记忆列表。

## 范围

本轮包含三块：

1. 写入门槛：`write_operation_memory()` 在写长期运营记忆前检查 `rag_eligibility`。
2. 记录留痕：运营记忆记录保存 `rag_eligibility`。
3. 工作台展示：复用 `/memory/graph` 展示当前主题的召回依据。

本轮不做：

- 不改变 `find_relevant_records()` 的召回过滤逻辑。
- 不过滤历史旧记录。
- 不做历史 operation memory 全量迁移。
- 不新增向量检索或图数据库。
- 不做复杂图谱可视化，只做结构化文本展示。

## 后端设计

### 写入门槛

`nodes/memory_node.write_operation_memory()` 保留现有发布成功前提：

- `publish_status != "success"`：继续跳过写入。
- `publish_status == "success"` 且 `rag_eligibility.eligible is False`：跳过写入长期运营记忆。
- `rag_eligibility` 缺失或不是 dict：保持兼容，允许写入，避免旧 run 或人工补偿链路被突然阻断。
- `rag_eligibility.eligible is True`：正常写入。

跳过时返回：

```python
{
    "next_action": "...",
    "operation_memory_path": "...",
    "operation_memory_written": False,
    "operation_memory_skip_reason": "rag_eligibility_blocked",
    "operation_memory_skip_detail": {
        "level": "...",
        "score": 0,
        "blocking_reasons": [...],
        "recommended_action": "...",
    },
}
```

`operation_memory_skip_detail` 只保存紧凑字段，避免把完整采集数据重复写入 run summary。

### 记录留痕

`memory/operation_store.record_from_state()` 将 `rag_eligibility` 原样保存到运营记忆记录中。这样后续展示、补偿脚本和真正 RAG 入库可以判断记录来源质量。

如果 `rag_eligibility` 缺失，则记录里保存空 dict，保持旧路径兼容。

### API 摘要

`app/api._state_summary()` 暴露：

- `operation_memory_skip_reason`
- `operation_memory_skip_detail`

`app/api._compact_memory_record()` 暴露：

- `rag_eligibility`

这样工作台既能看到当前 run 为什么没有写入长期记忆，也能看到已有记忆的入库质量信息。

## 工作台设计

工作台新增一个轻量召回依据区，优先放在“运营记忆”面板顶部或紧邻运营记忆列表，复用现有侧边工作区节奏。

数据来源：

- 当前已选 run：使用 `run.request.topic` 调用 `/memory/graph?topic=<topic>&limit=5`。
- 未选 run 或主题为空：展示空状态。

展示内容：

- 推荐内容类型：来自 `memory_graph.recommended_content_types`。
- 相关痛点：来自 `memory_graph.related_pain_points`。
- 召回记录：来自 `memory_graph.recall_evidence`。

交互边界：

- 只读展示，不新增编辑、批量选择或入库按钮。
- 如果 `/memory/graph` 返回空记录，展示“暂无召回依据”。
- 如果请求失败，展示紧凑错误提示，不影响其他工作台刷新。

## 错误处理

- `rag_eligibility` 缺失：兼容旧记录，允许写入。
- `rag_eligibility.eligible` 为 `False`：跳过写入并返回明确原因。
- `/memory/graph` 请求失败：前端仅在召回依据区展示错误，不阻断运行记录、运营记忆和表现趋势刷新。
- 历史记录没有 `rag_eligibility`：工作台显示为“未记录门槛”，不推断为合格或不合格。

## 测试设计

新增或扩展测试：

- `tests/test_memory_node.py`
  - `rag_eligibility.eligible=False` 时不调用 `upsert_record_from_state()`，并返回跳过原因。
  - `rag_eligibility` 缺失时仍保持旧行为，发布成功后写入。
- `tests/test_operation_store_sqlite.py` 或新增 JSON 记录测试
  - `record_from_state()` 保存 `rag_eligibility`。
- `tests/test_api_memory_graph.py` 或新增 API 摘要测试
  - run summary 暴露 `operation_memory_skip_reason` 和 `operation_memory_skip_detail`。
  - memory records API 暴露 `rag_eligibility`。
- `tests/test_workbench_memory_visibility_static.py`
  - 静态检查工作台包含召回依据区、调用 `/memory/graph`、渲染推荐内容类型/相关痛点/召回记录。

验证命令：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_node.py tests/test_operation_store_sqlite.py tests/test_api_memory_graph.py tests/test_workbench_memory_visibility_static.py -q
```

```powershell
node --check app/static/app.js
```

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes memory tests
```

## 验收标准

- 数据质量不合格的 run 不再进入长期运营记忆。
- 跳过写入时，API summary 能说明跳过原因和阻断项。
- 合格或旧兼容 run 仍能正常写入运营记忆。
- 运营记忆记录保留 `rag_eligibility`。
- 工作台能按当前主题展示召回依据。
- 本轮不改变历史召回过滤行为，不引入新外部依赖。

## 后续任务

- 真正 RAG 入库和向量召回。
- 历史 operation memory 全量迁移和质量补标。
- 合规风险历史召回。
- 更完整的图谱可视化和召回解释。
