# M5 合规留痕与召回解释可见化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保存 operation memory 的合规风险字段，提升历史合规风险召回质量，并在工作台召回依据区展示相似经验、历史风险和召回解释。

**Architecture:** 在 `memory/operation_store.py` 做合规字段留痕，在 `app/api.py` 暴露紧凑字段，在 `app/memory_graph.py` 让历史合规风险优先命中结构化字段，在 `app/static/app.js` 复用现有召回依据面板做只读展示。所有能力继续基于现有 operation memory 和 `/memory/graph`，不新增外部依赖。

**Tech Stack:** Python、pytest、标准库 HTTP API、现有前端静态 JS/CSS、node 语法检查。

---

## 文件结构

- 修改：`memory/operation_store.py`
  - 新增合规字段紧凑函数，`record_from_state()` 保存 `compliance_risk_level`、`compliance_issues`、`revised_content`、`compliance_summary`。
- 修改：`app/api.py`
  - `_compact_memory_record()` 暴露合规留痕字段。
- 修改：`app/memory_graph.py`
  - 历史合规风险召回优先扫描 `compliance_issues` 和 `compliance_summary`。
- 修改：`app/static/app.js`
  - `renderMemoryRecallEvidence()` 展示 `similar_experience_records`、`historical_compliance_risks`、`recall_explanations`。
- 修改：`app/static/styles.css`
  - 复用或轻量扩展召回依据样式。
- 修改：`tests/test_operation_store_sqlite.py`
  - 覆盖 operation memory 合规留痕。
- 修改：`tests/test_api_memory_graph.py`
  - 覆盖 compact API 字段。
- 修改：`tests/test_memory_graph.py`
  - 覆盖结构化合规字段优先命中。
- 修改：`tests/test_workbench_memory_visibility_static.py`
  - 覆盖工作台新增展示入口。
- 修改：`memory/current_progress.md`
  - 记录本轮完成、验证和限制。

---

### Task 1: operation memory 保存合规字段

**Files:**
- Modify: `tests/test_operation_store_sqlite.py`
- Modify: `memory/operation_store.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_operation_store_sqlite.py` 增加：

```python
def test_operation_memory_record_keeps_compliance_trace(sqlite_memory: Path) -> None:
    state = sample_state("output/compliance.md")
    state["compliance_risk_level"] = "medium"
    state["compliance_issues"] = ["内容中包含绝对词：一定", ""]
    state["revised_content"] = "发布前提醒：内容仅作经验分享。"

    saved = store.upsert_record_from_state(state)
    loaded = store.load_history()["records"][0]

    assert saved["compliance_risk_level"] == "medium"
    assert saved["compliance_issues"] == ["内容中包含绝对词：一定"]
    assert loaded["revised_content"] == "发布前提醒：内容仅作经验分享。"
    assert loaded["compliance_summary"] == {
        "risk_level": "medium",
        "issue_count": 1,
        "issues": ["内容中包含绝对词：一定"],
        "has_revision": True,
    }
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_operation_store_sqlite.py::test_operation_memory_record_keeps_compliance_trace -q`

Expected: FAIL，原因是记录尚未包含合规留痕字段。

- [ ] **Step 3: 实现最小代码**

在 `memory/operation_store.py`：

