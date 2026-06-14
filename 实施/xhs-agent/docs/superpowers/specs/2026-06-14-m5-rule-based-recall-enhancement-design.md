# M5 第四片：规则版相似经验与合规风险召回设计

## 目标

本轮目标是在现有 M5 图谱记忆基础上，补齐轻量跨主题召回能力：不引入 embedding、向量库、图数据库或新外部服务，先用规则匹配把“当前 run 的痛点”和“当前 run 的合规风险”映射到历史 operation memory，形成可解释的相似经验和历史风险提醒。

完成后，`graphrag_memory` 不只包含按主题召回的历史记录，还会包含：

- 跨主题相似经验记录。
- 相似痛点聚合。
- 历史合规风险提醒。
- 每条召回的解释字段。

## 背景

当前 M5 已完成前三片：

- `app/memory_graph.py` 可以基于 operation memory 构建主题、痛点、内容类型和记录之间的图谱视图。
- `nodes/memory_node.retrieve_graphrag_memory()` 已把 `graphrag_memory` 写入 LangGraph state。
- `nodes/memory_context.py` 已把召回结果压缩后交给策略、图文和视频生成节点。
- `rag_eligibility` 已开始控制长期运营记忆写入，工作台也能查看当前主题召回依据。

当前缺口：

- 召回仍以主题文本包含匹配为主，对“不同主题但痛点相似”的经验复用不足。
- 合规节点只检查当前内容，没有利用历史中风险和高风险原因做提前提醒。
- 下游生成链路无法看到“为什么召回这些历史记录”的解释。

## 范围

本轮包含：

1. 扩展 `app/memory_graph.py` 的查询上下文，让召回可接收当前痛点、评论洞察和合规信息。
2. 新增跨主题相似经验召回，基于痛点、评论洞察、复盘摘要和下一步建议做规则匹配。
3. 新增历史合规风险召回，基于合规 issue 和历史风险文本做规则匹配。
4. 扩展 `nodes/memory_node.py`，把当前 state 的相关上下文传给 `query_memory_graph()`。
5. 扩展 `nodes/memory_context.py`，把新增召回字段压缩到生成上下文。
6. 增加测试覆盖，确保召回结果可解释、边界可控、旧行为兼容。

本轮不做：

- 不新增 embedding、向量库、图数据库、外部 RAG 框架或新模型调用。
- 不改变 `write_operation_memory()` 的 RAG 入库门槛。
- 不做历史 operation memory 大迁移。
- 不做复杂前端图谱可视化。
- 不触发任何真实平台写入行为。

## 后端设计

### 查询输入

`app.memory_graph.query_memory_graph()` 保持现有参数兼容，并新增可选参数：

```python
def query_memory_graph(
    records: list[dict[str, Any]],
    *,
    topic: str,
    limit: int = 20,
    pain_points: list[dict[str, Any]] | None = None,
    comment_insights: list[dict[str, Any]] | None = None,
    compliance_issues: list[str] | None = None,
    compliance_risk_level: str = "",
) -> dict[str, Any]:
    ...
```

旧调用不传这些参数时，返回结构继续包含现有字段，新增字段为空列表。

### 相似经验召回

新增内部函数从当前上下文提取关键词：

- 当前 `pain_points[].pain`
- 当前 `pain_points[].evidence`
- 当前 `comment_insights[].pain`
- 当前 `comment_insights[].evidence_comments`

对每条历史记录扫描：

- `topic`
- `title`
- `pain_points`
- `comment_insights`
- `review_summary`
- `next_action`

匹配规则：

- 对中文文本做保守切分：优先使用长度不少于 2 的短语片段、标点分隔片段和去重关键词。
- 命中当前痛点词或评论洞察词时，生成 `matched_terms` 和 `matched_fields`。
- 记录表现分越高、命中字段越多、命中词越多，排序越靠前。
- 继续复用现有跨领域健康污染过滤逻辑，避免非健康主题召回健康护理类污染记录。

输出字段：

```python
"similar_experience_records": [
    {
        "record_id": "...",
        "topic": "...",
        "title": "...",
        "content_type": "...",
        "performance_score": 0,
        "matched_terms": ["..."],
        "matched_fields": ["pain_points", "review_summary"],
        "reason": "当前痛点与历史记录的痛点/复盘摘要相似。",
    }
]
```

### 相似痛点聚合

从相似经验记录里聚合历史痛点：

```python
"similar_pain_points": [
    {
        "pain": "...",
        "count": 2,
        "max_score": 35,
        "record_ids": ["op_x", "op_y"],
        "matched_terms": ["..."],
    }
]
```

排序优先级为最高表现分、出现次数、痛点文本。

### 历史合规风险召回

当前系统的 operation memory 记录尚未统一保存完整 `compliance_issues`。因此本轮合规风险召回采用兼容式扫描：

