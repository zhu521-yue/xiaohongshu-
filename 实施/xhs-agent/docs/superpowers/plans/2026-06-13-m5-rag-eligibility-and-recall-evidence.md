# M5 RAG 入库门槛与召回依据展示实施计划

> **给执行者：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务执行本计划。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**目标：** 用现有 `rag_eligibility` 控制长期运营记忆写入，并在工作台展示当前主题的召回依据。

**架构：** 后端保持现有 LangGraph 和标准库 HTTP API 结构，只在 `write_operation_memory()` 前增加质量门槛，并把跳过原因透出到 run summary。运营记忆记录保存 `rag_eligibility`，工作台复用已有 `/memory/graph` 查询接口做只读展示，不引入新服务或新数据库。

**技术栈：** Python 标准库 HTTP API、LangGraph 节点、JSON/SQLite operation memory、原生 HTML/CSS/JavaScript、pytest、node syntax check。

---

## 文件结构

- 修改 `nodes/memory_node.py`：增加 `rag_eligibility` 写入门槛和紧凑跳过原因。
- 修改 `memory/operation_store.py`：让 `record_from_state()` 保存 `rag_eligibility`。
- 修改 `app/api.py`：在 run summary 和 memory records API 中暴露新增字段。
- 修改 `app/static/index.html`：给工作台增加召回依据容器。
- 修改 `app/static/app.js`：加载 `/memory/graph` 并渲染推荐内容类型、相关痛点和召回记录。
- 修改 `app/static/styles.css`：补召回依据区紧凑样式。
- 修改 `tests/test_memory_node.py`：覆盖入库门槛。
- 修改 `tests/test_operation_store_sqlite.py`：覆盖记录留痕。
- 修改或新增 `tests/test_api_memory_graph.py`：覆盖 API 摘要字段。
- 修改 `tests/test_workbench_memory_visibility_static.py`：覆盖工作台静态结构。
- 修改 `memory/current_progress.md` 和 `memory/project_status_and_roadmap.md`：记录本轮完成内容、验证结果和限制。

## Task 1：运营记忆写入门槛

**Files:**
- Modify: `实施/xhs-agent/nodes/memory_node.py`
- Test: `实施/xhs-agent/tests/test_memory_node.py`

- [ ] **Step 1：写失败测试：不合格 run 跳过长期记忆写入**

在 `tests/test_memory_node.py` 追加：

```python
def test_write_operation_memory_skips_when_rag_eligibility_blocked(monkeypatch) -> None:
    called = {"upsert": False}

    def fake_upsert(state):
        called["upsert"] = True
        return {"record_id": "op_should_not_write"}

    monkeypatch.setattr(memory_node, "upsert_record_from_state", fake_upsert)

    result = memory_node.write_operation_memory(
        {
            "publish_status": "success",
            "next_action": "重新采集更多评论。",
            "rag_eligibility": {
                "eligible": False,
                "level": "blocked",
                "score": 35,
                "blocking_reasons": ["评论样本较少", "痛点证据不足"],
                "recommended_action": "重新采集更多候选和评论后再进入 RAG 入库。",
            },
        }
    )

    assert called["upsert"] is False
    assert result["operation_memory_written"] is False
    assert result["operation_memory_skip_reason"] == "rag_eligibility_blocked"
    assert result["operation_memory_skip_detail"] == {
        "level": "blocked",
        "score": 35,
        "blocking_reasons": ["评论样本较少", "痛点证据不足"],
        "recommended_action": "重新采集更多候选和评论后再进入 RAG 入库。",
    }
```

- [ ] **Step 2：运行失败测试**

Run:

```powershell
cd .\实施\xhs-agent
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_node.py::test_write_operation_memory_skips_when_rag_eligibility_blocked -q
```

Expected: FAIL，原因是 `operation_memory_skip_reason` 不存在，或 `upsert_record_from_state()` 被调用。

- [ ] **Step 3：实现最小门槛逻辑**

在 `nodes/memory_node.py` 中增加 helper：

```python
def _rag_skip_detail(rag_eligibility: object) -> dict:
    if not isinstance(rag_eligibility, dict):
        return {}
    return {
        "level": rag_eligibility.get("level") or "",
        "score": rag_eligibility.get("score") or 0,
        "blocking_reasons": rag_eligibility.get("blocking_reasons") or [],
        "recommended_action": rag_eligibility.get("recommended_action") or "",
    }


def _is_rag_blocked(state: XHSState) -> bool:
    rag_eligibility = state.get("rag_eligibility")
    return isinstance(rag_eligibility, dict) and rag_eligibility.get("eligible") is False
```

