# M5 第二片：GraphRAG 记忆消费侧设计

## 目标

在不引入向量库、图数据库或新的入库流程的前提下，让现有 `graphrag_memory` 从“只产出”推进到“被策略和生成链路稳定消费”。

本轮只做消费侧最小闭环：

1. 策略节点可参考 `graphrag_memory.recommended_content_types` 选择内容类型。
2. 图文生成和视频生成的 LLM prompt 可获得召回证据、相关痛点和推荐类型。
3. fallback 模板在记忆为空、结构异常或证据不足时行为不变。
4. 解析逻辑集中在一个模块内，避免策略、图文、视频节点各自硬编码同一份字典结构。

## 当前状态

项目已经具备：

- `nodes/memory_node.retrieve_graphrag_memory()` 返回 `retrieved_memory`、`successful_patterns` 和 `graphrag_memory`。
- `app/memory_graph.py` 从 operation memory 派生：
  - `related_records`
  - `related_pain_points`
  - `recommended_content_types`
  - `recall_evidence`
  - `graph`
- `nodes/strategy_node.py` 目前优先使用痛点关键词和 `successful_patterns`。
- `nodes/content_node.py` 和 `nodes/video_node.py` 目前会把 `successful_patterns` 压缩后放入 LLM 输入，但不消费 `graphrag_memory`。

当前缺口是：记忆检索节点已经把 GraphRAG 风格摘要写入 state，但下游生成链路还没有使用它。

## 范围

### 本轮包含

- 新增 `nodes/memory_context.py`：
  - 负责从 `XHSState.graphrag_memory` 中提取安全、紧凑、可测试的记忆上下文。
  - 负责过滤无效 content type、低证据推荐、异常结构和空字段。
  - 负责生成给 LLM prompt 使用的 `memory_context` payload。
- 修改 `nodes/strategy_node.py`：
  - 在关键词规则之后、`successful_patterns` 之前参考 GraphRAG 推荐类型。
  - 只在推荐类型有召回证据时使用。
  - 保持冷启动和软广限制逻辑不变。
- 修改 `nodes/content_node.py` 和 `nodes/video_node.py`：
  - LLM prompt 增加 `memory_context`。
  - fallback 模板不强依赖记忆，避免把历史召回直接写进模板正文。
- 增加节点级测试，覆盖：
  - GraphRAG 推荐可影响策略。
  - 关键词规则仍优先于 GraphRAG 推荐。
  - 无证据或非法推荐不会影响策略。
  - 图文/视频 LLM payload 包含紧凑记忆上下文。
  - 空记忆时 payload 使用空结构且不报错。

### 本轮不包含

- embedding、向量检索、pgvector、图数据库或完整 GraphRAG 入库。
- 修改 `app/memory_graph.py` 的召回算法。
- 前端图谱展示。
- 历史 operation memory 全量迁移。
- 让 fallback 模板大幅复用历史正文，避免历史内容污染新稿。

## 方案选择

### 方案 A：各节点直接读取 `graphrag_memory`

优点是改动少。缺点是三个节点会重复解析同一份嵌套字典，后续字段变化时容易散落修改，也会继续形成硬编码。

### 方案 B：新增小型记忆上下文适配层（采用）

新增 `nodes/memory_context.py`，所有下游节点只读取该模块返回的稳定结构。

优点是边界清晰、测试集中、后续真正 RAG 接入时只需要替换适配层。缺点是多一个小模块，但复杂度可控。

### 方案 C：把 `graphrag_memory` 合并进 `pattern_utils`

优点是复用已有结构选择工具。缺点是 `pattern_utils` 目前关注高表现模式和结构 profile，如果把召回证据、痛点和 prompt payload 都塞进去，会让职责变混。

本轮采用方案 B。

## 架构设计

### `nodes/memory_context.py`

提供三个公开函数：

- `recommended_memory_content_type(state, min_evidence_count=1) -> str | None`
- `build_generation_memory_context(state, limit=3) -> dict`
- `has_memory_evidence(state) -> bool`

`recommended_memory_content_type()` 只返回已在内容规则中声明的合法 content type，并要求：

