# M5 GraphRAG Memory Consumption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让现有 `graphrag_memory` 被策略节点和图文/视频 LLM prompt 稳定消费，同时保持记忆为空时的旧行为不变。

**Architecture:** 新增 `nodes/memory_context.py` 作为唯一适配层，负责清洗、裁剪、过滤和压缩 `graphrag_memory`。策略节点只通过该适配层读取推荐内容类型；图文和视频节点只通过该适配层构造 `memory_context` prompt payload。

**Tech Stack:** Python 3、pytest、现有 LangGraph state、现有 JSON prompt builder、现有 `app.rules` 内容规则。

---

## 文件结构

- Create: `nodes/memory_context.py`
  - 从 `XHSState.graphrag_memory` 提取稳定的推荐类型和生成上下文。
- Modify: `nodes/strategy_node.py`
  - 在关键词规则之后、`successful_patterns` 之前使用 GraphRAG 推荐类型。
- Modify: `nodes/content_node.py`
  - 图文 LLM prompt payload 增加 `memory_context`。
- Modify: `nodes/video_node.py`
  - 视频 LLM prompt payload 增加 `memory_context`。
- Create: `tests/test_memory_context.py`
  - 覆盖适配层清洗、过滤和裁剪。
- Create: `tests/test_strategy_memory_context.py`
  - 覆盖策略优先级。
- Create: `tests/test_generation_memory_context.py`
  - 覆盖图文/视频 prompt payload。
- Modify: `memory/current_progress.md`
  - 记录本轮完成内容、验证结果和遗留问题。
- Modify: `memory/project_status_and_roadmap.md`
  - 更新 M5 第二片状态和后续任务。

## Task 1: 记忆上下文适配层

**Files:**
- Create: `nodes/memory_context.py`
- Test: `tests/test_memory_context.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_memory_context.py`:

```python
from nodes.memory_context import (
    build_generation_memory_context,
    has_memory_evidence,
    recommended_memory_content_type,
)


def _state(graphrag_memory: dict) -> dict:
    return {"graphrag_memory": graphrag_memory}


def test_recommended_memory_content_type_uses_evidenced_valid_type() -> None:
    result = recommended_memory_content_type(
        _state(
            {
                "recommended_content_types": [
                    {"content_type": "step_tutorial", "count": 2, "max_score": 90}
                ],
                "recall_evidence": [{"record_id": "op_1"}],
            }
        )
    )

    assert result == "step_tutorial"


def test_recommended_memory_content_type_ignores_recommendation_without_evidence() -> None:
    result = recommended_memory_content_type(
        _state(
            {
                "recommended_content_types": [
                    {"content_type": "step_tutorial", "count": 2, "max_score": 90}
                ],
                "recall_evidence": [],
                "related_records": [],
            }
        )
    )

    assert result is None


def test_recommended_memory_content_type_ignores_invalid_type() -> None:
    result = recommended_memory_content_type(
        _state(
            {
                "recommended_content_types": [
                    {"content_type": "unknown_type", "count": 3, "max_score": 95},
                    {"content_type": "qa_education", "count": 1, "max_score": 80},
                ],
                "recall_evidence": [{"record_id": "op_2"}],
            }
        )
    )

    assert result == "qa_education"


def test_generation_memory_context_compacts_and_limits_fields() -> None:
    context = build_generation_memory_context(
        _state(
            {
                "query": "小红书选题",
                "recommended_content_types": [
                    {"content_type": "step_tutorial", "count": 2, "average_score": 81.5, "max_score": 90}
                ],
                "related_pain_points": [
                    {"pain": "不知道第一步怎么做", "count": 2, "max_score": 90, "record_ids": ["op_1"]}
                ],
                "recall_evidence": [
                    {
                        "record_id": "op_1",
                        "topic": "小红书选题",
                        "title": "选题方法",
                        "content_type": "step_tutorial",
                        "content_format": "image_text",
                        "performance_score": 90,
                        "review_summary": "表现好",
                        "performance_data": {"likes": 100},
                    }
                ],
            }
        ),
        limit=1,
    )

    assert context == {
        "enabled": True,
        "query": "小红书选题",
        "recommended_content_types": [
            {"content_type": "step_tutorial", "count": 2, "average_score": 81.5, "max_score": 90}
        ],
        "related_pain_points": [
            {"pain": "不知道第一步怎么做", "count": 2, "max_score": 90}
        ],
        "recall_evidence": [
            {
                "record_id": "op_1",
                "topic": "小红书选题",
                "title": "选题方法",
                "content_type": "step_tutorial",
                "performance_score": 90,
            }
        ],
    }


def test_empty_generation_memory_context_is_disabled() -> None:
    context = build_generation_memory_context({})

    assert context == {
        "enabled": False,
        "query": "",
        "recommended_content_types": [],
        "related_pain_points": [],
        "recall_evidence": [],
    }
    assert has_memory_evidence({}) is False
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_context.py -q
```