在 `write_operation_memory()` 的 `publish_status` 检查之后、`upsert_record_from_state(state)` 之前加入：

```python
    if _is_rag_blocked(state):
        return {
            "next_action": next_action,
            "operation_memory_path": str(operation_memory_path()),
            "operation_memory_written": False,
            "operation_memory_skip_reason": "rag_eligibility_blocked",
            "operation_memory_skip_detail": _rag_skip_detail(state.get("rag_eligibility")),
        }
```

- [ ] **Step 4：运行测试确认通过**

Run:

```powershell
cd .\实施\xhs-agent
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_node.py -q
```

Expected: PASS，`test_write_operation_memory_skips_when_rag_eligibility_blocked` 和既有记忆节点测试均通过。

- [ ] **Step 5：补兼容测试：缺失 `rag_eligibility` 时仍写入**

在 `tests/test_memory_node.py` 追加：

```python
def test_write_operation_memory_allows_legacy_state_without_rag_eligibility(monkeypatch) -> None:
    captured = {}

    def fake_upsert(state):
        captured["state"] = state
        return {"record_id": "op_legacy"}

    monkeypatch.setattr(memory_node, "upsert_record_from_state", fake_upsert)

    result = memory_node.write_operation_memory(
        {
            "publish_status": "success",
            "next_action": "发布后录入表现数据。",
        }
    )

    assert captured["state"]["publish_status"] == "success"
    assert result["operation_memory_written"] is True
    assert result["operation_record_id"] == "op_legacy"
    assert "operation_memory_skip_reason" not in result
```

- [ ] **Step 6：运行兼容测试**

Run:

```powershell
cd .\实施\xhs-agent
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_node.py::test_write_operation_memory_allows_legacy_state_without_rag_eligibility -q
```

Expected: PASS。

- [ ] **Step 7：提交 Task 1**

Run:

```powershell
git add 实施/xhs-agent/nodes/memory_node.py 实施/xhs-agent/tests/test_memory_node.py
git commit -m "feat: gate operation memory by rag eligibility"
```

Expected: commit 成功，且不暂存 `AGENTS.md` 或既有进度文档脏改。

## Task 2：运营记忆记录保存 `rag_eligibility`

**Files:**
- Modify: `实施/xhs-agent/memory/operation_store.py`
- Test: `实施/xhs-agent/tests/test_operation_store_sqlite.py`

- [ ] **Step 1：写失败测试：记录保存 RAG 门槛信息**

在 `tests/test_operation_store_sqlite.py` 追加：

```python
def test_operation_memory_record_keeps_rag_eligibility(sqlite_memory: Path) -> None:
    state = sample_state("output/rag-eligible.md")
    state["rag_eligibility"] = {
        "eligible": True,
        "level": "eligible",
        "score": 82,
        "reasons": ["评论样本达到最低要求"],
        "blocking_reasons": [],
        "recommended_action": "可以进入后续 RAG 入库候选。",
    }

    saved = store.upsert_record_from_state(state)
    loaded = store.load_history()["records"][0]

    assert saved["rag_eligibility"]["eligible"] is True
    assert loaded["rag_eligibility"]["score"] == 82
    assert loaded["rag_eligibility"]["recommended_action"] == "可以进入后续 RAG 入库候选。"
```

- [ ] **Step 2：运行失败测试**

Run:

```powershell
cd .\实施\xhs-agent
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_operation_store_sqlite.py::test_operation_memory_record_keeps_rag_eligibility -q
```

Expected: FAIL，原因是 `rag_eligibility` 字段缺失。

- [ ] **Step 3：实现最小记录字段**

在 `memory/operation_store.py` 的 `record_from_state()` 返回 dict 中，紧跟 `comment_insights` 后加入：

```python
        "rag_eligibility": state.get("rag_eligibility") if isinstance(state.get("rag_eligibility"), dict) else {},
```

- [ ] **Step 4：运行记录测试**

Run:

```powershell
cd .\实施\xhs-agent
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_operation_store_sqlite.py -q
```

Expected: PASS，SQLite 和显式 JSON path 测试均通过。

- [ ] **Step 5：提交 Task 2**

Run:

```powershell
git add 实施/xhs-agent/memory/operation_store.py 实施/xhs-agent/tests/test_operation_store_sqlite.py
git commit -m "feat: persist rag eligibility in operation memory"
```

Expected: commit 成功。

## Task 3：API 摘要字段

**Files:**
- Modify: `实施/xhs-agent/app/api.py`
- Test: `实施/xhs-agent/tests/test_api_memory_graph.py`