- 优先读取历史记录中的 `compliance_issues` 和 `compliance_risk_level`，为后续扩展留好入口。
- 同时扫描 `review_summary`、`next_action`、`title`、`pain_points` 等文本，识别与当前 `compliance_issues` 重合的风险词。
- 如果当前 `compliance_risk_level` 为空或为 `low`，默认不生成强提醒，只保留空列表。
- 如果当前为 `medium` 或 `high`，且命中历史风险词，则生成历史风险提醒。

输出字段：

```python
"historical_compliance_risks": [
    {
        "record_id": "...",
        "topic": "...",
        "risk_level": "medium",
        "issues": ["内容中包含绝对词：一定"],
        "matched_terms": ["绝对词", "一定"],
        "reason": "当前合规问题与历史风险记录相似，生成前需要避免重复表达。",
    }
]
```

### 召回解释

新增统一解释列表，方便后续工作台或调试脚本展示：

```python
"recall_explanations": [
    {
        "type": "similar_experience",
        "record_id": "...",
        "reason": "...",
        "matched_terms": ["..."],
        "matched_fields": ["..."],
    },
    {
        "type": "historical_compliance_risk",
        "record_id": "...",
        "reason": "...",
        "matched_terms": ["..."],
        "matched_fields": ["..."],
    }
]
```

解释字段只保存短文本和命中摘要，不复制完整历史正文。

## 节点设计

`nodes.memory_node.retrieve_graphrag_memory()` 继续读取：

- `retrieved_memory`
- `successful_patterns`
- `graphrag_memory`

但调用 `query_memory_graph()` 时传入当前 state：

- `pain_points`
- `comment_insights`
- `compliance_issues`
- `compliance_risk_level`

这样召回增强仍在记忆节点内部完成，不让策略节点或生成节点直接理解 operation memory 的原始结构。

## 生成上下文设计

`nodes.memory_context.build_generation_memory_context()` 新增压缩字段：

```python
"similar_experience_records": [
    {
        "record_id": "...",
        "topic": "...",
        "title": "...",
        "content_type": "...",
        "performance_score": 0,
        "reason": "...",
    }
],
"historical_compliance_risks": [
    {
        "record_id": "...",
        "risk_level": "...",
        "issues": ["..."],
        "reason": "...",
    }
],
```

限制：

- 默认最多保留 3 条相似经验。
- 默认最多保留 3 条合规风险提醒。
- 不把完整 `matched_fields` 和长证据文本塞进 prompt，只保留短解释。

## 错误处理

- 新参数缺失或类型不符合预期时，按空列表处理。
- 历史记录字段缺失时跳过对应字段，不抛异常。
- 没有相似经验或合规风险时返回空列表。
- 旧测试和旧调用保持兼容。
- 跨领域健康污染过滤继续生效，避免旧健康护理记录污染非健康主题。

## 测试设计

新增或扩展测试：

- `tests/test_memory_graph.py`
  - 当前痛点与历史痛点相似时，返回 `similar_experience_records`。
  - 相似经验召回支持跨主题，但仍受跨领域健康污染过滤保护。
  - 当前合规 issue 与历史风险文本相似时，返回 `historical_compliance_risks`。
  - 新增 `recall_explanations` 包含类型、记录 ID、命中词和原因。
- `tests/test_memory_node.py`
  - `retrieve_graphrag_memory()` 会把当前痛点和合规字段传给 `query_memory_graph()`。
- `tests/test_memory_context.py`
  - 生成上下文会压缩相似经验和历史合规风险。
  - 空增强召回时仍保持 `enabled` 逻辑兼容。
- 相关回归：
  - `tests/test_strategy_memory_context.py`
  - `tests/test_generation_memory_context.py`
  - `tests/test_api_memory_graph.py`

验证命令：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_graph.py tests/test_memory_node.py tests/test_memory_context.py -q
```

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_strategy_memory_context.py tests/test_generation_memory_context.py tests/test_api_memory_graph.py -q
```

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes memory tests
```

## 验收标准

- 当前 run 有痛点上下文时，`graphrag_memory` 能返回可解释的跨主题相似经验。
- 当前 run 有中高风险合规问题时，`graphrag_memory` 能返回历史风险提醒。
- 召回增强不破坏原有按主题召回、推荐内容类型、相关痛点和召回依据字段。
- 下游生成上下文能拿到压缩后的相似经验和风险提醒。
- 不引入新外部依赖，不改变真实平台写入行为。
- 本轮实现后，后续 embedding/向量检索可以复用这些解释字段作为评估基线。

## 后续任务

- 基于本轮规则版结果，评估 embedding/向量检索的最小可测方案。
- 将 `compliance_issues` 和 `compliance_risk_level` 正式写入 operation memory，提升历史风险召回质量。
- 在工作台召回依据区展示相似经验和历史风险提醒。
- 历史 operation memory 大迁移和质量补标。