Expected: FAIL，原因是 `nodes.memory_context` 还不存在。

- [ ] **Step 3: 实现最小适配层**

Create `nodes/memory_context.py`:

```python
from __future__ import annotations

from typing import Any

from app.rules import load_content_rules
from app.state import XHSState


_CONTENT_RULES = load_content_rules()
VALID_CONTENT_TYPES = set(_CONTENT_RULES.get("valid_content_types") or [])


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _memory(state: XHSState) -> dict[str, Any]:
    return _as_dict(state.get("graphrag_memory"))


def _evidence_items(memory: dict[str, Any]) -> list[Any]:
    evidence = _as_list(memory.get("recall_evidence"))
    if evidence:
        return evidence
    return _as_list(memory.get("related_records"))


def has_memory_evidence(state: XHSState) -> bool:
    return bool(_evidence_items(_memory(state)))


def recommended_memory_content_type(state: XHSState, min_evidence_count: int = 1) -> str | None:
    memory = _memory(state)
    if len(_evidence_items(memory)) < min_evidence_count:
        return None

    for item in _as_list(memory.get("recommended_content_types")):
        item_dict = _as_dict(item)
        content_type = str(item_dict.get("content_type") or "")
        if content_type not in VALID_CONTENT_TYPES:
            continue
        if _safe_int(item_dict.get("count")) <= 0 and _safe_int(item_dict.get("max_score")) <= 0:
            continue
        return content_type
    return None


def _compact_recommendations(memory: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _as_list(memory.get("recommended_content_types")):
        item_dict = _as_dict(item)
        content_type = str(item_dict.get("content_type") or "")
        if content_type not in VALID_CONTENT_TYPES:
            continue
        result.append(
            {
                "content_type": content_type,
                "count": _safe_int(item_dict.get("count")),
                "average_score": round(_safe_float(item_dict.get("average_score")), 2),
                "max_score": _safe_int(item_dict.get("max_score")),
            }
        )
    return result[: max(0, int(limit))]


def _compact_pain_points(memory: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _as_list(memory.get("related_pain_points")):
        item_dict = _as_dict(item)
        pain = str(item_dict.get("pain") or "").strip()
        if not pain:
            continue
        result.append(
            {
                "pain": pain,
                "count": _safe_int(item_dict.get("count")),
                "max_score": _safe_int(item_dict.get("max_score")),
            }
        )
    return result[: max(0, int(limit))]


def _compact_evidence(memory: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _evidence_items(memory):
        item_dict = _as_dict(item)
        record_id = str(item_dict.get("record_id") or "").strip()
        title = str(item_dict.get("title") or "").strip()
        topic = str(item_dict.get("topic") or "").strip()
        if not record_id and not title and not topic:
            continue
        result.append(
            {
                "record_id": record_id,
                "topic": topic,
                "title": title,
                "content_type": str(item_dict.get("content_type") or ""),
                "performance_score": _safe_int(item_dict.get("performance_score")),
            }
        )
    return result[: max(0, int(limit))]


def build_generation_memory_context(state: XHSState, limit: int = 3) -> dict[str, Any]:
    memory = _memory(state)
    recommendations = _compact_recommendations(memory, limit)
    pain_points = _compact_pain_points(memory, limit)
    evidence = _compact_evidence(memory, limit)
    enabled = bool(recommendations or pain_points or evidence)

    return {
        "enabled": enabled,
        "query": str(memory.get("query") or "") if enabled else "",
        "recommended_content_types": recommendations,
        "related_pain_points": pain_points,
        "recall_evidence": evidence,
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_context.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交适配层**

Run:

```powershell
git add nodes/memory_context.py tests/test_memory_context.py
git commit -m "feat: add memory context adapter"
```

## Task 2: 策略节点消费 GraphRAG 推荐

**Files:**
- Modify: `nodes/strategy_node.py`
- Test: `tests/test_strategy_memory_context.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_strategy_memory_context.py`:

```python
from nodes.strategy_node import decide_content_strategy


def _state(**overrides) -> dict:
    state = {
        "user_topic": "小红书选题",
        "pain_points": [{"pain": "不知道怎么开始", "evidence": "第一步是什么"}],
        "user_selected_format": "image_text",
        "successful_patterns": [],
        "account_stage": "growth",
        "allow_soft_ad": False,
    }
    state.update(overrides)
    return state


