# M5 规则版相似经验与合规风险召回实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不引入新外部依赖的前提下，让 `graphrag_memory` 支持可解释的跨主题相似经验召回和历史合规风险召回。

**Architecture:** 继续以 `app/memory_graph.py` 作为召回聚合层，`nodes/memory_node.py` 负责把当前 state 上下文传入召回层，`nodes/memory_context.py` 负责把增强召回压缩给策略和生成节点。规则召回只读取现有 operation memory 记录，不改变写入门槛和真实平台行为。

**Tech Stack:** Python、pytest、现有 operation memory JSON/SQLite 抽象、LangGraph state 字典、现有测试套件。

---

## 文件结构

- 修改：`app/memory_graph.py`
  - 新增当前上下文关键词提取、历史文本扫描、相似经验召回、相似痛点聚合、历史合规风险召回和统一解释字段。
- 修改：`nodes/memory_node.py`
  - `retrieve_graphrag_memory()` 调用 `query_memory_graph()` 时传入当前痛点、评论洞察、合规风险等级和合规 issue。
- 修改：`nodes/memory_context.py`
  - `build_generation_memory_context()` 输出压缩后的 `similar_experience_records` 和 `historical_compliance_risks`。
- 修改：`tests/test_memory_graph.py`
  - 覆盖相似经验、跨领域污染保护、合规风险和解释字段。
- 修改：`tests/test_memory_node.py`
  - 覆盖记忆节点传参。
- 修改：`tests/test_memory_context.py`
  - 覆盖生成上下文压缩。
- 修改：`memory/current_progress.md`
  - 实现完成后记录本轮进度、验证和遗留项。

---

### Task 1: 相似经验召回

**Files:**
- Modify: `tests/test_memory_graph.py`
- Modify: `app/memory_graph.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_memory_graph.py` 增加测试：

```python
def test_query_memory_graph_returns_cross_topic_similar_experience() -> None:
    records = [
        _record(
            "op_tool",
            topic="自由职业接单避坑",
            content_type="avoid_mistakes",
            score=45,
            pain="担心踩坑浪费时间",
        ),
        _record(
            "op_unrelated",
            topic="宝宝湿疹护理",
            content_type="qa_education",
            score=99,
            pain="担心护理方式不靠谱",
        ),
    ]

    result = memory_graph.query_memory_graph(
        records,
        topic="小红书选题",
        limit=5,
        pain_points=[{"pain": "担心踩坑浪费时间", "evidence": "不知道是否值得继续做"}],
    )

    assert result["similar_experience_records"][0]["record_id"] == "op_tool"
    assert "担心踩坑浪费时间" in result["similar_experience_records"][0]["matched_terms"]
    assert result["similar_experience_records"][0]["reason"]
    assert result["similar_pain_points"][0]["pain"] == "担心踩坑浪费时间"
    assert not any(item["record_id"] == "op_unrelated" for item in result["similar_experience_records"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_graph.py::test_query_memory_graph_returns_cross_topic_similar_experience -q`

Expected: FAIL，原因是 `query_memory_graph()` 尚不接受 `pain_points` 或尚未返回 `similar_experience_records`。

- [ ] **Step 3: 实现最小代码**

在 `app/memory_graph.py`：