- [ ] **Step 1：写失败测试：run summary 暴露跳过原因**

在 `tests/test_api_memory_graph.py` 追加：

```python
def test_state_summary_exposes_operation_memory_skip_detail() -> None:
    summary = api._state_summary(
        {
            "operation_memory_written": False,
            "operation_memory_skip_reason": "rag_eligibility_blocked",
            "operation_memory_skip_detail": {
                "level": "blocked",
                "score": 20,
                "blocking_reasons": ["评论样本较少"],
                "recommended_action": "重新采集更多候选和评论后再进入 RAG 入库。",
            },
        }
    )

    assert summary["operation_memory_written"] is False
    assert summary["operation_memory_skip_reason"] == "rag_eligibility_blocked"
    assert summary["operation_memory_skip_detail"]["blocking_reasons"] == ["评论样本较少"]
```

- [ ] **Step 2：运行失败测试**

Run:

```powershell
cd .\实施\xhs-agent
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_memory_graph.py::test_state_summary_exposes_operation_memory_skip_detail -q
```

Expected: FAIL，原因是 summary 中没有 skip 字段。

- [ ] **Step 3：实现 run summary 字段**

在 `app/api.py` 的 `_state_summary()` 返回 dict 中，紧跟 `operation_record_id` 后加入：

```python
        "operation_memory_skip_reason": state.get("operation_memory_skip_reason"),
        "operation_memory_skip_detail": state.get("operation_memory_skip_detail") or {},
```

- [ ] **Step 4：写失败测试：memory records API 暴露 `rag_eligibility`**

在 `tests/test_api_memory_graph.py` 追加：

```python
def test_compact_memory_record_exposes_rag_eligibility() -> None:
    compact = api._compact_memory_record(
        {
            "record_id": "op_1",
            "topic": "小红书选题",
            "title": "选题三步法",
            "rag_eligibility": {
                "eligible": True,
                "level": "eligible",
                "score": 90,
            },
        }
    )

    assert compact["rag_eligibility"] == {
        "eligible": True,
        "level": "eligible",
        "score": 90,
    }
```

- [ ] **Step 5：运行失败测试**

Run:

```powershell
cd .\实施\xhs-agent
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_memory_graph.py::test_compact_memory_record_exposes_rag_eligibility -q
```

Expected: FAIL，原因是 compact memory record 中没有 `rag_eligibility`。

- [ ] **Step 6：实现 compact memory record 字段**

在 `app/api.py` 的 `_compact_memory_record()` 返回 dict 中，紧跟 `comment_insights` 或 `performance_score` 附近加入：

```python
        "rag_eligibility": record.get("rag_eligibility") or {},
```

- [ ] **Step 7：运行 API 定点测试**

Run:

```powershell
cd .\实施\xhs-agent
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_memory_graph.py -q
```

Expected: PASS。

- [ ] **Step 8：提交 Task 3**

Run:

```powershell
git add 实施/xhs-agent/app/api.py 实施/xhs-agent/tests/test_api_memory_graph.py
git commit -m "feat: expose rag memory gate metadata"
```

Expected: commit 成功。

## Task 4：工作台召回依据展示

**Files:**
- Modify: `实施/xhs-agent/app/static/index.html`
- Modify: `实施/xhs-agent/app/static/app.js`
- Modify: `实施/xhs-agent/app/static/styles.css`
- Test: `实施/xhs-agent/tests/test_workbench_memory_visibility_static.py`

- [ ] **Step 1：写失败测试：静态结构包含召回依据区**

在 `tests/test_workbench_memory_visibility_static.py` 顶部加入：

```python
INDEX_HTML = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
```

追加测试：

```python
def test_workbench_has_memory_recall_evidence_panel():
    assert 'id="memoryRecallEvidence"' in INDEX_HTML
    assert "renderMemoryRecallEvidence" in APP_JS
    assert 'apiGet(`/memory/graph?topic=${encodeURIComponent(topic)}&limit=5`)' in APP_JS
    assert "recommended_content_types" in APP_JS
    assert "related_pain_points" in APP_JS
    assert "recall_evidence" in APP_JS
    assert ".memory-recall-evidence" in STYLES_CSS
```

- [ ] **Step 2：运行失败测试**

Run:

```powershell
cd .\实施\xhs-agent
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_memory_visibility_static.py::test_workbench_has_memory_recall_evidence_panel -q
```

Expected: FAIL，原因是页面和 JS 尚未包含召回依据区。

- [ ] **Step 3：新增 HTML 容器**

在 `app/static/index.html` 的运营记忆面板中，`<div class="memory-list" id="memoryList"></div>` 前加入：