- `graphrag_memory.recommended_content_types` 是列表。
- 推荐项是 dict。
- `content_type` 合法。
- `count > 0` 或 `max_score > 0`。
- `recall_evidence` 或 `related_records` 至少有一条。

`build_generation_memory_context()` 返回紧凑 payload：

```json
{
  "enabled": true,
  "query": "小红书选题",
  "recommended_content_types": [
    {"content_type": "step_tutorial", "count": 2, "average_score": 81.5, "max_score": 90}
  ],
  "related_pain_points": [
    {"pain": "不知道第一步怎么做", "count": 2, "max_score": 90}
  ],
  "recall_evidence": [
    {"record_id": "op_1", "topic": "小红书选题", "title": "选题方法", "content_type": "step_tutorial", "performance_score": 90}
  ]
}
```

当没有有效记忆时返回：

```json
{
  "enabled": false,
  "query": "",
  "recommended_content_types": [],
  "related_pain_points": [],
  "recall_evidence": []
}
```

### 策略节点

`_choose_content_type()` 的优先级调整为：

1. 痛点关键词规则：避坑、步骤教程等强意图仍优先。
2. GraphRAG 推荐类型：用于历史召回有证据时的结构选择。
3. `successful_patterns`：保留旧逻辑，作为无 GraphRAG 推荐时的兼容路径。
4. 默认内容类型。

软广限制仍在 `decide_content_strategy()` 末尾统一兜底。

### 图文和视频生成节点

LLM prompt 的 `input_payload` 增加：

```python
"memory_context": build_generation_memory_context(state)
```

prompt 模板已通过 `{input_payload}` 注入 JSON，因此不需要改模板文件。模型会看到该字段，但 JSON 输出合同不变。

fallback 模板本轮不消费 `memory_context`，因为 fallback 的价值是稳定可控，不应该在历史记忆不可靠时复制历史措辞。

## 错误处理

- `graphrag_memory` 不是 dict 时视为空记忆。
- 列表字段不是 list 时视为空列表。
- 数字字段无法转换时按 0 处理。
- 非法 content type 被忽略。
- 适配层不抛出业务异常，避免记忆脏数据中断生成链路。

## 测试设计

新增：

- `tests/test_memory_context.py`
  - 有证据推荐返回合法 content type。
  - 无证据推荐返回 `None`。
  - 非法 content type 被忽略。
  - generation memory context 会裁剪召回证据和痛点字段。
- `tests/test_strategy_memory_context.py`
  - GraphRAG 推荐可影响策略。
  - 痛点关键词优先于 GraphRAG 推荐。
  - 无证据 GraphRAG 推荐不会影响策略。
- `tests/test_generation_memory_context.py`
  - 图文 prompt payload 包含 `memory_context`。
  - 视频 prompt payload 包含 `memory_context`。
  - 空记忆时 payload 为 disabled 空结构。

验证顺序：

1. 先跑新增定点测试，确认 RED。
2. 实现最小代码后跑新增定点测试，确认 GREEN。
3. 跑相关回归：`test_memory_graph.py`、`test_memory_node.py`、运行链路相关测试。
4. 跑 `compileall`。

## 验收标准

- 下游节点开始消费 `graphrag_memory`，但不改变记忆为空时的行为。
- 记忆解析逻辑集中在 `nodes/memory_context.py`。
- 策略选择具备可解释优先级：关键词 > GraphRAG 推荐 > successful_patterns > 默认。
- LLM prompt 输入包含可审计的召回证据和相关痛点。
- 不引入新的数据库、向量库或外部服务。
- 本轮完成后更新 `memory/current_progress.md` 和 `memory/project_status_and_roadmap.md`。

## 本轮之后仍未完成

- 真正的 RAG / GraphRAG 入库和向量召回。
- 按 `rag_eligibility` 控制哪些 run 可以进入长期记忆。
- 召回结果在工作台中的可视化展示。
- 历史 operation memory 全量迁移。
- 正式公网部署所需的 HTTPS、反向代理、进程守护、用户体系和密钥治理。