def test_strategy_uses_graphrag_recommended_content_type_when_evidenced() -> None:
    result = decide_content_strategy(
        _state(
            graphrag_memory={
                "recommended_content_types": [
                    {"content_type": "qa_education", "count": 2, "max_score": 88}
                ],
                "recall_evidence": [{"record_id": "op_1"}],
            }
        )
    )

    assert result["content_type"] == "qa_education"


def test_strategy_keyword_rule_still_overrides_graphrag_recommendation() -> None:
    result = decide_content_strategy(
        _state(
            pain_points=[{"pain": "这些坑怎么避开", "evidence": "踩坑了"}],
            graphrag_memory={
                "recommended_content_types": [
                    {"content_type": "qa_education", "count": 2, "max_score": 88}
                ],
                "recall_evidence": [{"record_id": "op_1"}],
            },
        )
    )

    assert result["content_type"] == "avoid_mistakes"


def test_strategy_ignores_graphrag_recommendation_without_evidence() -> None:
    result = decide_content_strategy(
        _state(
            graphrag_memory={
                "recommended_content_types": [
                    {"content_type": "qa_education", "count": 2, "max_score": 88}
                ],
                "recall_evidence": [],
            }
        )
    )

    assert result["content_type"] == "knowledge_share"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_strategy_memory_context.py -q
```

Expected: FAIL，原因是策略节点尚未消费 GraphRAG 推荐。

- [ ] **Step 3: 最小实现策略接入**

Modify `nodes/strategy_node.py`:

```python
from nodes.memory_context import recommended_memory_content_type
```

在 `_choose_content_type()` 的关键词规则之后加入：

```python
    memory_content_type = recommended_memory_content_type(state)
    if memory_content_type:
        return memory_content_type
```

保留 `successful_patterns` 和默认逻辑不变。

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_strategy_memory_context.py tests/test_memory_context.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交策略接入**

Run:

```powershell
git add nodes/strategy_node.py tests/test_strategy_memory_context.py
git commit -m "feat: use graphrag memory in strategy"
```

## Task 3: 图文和视频 prompt 消费记忆上下文

**Files:**
- Modify: `nodes/content_node.py`
- Modify: `nodes/video_node.py`
- Test: `tests/test_generation_memory_context.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_generation_memory_context.py`:

```python
from nodes import content_node, video_node


def _state() -> dict:
    return {
        "user_topic": "小红书选题",
        "target_user": "新手博主",
        "content_type": "knowledge_share",
        "pain_points": [{"pain": "不知道第一步怎么做"}],
        "comment_insights": [{"pain": "不知道第一步怎么做", "evidence_comments": ["第一步是什么"]}],
        "successful_patterns": [],
        "graphrag_memory": {
            "query": "小红书选题",
            "recommended_content_types": [
                {"content_type": "step_tutorial", "count": 2, "average_score": 82.5, "max_score": 91}
            ],
            "related_pain_points": [
                {"pain": "不知道第一步怎么做", "count": 2, "max_score": 91}
            ],
            "recall_evidence": [
                {
                    "record_id": "op_1",
                    "topic": "小红书选题",
                    "title": "选题第一步",
                    "content_type": "step_tutorial",
                    "performance_score": 91,
                }
            ],
        },
    }


def test_image_text_prompt_includes_memory_context(monkeypatch) -> None:
    captured: dict = {}

    def fake_build_json_prompt(template_name: str, input_payload: dict) -> list:
        captured["template_name"] = template_name
        captured["input_payload"] = input_payload
        return []

    monkeypatch.setattr(content_node, "build_json_prompt", fake_build_json_prompt)

    content_node._build_image_text_prompt(
        state=_state(),
        profile={"content_type": "knowledge_share", "label": "知识分享"},
        content_label="知识分享",
        pain_points=["不知道第一步怎么做"],
        comment_insights=[],
        patterns=[],
        primary_pain="不知道第一步怎么做",
    )

    assert captured["template_name"] == "image_text_generation"
    assert captured["input_payload"]["memory_context"]["enabled"] is True
    assert captured["input_payload"]["memory_context"]["recall_evidence"][0]["record_id"] == "op_1"