```html
          <div class="memory-recall-evidence" id="memoryRecallEvidence"></div>
```

- [ ] **Step 4：新增元素引用**

在 `app/static/app.js` 的 `elements` 中，紧跟 `memoryList` 加入：

```javascript
  memoryRecallEvidence: $("#memoryRecallEvidence"),
```

- [ ] **Step 5：新增召回依据渲染函数**

在 `renderMemory(records)` 前加入：

```javascript
function renderMemoryRecallEvidence(memoryGraph, errorMessage = "") {
  if (errorMessage) {
    elements.memoryRecallEvidence.innerHTML = `<div class="memory-recall-empty">${escapeHtml(errorMessage)}</div>`;
    return;
  }
  if (!memoryGraph || !memoryGraph.graph || !memoryGraph.graph.record_count) {
    elements.memoryRecallEvidence.innerHTML = `<div class="memory-recall-empty">暂无召回依据</div>`;
    return;
  }
  const recommended = memoryGraph.recommended_content_types || [];
  const pains = memoryGraph.related_pain_points || [];
  const evidence = memoryGraph.recall_evidence || [];
  elements.memoryRecallEvidence.innerHTML = `
    <div class="memory-recall-head">
      <strong>召回依据</strong>
      <span class="mini-pill">${escapeHtml(memoryGraph.graph.record_count)} 条</span>
    </div>
    <div class="memory-recall-grid">
      <div>
        <span class="metric-label">推荐结构</span>
        ${
          recommended.length
            ? recommended.slice(0, 3).map((item) => `<p>${escapeHtml(item.content_type || "-")} · ${escapeHtml(item.max_score ?? 0)}</p>`).join("")
            : `<p class="muted">暂无推荐</p>`
        }
      </div>
      <div>
        <span class="metric-label">相关痛点</span>
        ${
          pains.length
            ? pains.slice(0, 3).map((item) => `<p>${escapeHtml(item.pain || "-")}</p>`).join("")
            : `<p class="muted">暂无痛点</p>`
        }
      </div>
      <div>
        <span class="metric-label">召回记录</span>
        ${
          evidence.length
            ? evidence.slice(0, 3).map((item) => `<p>${escapeHtml(item.title || item.topic || item.record_id || "-")}</p>`).join("")
            : `<p class="muted">暂无记录</p>`
        }
      </div>
    </div>
  `;
}
```

- [ ] **Step 6：新增加载函数**

在 `refreshAll()` 前加入：

```javascript
async function loadMemoryRecallEvidence(topic) {
  if (!topic) {
    renderMemoryRecallEvidence(null);
    return;
  }
  try {
    const data = await apiGet(`/memory/graph?topic=${encodeURIComponent(topic)}&limit=5`);
    renderMemoryRecallEvidence(data.memory_graph || {});
  } catch (error) {
    renderMemoryRecallEvidence(null, error.message);
  }
}
```

- [ ] **Step 7：在选中 run 后加载召回依据**

在 `renderRun(run)` 末尾、填充 `post_id` 逻辑之后加入：

```javascript
  loadMemoryRecallEvidence(run.request?.topic || run.state?.user_topic || "");
```

在 `refreshAll()` 末尾加入当前 run 兜底：

```javascript
  if (!state.currentRun) {
    renderMemoryRecallEvidence(null);
  }
```

- [ ] **Step 8：新增样式**

在 `app/static/styles.css` 的 `.memory-list` 附近加入：

```css
.memory-recall-evidence {
  display: grid;
  gap: 8px;
  padding: 0 14px 12px;
  border-bottom: 1px solid var(--line);
}

.memory-recall-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.memory-recall-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(140px, 1fr));
  gap: 8px;
}

.memory-recall-grid > div,
.memory-recall-empty {
  min-height: 58px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fbfcf9;
}

.memory-recall-grid p {
  margin: 4px 0 0;
  overflow-wrap: anywhere;
}
```

在移动端 media query 中加入：

```css
  .memory-recall-grid {
    grid-template-columns: 1fr;
  }
```

- [ ] **Step 9：运行静态测试和 JS 语法检查**

Run:

```powershell
cd .\实施\xhs-agent
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_memory_visibility_static.py -q
node --check app/static/app.js
```

Expected: pytest PASS，`node --check` exit code 0。

- [ ] **Step 10：提交 Task 4**

Run:

```powershell
git add 实施/xhs-agent/app/static/index.html 实施/xhs-agent/app/static/app.js 实施/xhs-agent/app/static/styles.css 实施/xhs-agent/tests/test_workbench_memory_visibility_static.py
git commit -m "feat: show memory recall evidence in workbench"
```