- 新增 `_compact_compliance_issues(value, limit=10)`。
- 新增 `_compliance_summary(risk_level, issues, revised_content)`。
- `record_from_state()` 保存四个新字段。

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_operation_store_sqlite.py::test_operation_memory_record_keeps_compliance_trace -q`

Expected: PASS。

### Task 2: memory records API 暴露合规字段

**Files:**
- Modify: `tests/test_api_memory_graph.py`
- Modify: `app/api.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_api_memory_graph.py` 增加：

```python
def test_compact_memory_record_exposes_compliance_trace() -> None:
    compact = api._compact_memory_record(
        {
            "record_id": "op_1",
            "compliance_risk_level": "medium",
            "compliance_issues": ["内容中包含绝对词：一定"],
            "revised_content": "发布前提醒：内容仅作经验分享。",
            "compliance_summary": {
                "risk_level": "medium",
                "issue_count": 1,
                "issues": ["内容中包含绝对词：一定"],
                "has_revision": True,
            },
        }
    )

    assert compact["compliance_risk_level"] == "medium"
    assert compact["compliance_issues"] == ["内容中包含绝对词：一定"]
    assert compact["revised_content"] == "发布前提醒：内容仅作经验分享。"
    assert compact["compliance_summary"]["has_revision"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_memory_graph.py::test_compact_memory_record_exposes_compliance_trace -q`

Expected: FAIL，原因是 compact 结果尚未暴露这些字段。

- [ ] **Step 3: 实现最小代码**

在 `app/api.py` 的 `_compact_memory_record()` 返回 dict 中增加：

```python
"compliance_risk_level": record.get("compliance_risk_level") or "",
"compliance_issues": record.get("compliance_issues") or [],
"revised_content": record.get("revised_content") or "",
"compliance_summary": record.get("compliance_summary") or {},
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_memory_graph.py::test_compact_memory_record_exposes_compliance_trace -q`

Expected: PASS。

### Task 3: 历史合规风险优先使用结构化字段

**Files:**
- Modify: `tests/test_memory_graph.py`
- Modify: `app/memory_graph.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_memory_graph.py` 增加：

```python
def test_historical_compliance_risks_prefer_structured_fields() -> None:
    record = _record(
        "op_structured_risk",
        topic="小红书标题表达",
        content_type="avoid_mistakes",
        score=18,
        pain="担心标题太夸张",
    )
    record["compliance_summary"] = {
        "risk_level": "medium",
        "issue_count": 1,
        "issues": ["内容中包含绝对词：一定"],
        "has_revision": True,
    }

    result = memory_graph.query_memory_graph(
        [record],
        topic="小红书选题",
        compliance_risk_level="medium",
        compliance_issues=["内容中包含绝对词：一定"],
    )

    risk = result["historical_compliance_risks"][0]
    assert risk["record_id"] == "op_structured_risk"
    assert "compliance_summary" in risk["matched_fields"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_graph.py::test_historical_compliance_risks_prefer_structured_fields -q`

Expected: FAIL，原因是合规匹配还没有扫描 `compliance_summary`。

- [ ] **Step 3: 实现最小代码**

在 `app/memory_graph.py` 的 `_compliance_match_fields()` 字段表中加入 `compliance_summary`，并确保 `risk_level` 可从 summary 兜底。

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_graph.py::test_historical_compliance_risks_prefer_structured_fields -q`

Expected: PASS。

### Task 4: 工作台展示召回解释

**Files:**
- Modify: `tests/test_workbench_memory_visibility_static.py`
- Modify: `app/static/app.js`
- Modify: `app/static/styles.css`

- [ ] **Step 1: 写失败测试**

扩展 `test_workbench_has_memory_recall_evidence_panel()`：

```python
    assert "similar_experience_records" in APP_JS
    assert "historical_compliance_risks" in APP_JS
    assert "recall_explanations" in APP_JS
    assert "相似经验" in APP_JS
    assert "历史合规风险" in APP_JS
    assert "召回解释" in APP_JS
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_memory_visibility_static.py::test_workbench_has_memory_recall_evidence_panel -q`

Expected: FAIL，原因是工作台尚未渲染新增字段。

- [ ] **Step 3: 实现最小代码**

在 `app/static/app.js` 的 `renderMemoryRecallEvidence()` 中：

- 读取 `memoryGraph.similar_experience_records || []`。
- 读取 `memoryGraph.historical_compliance_risks || []`。
- 读取 `memoryGraph.recall_explanations || []`。
- 在现有召回依据网格中追加三个只读区块。

在 `app/static/styles.css` 中：

- 复用 `.memory-recall-grid p`。
- 如需列表间距，新增 `.memory-recall-list`。

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_memory_visibility_static.py::test_workbench_has_memory_recall_evidence_panel -q`

Expected: PASS。

### Task 5: 回归、文档和提交

**Files:**
- Modify: `memory/current_progress.md`

- [ ] **Step 1: 运行定点回归**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_operation_store_sqlite.py tests/test_api_memory_graph.py tests/test_memory_graph.py tests/test_workbench_memory_visibility_static.py -q`

Expected: PASS。

- [ ] **Step 2: 运行相关回归**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_node.py tests/test_memory_context.py tests/test_generation_memory_context.py -q`

Expected: PASS。

- [ ] **Step 3: 运行前端语法检查**

Run: `node --check app/static/app.js`

Expected: exit code 0。

- [ ] **Step 4: 运行编译检查**

Run: `D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes memory tests`

Expected: exit code 0。

- [ ] **Step 5: 更新进度文档**

在 `memory/current_progress.md` 顶部记录 M5 第五片完成内容、验证结果、当前限制和下一步。

- [ ] **Step 6: 提交**

Run:

```powershell
git add memory/operation_store.py app/api.py app/memory_graph.py app/static/app.js app/static/styles.css tests/test_operation_store_sqlite.py tests/test_api_memory_graph.py tests/test_memory_graph.py tests/test_workbench_memory_visibility_static.py memory/current_progress.md
git commit -m "feat: add m5 compliance memory visibility"
```

Expected: 本地提交成功，工作树干净。