def test_video_prompt_includes_memory_context(monkeypatch) -> None:
    captured: dict = {}

    def fake_build_json_prompt(template_name: str, input_payload: dict) -> list:
        captured["template_name"] = template_name
        captured["input_payload"] = input_payload
        return []

    monkeypatch.setattr(video_node, "build_json_prompt", fake_build_json_prompt)

    video_node._build_video_prompt(
        state=_state(),
        profile={"content_type": "knowledge_share", "label": "知识分享"},
        pain_points=["不知道第一步怎么做"],
        comment_insights=[],
        patterns=[],
        primary_pain="不知道第一步怎么做",
    )

    assert captured["template_name"] == "video_script_generation"
    assert captured["input_payload"]["memory_context"]["enabled"] is True
    assert captured["input_payload"]["memory_context"]["recommended_content_types"][0]["content_type"] == "step_tutorial"


def test_generation_prompt_uses_disabled_memory_context_when_empty(monkeypatch) -> None:
    captured: dict = {}

    def fake_build_json_prompt(template_name: str, input_payload: dict) -> list:
        captured["input_payload"] = input_payload
        return []

    monkeypatch.setattr(content_node, "build_json_prompt", fake_build_json_prompt)

    state = _state()
    state["graphrag_memory"] = {}
    content_node._build_image_text_prompt(
        state=state,
        profile={"content_type": "knowledge_share", "label": "知识分享"},
        content_label="知识分享",
        pain_points=[],
        comment_insights=[],
        patterns=[],
        primary_pain="小红书选题",
    )

    assert captured["input_payload"]["memory_context"] == {
        "enabled": False,
        "query": "",
        "recommended_content_types": [],
        "related_pain_points": [],
        "recall_evidence": [],
    }
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_generation_memory_context.py -q
```

Expected: FAIL，原因是 prompt payload 尚未包含 `memory_context`。

- [ ] **Step 3: 最小实现 prompt 接入**

Modify `nodes/content_node.py`:

```python
from nodes.memory_context import build_generation_memory_context
```

在 `_build_image_text_prompt()` 的 `input_payload` 中加入：

```python
        "memory_context": build_generation_memory_context(state),
```

Modify `nodes/video_node.py`:

```python
from nodes.memory_context import build_generation_memory_context
```

在 `_build_video_prompt()` 的 `input_payload` 中加入：

```python
        "memory_context": build_generation_memory_context(state),
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_generation_memory_context.py tests/test_memory_context.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交生成接入**

Run:

```powershell
git add nodes/content_node.py nodes/video_node.py tests/test_generation_memory_context.py
git commit -m "feat: pass graphrag memory to generation prompts"
```

## Task 4: 相关回归和进度文档

**Files:**
- Modify: `memory/current_progress.md`
- Modify: `memory/project_status_and_roadmap.md`

- [ ] **Step 1: 运行新增定点测试**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_context.py tests/test_strategy_memory_context.py tests/test_generation_memory_context.py -q
```

Expected: PASS。

- [ ] **Step 2: 运行相关回归**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_memory_graph.py tests/test_memory_node.py tests/test_graph_run_events.py tests/test_langgraph_runtime.py -q
```

Expected: PASS。

- [ ] **Step 3: 运行编译检查**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes memory platforms scripts tests
```

Expected: exit code 0。

- [ ] **Step 4: 更新进度文档**

在 `memory/current_progress.md` 顶部新增小节，记录：

- M5 第二片已完成：GraphRAG 记忆进入策略和 LLM prompt。
- 新增 `nodes/memory_context.py` 作为消费侧适配层。
- 策略优先级为：关键词 > GraphRAG 推荐 > `successful_patterns` > 默认。
- 验证命令和结果。
- 遗留问题：真正 RAG 入库、向量召回、`rag_eligibility` 控制入库、前端召回展示、正式公网部署。

在 `memory/project_status_and_roadmap.md` 新增或更新 M5 小节，记录：

- M5 第一片：派生 GraphRAG 风格记忆视图。
- M5 第二片：消费侧初版完成。
- 后续仍需真正 RAG 入库和可视化。

- [ ] **Step 5: 检查 git diff**

Run:

```powershell
git status --short
git diff --stat
```

Expected: 只包含本轮文件和用户既有 `AGENTS.md` 修改；不要暂存 `AGENTS.md`。

- [ ] **Step 6: 提交文档更新**

Run:

```powershell
git add memory/current_progress.md memory/project_status_and_roadmap.md docs/superpowers/plans/2026-06-13-m5-graphrag-memory-consumption.md
git commit -m "docs: plan graphrag memory consumption"
```

## Self-Review Checklist

- 设计要求均有任务覆盖：适配层、策略消费、生成 prompt 消费、文档和验证。
- 计划没有要求引入向量库、图数据库、前端展示或新部署组件。
- 每个生产代码改动都有失败测试步骤。
- 所有命令使用项目指定 Python：`D:\Anaconda\envs\ContentShare\python.exe`。
- 计划明确不暂存用户既有 `AGENTS.md` 修改。