Expected: commit 成功。

## Task 5：文档、回归与收口

**Files:**
- Modify: `实施/xhs-agent/memory/current_progress.md`
- Modify: `实施/xhs-agent/memory/project_status_and_roadmap.md`

- [ ] **Step 1：运行后端定点回归**

Run:

```powershell
cd .\实施\xhs-agent
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_node.py tests/test_operation_store_sqlite.py tests/test_api_memory_graph.py -q
```

Expected: PASS。

- [ ] **Step 2：运行前端静态回归**

Run:

```powershell
cd .\实施\xhs-agent
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_memory_visibility_static.py -q
node --check app/static/app.js
```

Expected: PASS，JS 语法检查 exit code 0。

- [ ] **Step 3：运行相关 M5 回归**

Run:

```powershell
cd .\实施\xhs-agent
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_graph.py tests/test_memory_context.py tests/test_strategy_memory_context.py tests/test_generation_memory_context.py tests/test_memory_node.py -q
```

Expected: PASS。

- [ ] **Step 4：运行编译检查**

Run:

```powershell
cd .\实施\xhs-agent
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes memory tests
```

Expected: exit code 0。

- [ ] **Step 5：更新 `memory/current_progress.md`**

在文件顶部新增小节，内容包含：

```markdown
## 2026-06-13 M5 RAG 入库门槛与召回依据展示

本轮继续推进 M5 第三片：在不引入向量库、图数据库或新外部服务的前提下，用 `rag_eligibility` 控制长期运营记忆写入，并在工作台展示当前主题的召回依据。

已完成：
- `write_operation_memory()` 会在 `publish_status=success` 后检查 `rag_eligibility`；明确 blocked 的 run 不再写入长期运营记忆。
- run summary 会返回 `operation_memory_skip_reason` 和 `operation_memory_skip_detail`。
- 运营记忆记录保存 `rag_eligibility`，用于后续入库审计和补偿。
- 工作台复用 `/memory/graph?topic=...` 展示推荐内容类型、相关痛点和召回记录。

当前限制：
- 本轮不改变历史召回过滤逻辑，不过滤旧记录。
- 本轮不是完整 RAG/GraphRAG：仍没有 embedding、向量检索、图数据库或跨主题语义召回。
- 工作台只做结构化文本展示，不做复杂图谱可视化。

验证：
- 记录实际运行过的 pytest、node --check 和 compileall 命令及结果。
```

- [ ] **Step 6：更新 `memory/project_status_and_roadmap.md`**

在 M5 最新小节后追加：

```markdown
## 39. 2026-06-13 M5 RAG 入库门槛与召回依据展示完成

本次完成 M5 第三片最小闭环：`rag_eligibility` 开始控制长期运营记忆写入，工作台可以查看当前主题的召回依据。

路线图影响：
- “按 `rag_eligibility` 控制可入库记忆”从待办调整为初版完成。
- “前端查看召回依据”从未完成调整为轻量展示初版完成。
- 向量检索、embedding、跨主题语义召回、合规风险历史召回、历史大迁移和复杂图谱可视化继续后置。
```

- [ ] **Step 7：检查 diff**

Run:

```powershell
git status --short
git diff --stat
```

Expected: 只包含本轮实现文件、测试文件、计划/进度文档，以及用户既有未暂存 `AGENTS.md` 改动。不要暂存无关文件。

- [ ] **Step 8：提交文档收口**

Run:

```powershell
git add 实施/xhs-agent/memory/current_progress.md 实施/xhs-agent/memory/project_status_and_roadmap.md 实施/xhs-agent/docs/superpowers/plans/2026-06-13-m5-rag-eligibility-and-recall-evidence.md
git commit -m "docs: record rag eligibility recall evidence progress"
```

Expected: commit 成功；如果 `current_progress.md` 中包含本会话早前“项目阅读与下一主线确认”未提交内容，本次一起纳入文档收口提交。

## 自检清单

- 规格覆盖：写入门槛、记录留痕、API 摘要、工作台展示、错误处理和测试均有任务覆盖。
- 范围控制：没有引入 embedding、向量库、图数据库、新服务或真实平台写入。
- TDD：每个行为改动都有失败测试步骤，且实现步骤在失败测试之后。
- 类型一致：字段名统一为 `operation_memory_skip_reason`、`operation_memory_skip_detail`、`rag_eligibility`、`memoryRecallEvidence`。
- 遗留边界：历史记录过滤、历史大迁移、复杂图谱可视化和向量召回均明确后置。