- 为 `query_memory_graph()` 增加可选参数 `pain_points`、`comment_insights`、`compliance_issues`、`compliance_risk_level`。
- 新增 `_context_terms()` 从当前痛点和评论洞察提取短文本。
- 新增 `_record_text_fields()` 扫描历史记录字段。
- 新增 `_similar_experience_records()` 返回相似记录。
- 新增 `_similar_pain_points()` 聚合相似记录里的历史痛点。
- `query_memory_graph()` 返回新增字段，旧调用时字段为空列表。

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_graph.py::test_query_memory_graph_returns_cross_topic_similar_experience -q`

Expected: PASS。

### Task 2: 历史合规风险召回

**Files:**
- Modify: `tests/test_memory_graph.py`
- Modify: `app/memory_graph.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_memory_graph.py` 增加测试：

```python
def test_query_memory_graph_returns_historical_compliance_risks() -> None:
    record = _record(
        "op_risk",
        topic="小红书涨粉话题",
        content_type="avoid_mistakes",
        score=20,
        pain="担心表达太夸张",
    )
    record["compliance_risk_level"] = "medium"
    record["compliance_issues"] = ["内容中包含绝对词：一定"]

    result = memory_graph.query_memory_graph(
        [record],
        topic="小红书选题",
        limit=5,
        compliance_risk_level="medium",
        compliance_issues=["内容中包含绝对词：一定"],
    )

    assert result["historical_compliance_risks"][0]["record_id"] == "op_risk"
    assert result["historical_compliance_risks"][0]["risk_level"] == "medium"
    assert "一定" in result["historical_compliance_risks"][0]["matched_terms"]
    assert any(item["type"] == "historical_compliance_risk" for item in result["recall_explanations"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_graph.py::test_query_memory_graph_returns_historical_compliance_risks -q`

Expected: FAIL，原因是历史合规风险字段尚未生成。

- [ ] **Step 3: 实现最小代码**

在 `app/memory_graph.py`：

- 新增 `_compliance_terms()` 从当前合规 issue 中抽取风险词。
- 新增 `_historical_compliance_risks()` 扫描历史记录的 `compliance_issues`、`compliance_risk_level`、`review_summary`、`next_action`。
- 新增 `_recall_explanations()` 统一汇总相似经验和历史风险解释。

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_graph.py::test_query_memory_graph_returns_historical_compliance_risks -q`

Expected: PASS。

### Task 3: 记忆节点传入当前上下文

**Files:**
- Modify: `tests/test_memory_node.py`
- Modify: `nodes/memory_node.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_memory_node.py` 增加测试：

```python
def test_retrieve_graphrag_memory_passes_current_context(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(memory_node, "find_relevant_records", lambda topic, limit=5: [], raising=False)
    monkeypatch.setattr(memory_node, "find_successful_patterns", lambda topic, limit=3: [], raising=False)

    def fake_query(records, **kwargs):
        captured.update(kwargs)
        return {"query": kwargs.get("topic"), "similar_experience_records": []}

    monkeypatch.setattr(memory_node, "query_memory_graph", fake_query, raising=False)

    state = {
        "user_topic": "小红书选题",
        "pain_points": [{"pain": "担心踩坑浪费时间"}],
        "comment_insights": [{"pain": "不知道从哪里开始"}],
        "compliance_risk_level": "medium",
        "compliance_issues": ["内容中包含绝对词：一定"],
    }

    memory_node.retrieve_graphrag_memory(state)

    assert captured["pain_points"] == state["pain_points"]
    assert captured["comment_insights"] == state["comment_insights"]
    assert captured["compliance_risk_level"] == "medium"
    assert captured["compliance_issues"] == state["compliance_issues"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_node.py::test_retrieve_graphrag_memory_passes_current_context -q`

Expected: FAIL，原因是当前节点尚未传入这些关键字参数。

- [ ] **Step 3: 实现最小代码**

修改 `nodes/memory_node.py` 中 `retrieve_graphrag_memory()` 的 `query_memory_graph()` 调用，传入 `pain_points`、`comment_insights`、`compliance_issues`、`compliance_risk_level`。

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_node.py::test_retrieve_graphrag_memory_passes_current_context -q`

Expected: PASS。

### Task 4: 生成上下文压缩

**Files:**
- Modify: `tests/test_memory_context.py`
- Modify: `nodes/memory_context.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_memory_context.py` 增加测试：

```python
def test_generation_memory_context_includes_rule_based_recall() -> None:
    context = build_generation_memory_context(
        _state(
            {
                "query": "小红书选题",
                "similar_experience_records": [
                    {
                        "record_id": "op_tool",
                        "topic": "自由职业接单避坑",
                        "title": "避坑标题",
                        "content_type": "avoid_mistakes",
                        "performance_score": 45,
                        "reason": "当前痛点与历史记录相似。",
                        "matched_terms": ["担心踩坑浪费时间"],
                    }
                ],
                "historical_compliance_risks": [
                    {
                        "record_id": "op_risk",
                        "risk_level": "medium",
                        "issues": ["内容中包含绝对词：一定"],
                        "reason": "当前合规问题与历史风险相似。",
                    }
                ],
            }
        )
    )

    assert context["enabled"] is True
    assert context["similar_experience_records"][0]["record_id"] == "op_tool"
    assert context["historical_compliance_risks"][0]["risk_level"] == "medium"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_context.py::test_generation_memory_context_includes_rule_based_recall -q`

Expected: FAIL，原因是生成上下文尚未返回新增字段。

- [ ] **Step 3: 实现最小代码**

在 `nodes/memory_context.py`：

- 新增 `_compact_similar_experiences()`。
- 新增 `_compact_compliance_risks()`。
- `build_generation_memory_context()` 返回两个新增字段，并把它们计入 `enabled`。

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_context.py::test_generation_memory_context_includes_rule_based_recall -q`

Expected: PASS。

### Task 5: 回归、文档和提交

**Files:**
- Modify: `memory/current_progress.md`

- [ ] **Step 1: 运行定点回归**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_graph.py tests/test_memory_node.py tests/test_memory_context.py -q`

Expected: PASS。

- [ ] **Step 2: 运行相关回归**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_strategy_memory_context.py tests/test_generation_memory_context.py tests/test_api_memory_graph.py -q`

Expected: PASS。

- [ ] **Step 3: 运行编译检查**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes memory tests`

Expected: exit code 0。

- [ ] **Step 4: 更新进度文档**

在 `memory/current_progress.md` 顶部记录 M5 第四片完成内容、验证结果、当前限制和下一步。

- [ ] **Step 5: 提交**

Run:

```powershell
git add app/memory_graph.py nodes/memory_node.py nodes/memory_context.py tests/test_memory_graph.py tests/test_memory_node.py tests/test_memory_context.py memory/current_progress.md
git commit -m "feat: add rule based m5 recall enhancement"
```

Expected: 本地提交成功，工作树干净。
