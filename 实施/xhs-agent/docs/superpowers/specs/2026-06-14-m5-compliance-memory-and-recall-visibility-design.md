# M5 第五片：合规留痕与召回解释可见化设计

## 目标

本轮目标是在 M5 第四片“规则版相似经验与合规风险召回”之后，补齐合规数据的长期留痕和轻量可见化。系统需要把当前 run 的合规风险结果保存到 operation memory，让后续历史合规风险召回优先使用结构化字段，并在工作台召回依据区展示相似经验、历史合规风险和简短召回解释。

本轮仍不引入 embedding、向量库、图数据库、新外部服务或新的真实平台写入行为。

## 背景

当前已经具备：

- `nodes.compliance_node.check_compliance()` 会生成 `compliance_risk_level` 和 `compliance_issues`。
- `nodes.compliance_node.revise_content_for_compliance()` 会在中风险时生成 `revised_content`，并可能补充 `human_feedback`。
- `app.memory_graph.query_memory_graph()` 已支持 `historical_compliance_risks` 和 `recall_explanations`。
- `nodes.memory_node.retrieve_graphrag_memory()` 已把当前合规字段传入图谱召回层。
- `nodes.memory_context.build_generation_memory_context()` 已把历史合规风险压缩进生成上下文。
- 工作台已有“召回依据”区域，但只展示推荐内容类型、相关痛点和召回记录。

当前缺口：

- `memory.operation_store.record_from_state()` 尚未统一保存合规字段。
- `app.api._compact_memory_record()` 尚未暴露历史记录合规字段。
- 历史合规风险召回虽然兼容扫描复盘摘要和下一步建议，但结构化来源不足。
- 工作台看不到相似经验、历史合规风险和召回解释。

## 范围

本轮包含五块：

1. operation memory 合规留痕。
2. memory records API 暴露合规留痕字段。
3. 历史合规风险召回优先使用结构化字段。
4. 工作台召回依据区展示相似经验、历史合规风险和召回解释。
5. 文档、测试和进度记录收口。

本轮不做：

- 不做 embedding/向量召回。
- 不做历史 operation memory 大迁移。
- 不做复杂图谱可视化。
- 不改真实平台发布行为。
- 不进入 M6 软广或达人能力。

## 数据设计

### operation memory 记录新增字段

`memory.operation_store.record_from_state()` 保存以下字段：

```python
{
    "compliance_risk_level": "low" | "medium" | "high" | "",
    "compliance_issues": ["..."],
    "revised_content": "...",
    "compliance_summary": {
        "risk_level": "...",
        "issue_count": 0,
        "issues": ["..."],
        "has_revision": True,
    },
}
```

字段规则：

- `compliance_risk_level` 缺失时保存空字符串。
- `compliance_issues` 只保存字符串列表，过滤空值，最多保留 10 条。
- `revised_content` 只保存字符串，避免保存复杂对象。
- `compliance_summary.issues` 保留紧凑 issue 列表，最多 5 条。
- 旧记录没有这些字段时，读取和 API 展示使用空值兜底。

### API 暴露

`app.api._compact_memory_record()` 增加：

- `compliance_risk_level`
- `compliance_issues`
- `revised_content`
- `compliance_summary`

这样工作台和调试脚本可以直接看到历史记录的合规背景。

## 召回设计

`app.memory_graph._historical_compliance_risks()` 保持当前扫描能力，但排序和来源优先级调整：

1. 优先命中历史记录的 `compliance_issues`。
2. 其次命中 `compliance_summary.issues`。
3. 再扫描 `review_summary`、`next_action`、`title`、`pain_points` 等兼容字段。

召回结果增加 `source_fields` 或继续复用 `matched_fields`，让解释能区分“来自结构化合规字段”还是“来自复盘文本”。

如果当前风险等级为 `low` 或为空，仍不生成强提醒，避免正常内容被历史风险噪声干扰。

## 工作台设计

现有工作台“召回依据”区域继续复用 `/memory/graph?topic=...&limit=5`。

新增展示：

- 相似经验：
  - 标题或主题。
  - 内容类型。
  - 表现分。
  - 简短原因。
- 历史合规风险：
  - 风险等级。
  - 命中的历史 issue。
  - 简短原因。
- 召回解释：
  - 类型。
  - 命中词。
  - 简短原因。

交互边界：

- 只读展示。
- 不新增编辑、入库、删除或批量选择动作。
- 没有数据时展示空状态或不渲染对应小节。
- 请求失败时沿用当前召回依据区的错误展示，不影响其他工作台区域。

## 错误处理

- 旧 operation memory 没有合规字段时，API 返回空字符串、空列表和空 summary。
- `compliance_issues` 类型异常时按空列表保存。
- `revised_content` 过长时本轮先不截断；如果后续发现过重，再改为摘要化。
- 工作台展示时所有文本继续使用现有转义逻辑。
- 新增字段不改变 `rag_eligibility` 写入门槛。

## 测试设计

新增或扩展测试：

- `tests/test_operation_store_sqlite.py`
  - `record_from_state()` 保存合规风险等级、issue、修订内容和 summary。
- `tests/test_api_memory_graph.py`
  - `_compact_memory_record()` 暴露合规留痕字段，并兼容旧记录空值。
- `tests/test_memory_graph.py`
  - 历史合规风险优先命中结构化 `compliance_issues` / `compliance_summary.issues`。
  - `matched_fields` 能体现结构化字段来源。
- `tests/test_workbench_memory_visibility_static.py`
  - 工作台静态文件包含相似经验、历史合规风险、召回解释的渲染入口。
- `tests/test_generation_memory_context.py`
  - 保持新增字段不会破坏 prompt payload。

验证命令：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_operation_store_sqlite.py tests/test_api_memory_graph.py tests/test_memory_graph.py tests/test_workbench_memory_visibility_static.py -q
```

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_node.py tests/test_memory_context.py tests/test_generation_memory_context.py -q
```

```powershell
node --check app/static/app.js
```

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes memory tests
```

## 验收标准

- 新写入的 operation memory 记录包含合规风险等级、issue、修订内容和 summary。
- memory records API 能暴露合规留痕字段。
- 历史合规风险召回优先使用结构化合规字段，并保留可解释命中来源。
- 工作台召回依据区能展示相似经验、历史合规风险和召回解释。
- 旧记录、旧调用和旧工作台基础展示保持兼容。
- 本轮不引入新外部依赖，不改变真实平台写入行为。

## 后续任务

- 评估是否为历史 operation memory 做一次质量补标或小规模迁移。
- 评估 embedding/向量检索的最小可测方案。
- 后续可把召回解释从轻量文本展示升级为更完整的图谱可视化。
