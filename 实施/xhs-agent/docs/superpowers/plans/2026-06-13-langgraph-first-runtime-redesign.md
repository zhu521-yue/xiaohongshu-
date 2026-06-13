# LangGraph-first 全盘运行时整改实施计划

> **给 agentic workers：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务执行本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**目标：** 将项目主路径改造成 LangGraph-first 运行时，让审核、发布、creator 平台动作、复盘和写记忆都由同一个 LangGraph thread 控制。

**架构：** 新增 LangGraph runtime 边界和 SQLite snapshot checkpointer；API 只负责提交、审核输入和 run record 投影；worker 只启动图并在 interrupt 时释放队列任务。保留 `run_local_graph()` 作为显式兼容路径，但默认 API/worker 改走 LangGraph runtime。

**技术栈：** Python 3、LangGraph 1.2.1、SQLite、现有 stdlib HTTP API、pytest、现有 Spider_XHS/creator 适配器。

---

## 文件结构

- 新建 `app/langgraph_checkpoint.py`：提供 `SQLiteSnapshotSaver`，用 SQLite 持久化 LangGraph checkpointer 的内存结构快照。
- 新建 `app/langgraph_runtime.py`：提供 `LangGraphRunResult`、`run_graph_thread()`、`resume_graph_thread()`、`graph_thread_config()`。
- 修改 `app/graph.py`：`build_langgraph(checkpointer=None)`，新增图内 `reject_publish` 和 `creator_publish_or_skip` 节点。
- 修改 `app/state.py`：补齐 `run_id`、`run_status`、审核、creator、failure、节点事件字段。
- 修改 `nodes/human_review_node.py`：改为真正 `interrupt()` 节点，resume 后返回审核动作。
- 新建 `nodes/reject_node.py`：图内驳回节点。
- 新建 `nodes/creator_publish_node.py`：图内 creator 发布或跳过节点。
- 新建 `platforms/creator_publish_flow.py`：从 API 中抽出 creator 发布 payload、图片、错误脱敏和结果整理逻辑。
- 修改 `app/api.py`：默认执行 LangGraph runtime，approve/reject 通过 graph resume，不再手动调后续节点。
- 修改 `scripts/run_worker.py`：interrupt 后保存 waiting_review，并把 queue job 标记为 succeeded。
- 修改 `app/run_events.py` 或新增 runtime 事件 helper：记录 LangGraph 节点事件。
- 新增/修改测试：`tests/test_langgraph_runtime.py`、`tests/test_api_langgraph_resume.py`、`tests/test_run_worker.py`、`tests/test_graph_run_events.py`、`tests/test_api_creator_review_publish.py`。

## 任务 1：建立持久化 LangGraph runtime 边界

**文件：**
- 新建：`app/langgraph_checkpoint.py`
- 新建：`app/langgraph_runtime.py`
- 修改：`app/graph.py`
- 测试：`tests/test_langgraph_runtime.py`

- [ ] **步骤 1：写失败测试，证明 run_id 成为 thread_id 且 interrupt 可被识别**

在 `tests/test_langgraph_runtime.py` 新增：

```python
from __future__ import annotations

from pathlib import Path

from app.langgraph_runtime import run_graph_thread, resume_graph_thread


def test_run_graph_thread_interrupts_with_run_id_thread(tmp_path: Path, monkeypatch) -> None:
    from app import graph

    monkeypatch.setattr(graph, "load_user_input", lambda state: {"run_status": "running"})
    monkeypatch.setattr(graph, "check_account_stage", lambda state: {"account_stage": "cold_start"})
    monkeypatch.setattr(graph, "retrieve_graphrag_memory", lambda state: {"retrieved_memory": []})
    monkeypatch.setattr(graph, "analyze_topic_and_pain_points", lambda state: {"pain_points": []})
    monkeypatch.setattr(
        graph,
        "decide_content_strategy",
        lambda state: {"content_format": "image_text", "content_type": "step_tutorial"},
    )
    monkeypatch.setattr(graph, "generate_image_text", lambda state: {"titles": ["T"], "body": "B"})
    monkeypatch.setattr(graph, "check_compliance", lambda state: {"compliance_risk_level": "low"})

    result = run_graph_thread(
        {"user_topic": "topic", "target_user": "user", "user_selected_format": "image_text"},
        run_id="run_runtime_interrupt",
        checkpoint_db_path=tmp_path / "runtime.sqlite3",
    )

    assert result.interrupted is True
    assert result.run_status == "waiting_review"
    assert result.config["configurable"]["thread_id"] == "run_runtime_interrupt"
    assert result.interrupt_payload["run_id"] == "run_runtime_interrupt"
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_langgraph_runtime.py::test_run_graph_thread_interrupts_with_run_id_thread -q
```

预期：失败，原因是 `app.langgraph_runtime` 不存在。

- [ ] **步骤 3：实现 `SQLiteSnapshotSaver`**

在 `app/langgraph_checkpoint.py` 写入：

```python
from __future__ import annotations

import pickle
import sqlite3
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver


class SQLiteSnapshotSaver(InMemorySaver):
    """SQLite-backed snapshot wrapper for LangGraph checkpoint state."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._snapshot_lock = threading.RLock()
        super().__init__()
        self._init_db()
        self._load_snapshot()

    def put(self, config, checkpoint, metadata, new_versions):
        result = super().put(config, checkpoint, metadata, new_versions)
        self._persist_snapshot()
        return result

    def put_writes(self, config, writes, task_id: str, task_path: str = "") -> None:
        super().put_writes(config, writes, task_id, task_path)
        self._persist_snapshot()

    def delete_thread(self, thread_id: str) -> None:
        super().delete_thread(thread_id)
        self._persist_snapshot()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path, timeout=30) as connection:
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS langgraph_checkpoint_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    payload BLOB NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _load_snapshot(self) -> None:
        with self._snapshot_lock, sqlite3.connect(self.db_path, timeout=30) as connection:
            row = connection.execute(
                "SELECT payload FROM langgraph_checkpoint_snapshots WHERE snapshot_id = 'default'"
            ).fetchone()
        if row is None:
            return
        payload = pickle.loads(row[0])
        self.storage = defaultdict(lambda: defaultdict(dict))
        for thread_id, namespaces in payload.get("storage", {}).items():
            self.storage[thread_id] = defaultdict(dict, namespaces)
        self.writes = defaultdict(dict, payload.get("writes", {}))
        self.blobs = payload.get("blobs", {})

    def _persist_snapshot(self) -> None:
        payload: dict[str, Any] = {
            "storage": {thread_id: dict(namespaces) for thread_id, namespaces in self.storage.items()},
            "writes": dict(self.writes),
            "blobs": dict(self.blobs),
        }
        encoded = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        with self._snapshot_lock, sqlite3.connect(self.db_path, timeout=30) as connection:
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute(
                """
                INSERT INTO langgraph_checkpoint_snapshots (snapshot_id, payload, updated_at)
                VALUES ('default', ?, ?)
                ON CONFLICT(snapshot_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (encoded, now),
            )
```

- [ ] **步骤 4：实现 runtime 封装**

在 `app/langgraph_runtime.py` 写入：

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langgraph.types import Command

from app.config import load_settings
from app.graph import build_langgraph
from app.langgraph_checkpoint import SQLiteSnapshotSaver


@dataclass(frozen=True)
class LangGraphRunResult:
    state: dict[str, Any]
    interrupted: bool
    interrupt_payload: dict[str, Any]
    config: dict[str, Any]

    @property
    def run_status(self) -> str:
        return str(self.state.get("run_status") or ("waiting_review" if self.interrupted else "published"))


def graph_thread_config(run_id: str) -> dict[str, Any]:
    clean_run_id = str(run_id or "").strip()
    if not clean_run_id:
        raise ValueError("run_id is required for LangGraph thread execution")
    return {"configurable": {"thread_id": clean_run_id}}


def default_checkpoint_db_path() -> Path:
    return Path(load_settings().run_db_path)


def run_graph_thread(
    initial_state: dict[str, Any],
    *,
    run_id: str,
    checkpoint_db_path: str | Path | None = None,
) -> LangGraphRunResult:
    return _invoke_graph(
        dict(initial_state, run_id=run_id, run_status="running"),
        run_id=run_id,
        checkpoint_db_path=checkpoint_db_path,
    )


def resume_graph_thread(
    run_id: str,
    resume_value: dict[str, Any],
    *,
    checkpoint_db_path: str | Path | None = None,
) -> LangGraphRunResult:
    return _invoke_graph(
        Command(resume=resume_value),
        run_id=run_id,
        checkpoint_db_path=checkpoint_db_path,
    )


def _invoke_graph(
    payload: Any,
    *,
    run_id: str,
    checkpoint_db_path: str | Path | None,
) -> LangGraphRunResult:
    config = graph_thread_config(run_id)
    checkpointer = SQLiteSnapshotSaver(checkpoint_db_path or default_checkpoint_db_path())
    app = build_langgraph(checkpointer=checkpointer)
    result = app.invoke(payload, config)
    interrupted = "__interrupt__" in result
    interrupt_payload = _interrupt_payload(result, run_id=run_id) if interrupted else {}
    state = {key: value for key, value in dict(result).items() if key != "__interrupt__"}
    if interrupted:
        state["run_status"] = "waiting_review"
        state["review_required"] = True
        state["review_interrupt_payload"] = interrupt_payload
    elif state.get("publish_status") == "rejected":
        state["run_status"] = "rejected"
    elif state.get("publish_status") == "success":
        state["run_status"] = "published"
    else:
        state.setdefault("run_status", "published")
    return LangGraphRunResult(
        state=state,
        interrupted=interrupted,
        interrupt_payload=interrupt_payload,
        config=config,
    )


def _interrupt_payload(result: dict[str, Any], *, run_id: str) -> dict[str, Any]:
    interrupts = result.get("__interrupt__") or []
    first = interrupts[0] if interrupts else None
    value = getattr(first, "value", None)
    payload = value if isinstance(value, dict) else {"value": value}
    payload.setdefault("run_id", run_id)
    return payload
```

- [ ] **步骤 5：修改 `build_langgraph()` 接收 checkpointer**

在 `app/graph.py` 将签名和 compile 修改为：

```python
def build_langgraph(*, checkpointer=None):
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(XHSState)
    ...
    return graph.compile(checkpointer=checkpointer)
```

- [ ] **步骤 6：运行测试确认通过**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_langgraph_runtime.py::test_run_graph_thread_interrupts_with_run_id_thread -q
```

预期：通过。

- [ ] **步骤 7：提交**

运行：

```powershell
git add 实施/xhs-agent/app/langgraph_checkpoint.py 实施/xhs-agent/app/langgraph_runtime.py 实施/xhs-agent/app/graph.py 实施/xhs-agent/tests/test_langgraph_runtime.py
git commit -m "feat: add langgraph runtime boundary"
```

## 任务 2：把 human_review 改成真正 interrupt/resume

**文件：**
- 修改：`nodes/human_review_node.py`
- 修改：`app/state.py`
- 测试：`tests/test_langgraph_runtime.py`

- [ ] **步骤 1：写失败测试，证明 approve resume 后继续执行**

在 `tests/test_langgraph_runtime.py` 追加：

```python
def test_resume_graph_thread_uses_human_review_payload(tmp_path: Path, monkeypatch) -> None:
    from app import graph

    monkeypatch.setattr(graph, "load_user_input", lambda state: {"run_status": "running"})
    monkeypatch.setattr(graph, "check_account_stage", lambda state: {"account_stage": "cold_start"})
    monkeypatch.setattr(graph, "retrieve_graphrag_memory", lambda state: {"retrieved_memory": []})
    monkeypatch.setattr(graph, "analyze_topic_and_pain_points", lambda state: {"pain_points": []})
    monkeypatch.setattr(
        graph,
        "decide_content_strategy",
        lambda state: {"content_format": "image_text", "content_type": "step_tutorial"},
    )
    monkeypatch.setattr(graph, "generate_image_text", lambda state: {"titles": ["T"], "body": "B"})
    monkeypatch.setattr(graph, "check_compliance", lambda state: {"compliance_risk_level": "low"})
    monkeypatch.setattr(graph, "publish_or_schedule", lambda state: {"publish_status": "success", "post_id": "post.md"})
    monkeypatch.setattr(graph, "review_performance", lambda state: {"review_summary": "reviewed"})
    monkeypatch.setattr(graph, "write_operation_memory", lambda state: {"operation_memory_written": True})

    run_graph_thread(
        {"user_topic": "topic", "target_user": "user", "user_selected_format": "image_text"},
        run_id="run_runtime_resume",
        checkpoint_db_path=tmp_path / "runtime.sqlite3",
    )
    result = resume_graph_thread(
        "run_runtime_resume",
        {"action": "approved", "feedback": "approved by user"},
        checkpoint_db_path=tmp_path / "runtime.sqlite3",
    )

    assert result.interrupted is False
    assert result.state["human_approved"] is True
    assert result.state["human_feedback"] == "approved by user"
    assert result.state["publish_status"] == "success"
    assert result.state["operation_memory_written"] is True
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_langgraph_runtime.py::test_resume_graph_thread_uses_human_review_payload -q
```

预期：失败，原因是当前 `human_review` 不会 `interrupt()`。

- [ ] **步骤 3：修改 `XHSState` 增加运行时字段**

在 `app/state.py` 的 `XHSState` 中加入：

```python
    run_id: str
    run_status: Literal["queued", "running", "waiting_review", "rejected", "published", "failed", "cancelled", "timed_out"]
    review_action: Optional[Literal["approved", "rejected"]]
    review_required: bool
    review_interrupt_payload: Dict[str, Any]
    creator_publish_requested: bool
    creator_publish_private: bool
    creator_human_confirmed: bool
    creator_publish_status: Optional[str]
    creator_publish_mode: Optional[str]
    creator_note_id: Optional[str]
    creator_publish_error: Optional[str]
    creator_publish_result: Dict[str, Any]
    failure_category: Optional[str]
    failure_category_label: Optional[str]
    node_events: List[Dict[str, Any]]
```

- [ ] **步骤 4：实现 `human_review` interrupt/resume**

替换 `nodes/human_review_node.py` 的 `human_review()`：

```python
from langgraph.types import interrupt

from app.state import XHSState


def human_review(state: XHSState) -> dict:
    risk_level = state.get("compliance_risk_level", "low")
    if risk_level == "high":
        return {
            "review_action": "rejected",
            "human_approved": False,
            "human_feedback": "合规风险高，人工审核不通过。",
            "publish_status": "rejected",
            "run_status": "rejected",
        }

    if state.get("human_approved") is True:
        return {
            "review_action": "approved",
            "human_approved": True,
            "human_feedback": state.get("human_feedback") or "人工审核通过。",
            "publish_status": "pending",
        }

    resume_value = interrupt(_review_payload(state))
    if not isinstance(resume_value, dict):
        raise ValueError("human review resume payload must be a dict")

    action = str(resume_value.get("action") or "").strip().lower()
    feedback = str(resume_value.get("feedback") or "").strip()
    if action == "approved":
        return {
            "review_action": "approved",
            "human_approved": True,
            "human_feedback": feedback or "人工审核通过。",
            "publish_status": "pending",
            "creator_publish_requested": bool(resume_value.get("creator_publish")),
            "creator_publish_private": bool(resume_value.get("creator_publish_private")),
            "creator_human_confirmed": bool(resume_value.get("creator_human_confirmed")),
        }
    if action == "rejected":
        return {
            "review_action": "rejected",
            "human_approved": False,
            "human_feedback": feedback or "人工审核不通过。",
            "publish_status": "rejected",
        }
    raise ValueError("human review action must be approved or rejected")


def _review_payload(state: XHSState) -> dict:
    return {
        "run_id": state.get("run_id"),
        "user_topic": state.get("user_topic"),
        "content_format": state.get("content_format"),
        "titles": state.get("titles") or [],
        "body": state.get("body") or "",
        "video_script": state.get("video_script") or {},
        "tags": state.get("tags") or [],
        "compliance_risk_level": state.get("compliance_risk_level"),
        "compliance_issues": state.get("compliance_issues") or [],
    }
```

- [ ] **步骤 5：运行任务测试**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_langgraph_runtime.py -q
```

预期：任务 1 和任务 2 runtime 测试通过。

- [ ] **步骤 6：提交**

运行：

```powershell
git add 实施/xhs-agent/app/state.py 实施/xhs-agent/nodes/human_review_node.py 实施/xhs-agent/tests/test_langgraph_runtime.py
git commit -m "feat: make human review interrupt resumable"
```

## 任务 3：把驳回和 creator 发布迁入图内节点

**文件：**
- 新建：`nodes/reject_node.py`
- 新建：`nodes/creator_publish_node.py`
- 新建：`platforms/creator_publish_flow.py`
- 修改：`app/graph.py`
- 测试：`tests/test_langgraph_runtime.py`

- [ ] **步骤 1：写失败测试，证明 reject resume 进入图内驳回节点**

在 `tests/test_langgraph_runtime.py` 追加：

```python
def test_reject_resume_finishes_inside_graph(tmp_path: Path, monkeypatch) -> None:
    from app import graph

    monkeypatch.setattr(graph, "load_user_input", lambda state: {"run_status": "running"})
    monkeypatch.setattr(graph, "check_account_stage", lambda state: {"account_stage": "cold_start"})
    monkeypatch.setattr(graph, "retrieve_graphrag_memory", lambda state: {"retrieved_memory": []})
    monkeypatch.setattr(graph, "analyze_topic_and_pain_points", lambda state: {"pain_points": []})
    monkeypatch.setattr(
        graph,
        "decide_content_strategy",
        lambda state: {"content_format": "image_text", "content_type": "step_tutorial"},
    )
    monkeypatch.setattr(graph, "generate_image_text", lambda state: {"titles": ["T"], "body": "B"})
    monkeypatch.setattr(graph, "check_compliance", lambda state: {"compliance_risk_level": "low"})

    run_graph_thread(
        {"user_topic": "topic", "target_user": "user", "user_selected_format": "image_text"},
        run_id="run_runtime_reject",
        checkpoint_db_path=tmp_path / "runtime.sqlite3",
    )
    result = resume_graph_thread(
        "run_runtime_reject",
        {"action": "rejected", "feedback": "needs rewrite"},
        checkpoint_db_path=tmp_path / "runtime.sqlite3",
    )

    assert result.state["run_status"] == "rejected"
    assert result.state["publish_status"] == "rejected"
    assert result.state["operation_memory_written"] is False
    assert "needs rewrite" in result.state["human_feedback"]
```

- [ ] **步骤 2：写失败测试，证明 creator 发布节点在图内执行**

在 `tests/test_langgraph_runtime.py` 追加：

```python
def test_creator_publish_runs_inside_graph(tmp_path: Path, monkeypatch) -> None:
    from app import graph
    from platforms import creator as creator_platform

    calls = []
    monkeypatch.setattr(graph, "load_user_input", lambda state: {"run_status": "running"})
    monkeypatch.setattr(graph, "check_account_stage", lambda state: {"account_stage": "cold_start"})
    monkeypatch.setattr(graph, "retrieve_graphrag_memory", lambda state: {"retrieved_memory": []})
    monkeypatch.setattr(graph, "analyze_topic_and_pain_points", lambda state: {"pain_points": []})
    monkeypatch.setattr(
        graph,
        "decide_content_strategy",
        lambda state: {"content_format": "image_text", "content_type": "step_tutorial"},
    )
    monkeypatch.setattr(graph, "generate_image_text", lambda state: {"titles": ["T"], "body": "B", "tags": ["xhs"]})
    monkeypatch.setattr(graph, "check_compliance", lambda state: {"compliance_risk_level": "low"})
    monkeypatch.setattr(graph, "publish_or_schedule", lambda state: {"publish_status": "success", "post_id": "post.md"})
    monkeypatch.setattr(graph, "review_performance", lambda state: {"review_summary": "reviewed"})
    monkeypatch.setattr(graph, "write_operation_memory", lambda state: {"operation_memory_written": True})
    monkeypatch.setattr(
        creator_platform,
        "publish_private_image_text",
        lambda draft, human_confirmed: calls.append((draft, human_confirmed)) or {
            "ok": True,
            "mode": "mock",
            "platform": "xhs_creator",
            "visibility": "private",
            "note_id": "mock_private_note",
        },
    )

    run_graph_thread(
        {"user_topic": "topic", "target_user": "user", "user_selected_format": "image_text"},
        run_id="run_runtime_creator",
        checkpoint_db_path=tmp_path / "runtime.sqlite3",
    )
    result = resume_graph_thread(
        "run_runtime_creator",
        {
            "action": "approved",
            "feedback": "approved",
            "creator_publish": True,
            "creator_publish_private": True,
            "creator_human_confirmed": True,
        },
        checkpoint_db_path=tmp_path / "runtime.sqlite3",
    )

    assert len(calls) == 1
    assert result.state["creator_publish_status"] == "success"
    assert result.state["creator_note_id"] == "mock_private_note"
```

- [ ] **步骤 3：运行测试确认失败**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_langgraph_runtime.py::test_reject_resume_finishes_inside_graph tests/test_langgraph_runtime.py::test_creator_publish_runs_inside_graph -q
```

预期：失败，原因是图里没有 `reject_publish` 和 `creator_publish_or_skip`。

- [ ] **步骤 4：抽出 creator 发布流程**

在 `platforms/creator_publish_flow.py` 写入可从节点调用的函数，保留现有 API 行为：

```python
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from platforms import creator as creator_platform

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CREATOR_ASSETS_DIR = PROJECT_ROOT / "data" / "creator_assets"
MIN_CREATOR_IMAGE_BYTES = 8


def publish_creator_private_if_requested(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("creator_publish_requested") is not True:
        return creator_publish_not_requested()
    mode = creator_platform.creator_mode()
    if state.get("content_format") != "image_text":
        return creator_publish_failed("creator publishing is image_text only in M19b")
    try:
        draft = build_creator_image_text_draft(state, mode=mode)
        result = creator_platform.publish_private_image_text(draft, human_confirmed=True)
    except Exception as exc:
        return creator_publish_failed(str(exc))
    if result.get("ok") is True:
        return creator_publish_success(result)
    return creator_publish_failed(str(result.get("error") or "creator publish failed"))


def creator_publish_not_requested() -> dict[str, Any]:
    return {
        "creator_publish_requested": False,
        "creator_publish_status": "not_requested",
        "creator_publish_mode": creator_platform.creator_mode(),
        "creator_note_id": None,
        "creator_publish_error": None,
        "creator_publish_result": {},
    }


def creator_publish_failed(error: str, *, requested: bool = True) -> dict[str, Any]:
    mode = creator_platform.creator_mode()
    sanitized_error = sanitize_creator_error(error)
    return {
        "creator_publish_requested": requested,
        "creator_publish_status": "failed",
        "creator_publish_mode": mode,
        "creator_note_id": None,
        "creator_publish_error": sanitized_error,
        "creator_publish_result": {
            "ok": False,
            "mode": mode,
            "platform": "xhs_creator",
            "error": sanitized_error,
        },
    }


def creator_publish_success(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "creator_publish_requested": True,
        "creator_publish_status": "success",
        "creator_publish_mode": str(result.get("mode") or creator_platform.creator_mode()),
        "creator_note_id": result.get("note_id"),
        "creator_publish_error": None,
        "creator_publish_result": {
            "ok": result.get("ok") is True,
            "mode": result.get("mode"),
            "platform": result.get("platform"),
            "visibility": result.get("visibility"),
            "note_id": result.get("note_id"),
            "error": result.get("error"),
        },
    }


def build_creator_image_text_draft(state: dict[str, Any], *, mode: str) -> dict[str, Any]:
    fallback_title = state.get("user_topic") or "Untitled note"
    title = str((state.get("titles") or [fallback_title])[0]).strip()
    desc = creator_description_from_state(state)
    return {
        "title": title,
        "desc": desc or title,
        "images": creator_images_from_state(state, mode=mode),
        "topics": [str(tag).strip().lstrip("#") for tag in state.get("tags") or [] if str(tag).strip()],
    }


def creator_description_from_state(state: dict[str, Any]) -> str:
    parts = [str(state.get("body") or "").strip()]
    tags = [str(tag).strip().lstrip("#") for tag in state.get("tags") or [] if str(tag).strip()]
    if tags:
        parts.append(" ".join(f"#{tag}" for tag in tags))
    comment_call = str(state.get("comment_call") or "").strip()
    if comment_call:
        parts.append(comment_call)
    return "\n\n".join(part for part in parts if part).strip()


def creator_images_from_state(state: dict[str, Any], *, mode: str) -> list[Any]:
    images = state.get("creator_image_bytes") or state.get("creator_images") or []
    if isinstance(images, list) and images:
        if mode == "mock":
            return images
        return [_valid_image_bytes(image) for image in images]
    file_bytes = creator_image_file_bytes_from_state(state)
    if file_bytes:
        return file_bytes
    if mode == "mock":
        return [b"mock-image-bytes"]
    raise ValueError("creator publishing requires image bytes in state when CREATOR_MODE=spider_xhs")


def creator_image_file_bytes_from_state(state: dict[str, Any]) -> list[bytes]:
    files = state.get("creator_image_files") or []
    if not isinstance(files, list) or not files:
        return []
    return [_valid_image_file(path_value) for path_value in files]


def _valid_image_file(path_value: Any) -> bytes:
    path = resolve_creator_asset_path(path_value)
    if not path.exists() or not path.is_file():
        raise ValueError(f"creator asset file not found: {path}")
    return _valid_image_bytes(path.read_bytes())


def _valid_image_bytes(image: Any) -> bytes:
    if not isinstance(image, (bytes, bytearray, memoryview)):
        raise ValueError("creator publishing requires image bytes in state when CREATOR_MODE=spider_xhs")
    payload = bytes(image)
    if not is_supported_creator_image_bytes(payload):
        raise ValueError("creator publishing requires valid image bytes in state when CREATOR_MODE=spider_xhs")
    return payload


def resolve_creator_asset_path(path_value: Any) -> Path:
    raw_path = str(path_value or "").strip()
    if not raw_path:
        raise ValueError("creator asset path is empty")
    path = Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve()
    asset_root = CREATOR_ASSETS_DIR.resolve()
    if resolved != asset_root and asset_root not in resolved.parents:
        raise ValueError("creator asset path must stay inside creator asset directory")
    return resolved


def is_supported_creator_image_bytes(payload: bytes) -> bool:
    if len(payload) < MIN_CREATOR_IMAGE_BYTES:
        return False
    if payload.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"BM")):
        return True
    return payload.startswith(b"RIFF") and len(payload) >= 12 and payload[8:12] == b"WEBP"


def sanitize_creator_error(error: Any) -> str:
    text = str(error)
    replacements = [
        r"(?i)\bauthorization\s*[:=]\s*Bearer\s+[^\s,;]+",
        r"(?i)\b(cookie|token|password|api[_-]?key|apikey|authorization)\s*[:=]\s*[^\s,;]+",
        r"(?i)([\"'])(cookie|token|password|api[_-]?key|apikey|authorization)\1\s*:\s*([\"']).*?\3",
    ]
    for pattern in replacements:
        text = re.sub(pattern, _redacted_creator_error_match, text)
    return re.sub(r"(?i)(cookie=\[REDACTED\])(?:;\s*[^,\s;=]+=[^,\s;]+)+", r"\1", text)


def _redacted_creator_error_match(match: re.Match[str]) -> str:
    if match.lastindex and match.lastindex >= 2 and match.group(2):
        quote = match.group(1)
        return f"{quote}{match.group(2)}{quote}: {quote}[REDACTED]{quote}"
    key = match.group(1) if match.lastindex else "authorization"
    return f"{key}=[REDACTED]"
```

- [ ] **步骤 5：新增图内节点**

`nodes/reject_node.py`：

```python
from app.state import XHSState
from memory.operation_store import operation_memory_path


def reject_publish(state: XHSState) -> dict:
    topic = state.get("user_topic") or "未命名主题"
    feedback = state.get("human_feedback") or "人工审核不通过。"
    return {
        "run_status": "rejected",
        "publish_status": "rejected",
        "post_id": None,
        "operation_memory_written": False,
        "operation_memory_path": str(operation_memory_path()),
        "review_summary": f"主题「{topic}」已被人工审核驳回，草稿未保存。",
        "next_action": f"根据人工反馈修改后重新生成。反馈：{feedback}",
        "review_generation": {
            "enabled": False,
            "provider_mode": "manual_review",
            "model": None,
            "usage": {},
        },
    }
```

`nodes/creator_publish_node.py`：

```python
from app.state import XHSState
from platforms.creator_publish_flow import publish_creator_private_if_requested


def creator_publish_or_skip(state: XHSState) -> dict:
    return publish_creator_private_if_requested(dict(state))
```

- [ ] **步骤 6：接入图路由**

在 `app/graph.py`：

```python
from nodes.creator_publish_node import creator_publish_or_skip
from nodes.reject_node import reject_publish
```

加入节点和边：

```python
    graph.add_node("reject_publish", reject_publish)
    graph.add_node("creator_publish_or_skip", creator_publish_or_skip)
```

修改 `human_review` 条件边：

```python
    graph.add_conditional_edges(
        "human_review",
        route_human_review,
        {
            "publish_or_schedule": "publish_or_schedule",
            "reject_publish": "reject_publish",
        },
    )

    graph.add_edge("publish_or_schedule", "creator_publish_or_skip")
    graph.add_edge("creator_publish_or_skip", "review_performance")
    graph.add_edge("reject_publish", END)
```

同时把原来的 `graph.add_edge("publish_or_schedule", "review_performance")` 删除。

- [ ] **步骤 7：修改审核路由**

在 `routers/review_router.py`：

```python
from app.state import XHSState


def route_human_review(state: XHSState) -> str:
    if state.get("human_approved") is True:
        return "publish_or_schedule"
    return "reject_publish"
```

- [ ] **步骤 8：运行 runtime 测试**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_langgraph_runtime.py -q
```

预期：全部通过。

- [ ] **步骤 9：提交**

运行：

```powershell
git add 实施/xhs-agent/app/graph.py 实施/xhs-agent/routers/review_router.py 实施/xhs-agent/nodes/reject_node.py 实施/xhs-agent/nodes/creator_publish_node.py 实施/xhs-agent/platforms/creator_publish_flow.py 实施/xhs-agent/tests/test_langgraph_runtime.py
git commit -m "feat: move review outcomes into graph"
```

## 任务 4：API 默认执行 LangGraph runtime，并从 state 投影 run record

**文件：**
- 修改：`app/api.py`
- 测试：`tests/test_api_langgraph_resume.py`

- [ ] **步骤 1：写失败测试，证明 create_run 保存 waiting_review**

新建 `tests/test_api_langgraph_resume.py`：

```python
from __future__ import annotations

from pathlib import Path

import pytest

from app import api
from app.run_store import LocalRunStore
from memory import operation_store


@pytest.fixture()
def isolated_langgraph_api(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "json")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "json")
    monkeypatch.setenv("LLM_MODEL_NAME", "mock")
    monkeypatch.setenv("COLLECTOR_MODE", "mock")
    monkeypatch.setattr(api, "RUN_STORE", LocalRunStore(tmp_path / "runs", json_default=api._json_default))
    monkeypatch.setattr(api, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(api, "RUN_QUEUE_SERVICE", None)
    monkeypatch.setattr(api, "RUNTIME_CHECKPOINT_DB_PATH", tmp_path / "runtime.sqlite3", raising=False)
    monkeypatch.setattr(
        operation_store,
        "MEMORY_BACKEND",
        operation_store.JsonOperationMemoryBackend(tmp_path / "operation_history.json"),
    )
    monkeypatch.setattr(api.publish_node, "OUTPUT_DIR", tmp_path / "markdown_exports")
    yield tmp_path
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    operation_store.MEMORY_BACKEND = None


def test_create_run_langgraph_waits_for_review(isolated_langgraph_api) -> None:
    record = api.create_run(
        {
            "topic": "小红书新手选题方法",
            "target_user": "内容创作新手",
            "format": "image_text",
            "engine": "langgraph",
            "collect_limit": 1,
        }
    )

    assert record["status"] == "success"
    assert record["summary"]["run_status"] == "waiting_review"
    assert record["summary"]["publish_status"] == "pending"
    assert record["summary"]["human_approved"] is False
    assert record["state"]["review_required"] is True
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_langgraph_resume.py::test_create_run_langgraph_waits_for_review -q
```

预期：失败，原因是 API 没有调用新的 runtime。

- [ ] **步骤 3：修改 API 使用 runtime**

在 `app/api.py` 增加导入：

```python
from app.langgraph_runtime import run_graph_thread, resume_graph_thread
```

增加测试可 patch 的 checkpoint 路径：

```python
RUNTIME_CHECKPOINT_DB_PATH: Path | None = None
```

修改 `_initial_state_from_request()`：

```python
        "run_status": "queued",
```

修改 `_state_summary()` 增加：

```python
        "run_status": state.get("run_status"),
        "review_action": state.get("review_action"),
        "review_required": state.get("review_required"),
```

修改 `_run_workflow()` 的 langgraph 分支：

```python
    result = run_graph_thread(
        initial_state,
        run_id=run_id,
        checkpoint_db_path=RUNTIME_CHECKPOINT_DB_PATH,
    )
    return result.state
```

保留 `engine=local` 分支只服务显式 local。

- [ ] **步骤 4：运行测试确认通过**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_langgraph_resume.py::test_create_run_langgraph_waits_for_review -q
```

预期：通过。

- [ ] **步骤 5：提交**

运行：

```powershell
git add 实施/xhs-agent/app/api.py 实施/xhs-agent/tests/test_api_langgraph_resume.py
git commit -m "feat: run api workflows through langgraph runtime"
```

## 任务 5：approve/reject 通过 LangGraph resume，不再手动拼流程

**文件：**
- 修改：`app/api.py`
- 修改：`tests/test_api_langgraph_resume.py`
- 修改：`tests/test_api_creator_review_publish.py`

- [ ] **步骤 1：写失败测试，证明 approve 不直接调用旧节点函数**

在 `tests/test_api_langgraph_resume.py` 追加：

```python
def test_approve_run_resumes_graph_without_direct_node_calls(isolated_langgraph_api, monkeypatch) -> None:
    record = api.create_run(
        {
            "topic": "小红书新手选题方法",
            "target_user": "内容创作新手",
            "format": "image_text",
            "engine": "langgraph",
            "collect_limit": 1,
        }
    )

    monkeypatch.setattr(api.publish_node, "publish_or_schedule", lambda state: (_ for _ in ()).throw(AssertionError("direct publish call")))
    monkeypatch.setattr(api, "review_performance", lambda state: (_ for _ in ()).throw(AssertionError("direct review call")))
    monkeypatch.setattr(api, "write_operation_memory", lambda state: (_ for _ in ()).throw(AssertionError("direct memory call")))

    reviewed = api.approve_run(record["run_id"], {"feedback": "approved"})

    assert reviewed["summary"]["run_status"] == "published"
    assert reviewed["summary"]["publish_status"] == "success"
    assert reviewed["state"]["operation_memory_written"] is True
```

- [ ] **步骤 2：写失败测试，证明 reject 也通过图内节点**

在 `tests/test_api_langgraph_resume.py` 追加：

```python
def test_reject_run_resumes_graph_to_rejected_state(isolated_langgraph_api) -> None:
    record = api.create_run(
        {
            "topic": "小红书新手选题方法",
            "target_user": "内容创作新手",
            "format": "image_text",
            "engine": "langgraph",
            "collect_limit": 1,
        }
    )

    rejected = api.reject_run(record["run_id"], {"feedback": "needs rewrite"})

    assert rejected["summary"]["run_status"] == "rejected"
    assert rejected["summary"]["publish_status"] == "rejected"
    assert rejected["state"]["operation_memory_written"] is False
    assert rejected["review_action"] == "rejected"
```

- [ ] **步骤 3：运行测试确认失败**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_langgraph_resume.py::test_approve_run_resumes_graph_without_direct_node_calls tests/test_api_langgraph_resume.py::test_reject_run_resumes_graph_to_rejected_state -q
```

预期：失败，原因是 `approve_run()` 和 `reject_run()` 仍手动调用节点。

- [ ] **步骤 4：改造 approve/reject**

在 `app/api.py` 中将 `approve_run()` 的核心替换为：

```python
    if record.get("summary", {}).get("run_status") != "waiting_review":
        raise ValueError("Only waiting_review LangGraph runs can be approved")

    payload = payload or {}
    _validate_creator_publish_payload(payload)
    feedback = str(payload.get("feedback") or "人工审核通过。").strip()
    result = resume_graph_thread(
        run_id,
        {
            "action": "approved",
            "feedback": feedback,
            "creator_publish": _bool(payload.get("creator_publish"), default=False),
            "creator_publish_private": _bool(payload.get("creator_publish_private"), default=False),
            "creator_human_confirmed": _bool(payload.get("creator_human_confirmed"), default=False),
        },
        checkpoint_db_path=RUNTIME_CHECKPOINT_DB_PATH,
    )
    reviewed = _save_reviewed_run(record, result.state, review_action="approved")
    LOGGER.info("run_approved run_id=%s", run_id)
    return reviewed
```

将 `reject_run()` 的核心替换为：

```python
    if record.get("summary", {}).get("run_status") != "waiting_review":
        raise ValueError("Only waiting_review LangGraph runs can be rejected")

    payload = payload or {}
    feedback = str(payload.get("feedback") or "人工审核不通过。").strip()
    result = resume_graph_thread(
        run_id,
        {"action": "rejected", "feedback": feedback},
        checkpoint_db_path=RUNTIME_CHECKPOINT_DB_PATH,
    )
    reviewed = _save_reviewed_run(record, result.state, review_action="rejected")
    LOGGER.info("run_rejected run_id=%s", run_id)
    return reviewed
```

- [ ] **步骤 5：运行 API resume 测试**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_langgraph_resume.py -q
```

预期：通过。

- [ ] **步骤 6：运行 creator 审核发布测试并按新触发点修正断言**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_creator_review_publish.py -q
```

预期：若测试仍构造旧式 `status=success` 但没有 checkpoint，会失败。把这些测试改为通过 `api.create_run()` 生成 waiting_review 记录，再调用 `approve_run()`。保留原有断言：creator 未请求、请求成功、缺少确认参数、视频格式失败、错误脱敏。

- [ ] **步骤 7：提交**

运行：

```powershell
git add 实施/xhs-agent/app/api.py 实施/xhs-agent/tests/test_api_langgraph_resume.py 实施/xhs-agent/tests/test_api_creator_review_publish.py
git commit -m "feat: resume graph for human review actions"
```

## 任务 6：worker 遇到 interrupt 后保存 waiting_review 并释放队列

**文件：**
- 修改：`scripts/run_worker.py`
- 修改：`app/api.py`
- 测试：`tests/test_run_worker.py`

- [ ] **步骤 1：写失败测试，证明 waiting_review 不被 worker 当失败**

在 `tests/test_run_worker.py` 追加：

```python
def test_worker_marks_waiting_review_as_succeeded_queue_job(tmp_path: Path) -> None:
    from scripts import run_worker
    from app.run_queue import SQLiteRunQueue

    records = {"run_waiting": {"status": "waiting_review"}}
    succeeded = []
    failed = []
    queue = SQLiteRunQueue(tmp_path / "queue.sqlite3", list_runs=lambda limit: [])
    queue.enqueue("run_waiting")

    original_mark_succeeded = queue.mark_succeeded
    original_mark_failed = queue.mark_failed

    def mark_succeeded(run_id: str, worker_id: str) -> None:
        succeeded.append(run_id)
        original_mark_succeeded(run_id, worker_id)

    def mark_failed(run_id: str, worker_id: str, error: str) -> bool:
        failed.append((run_id, error))
        return original_mark_failed(run_id, worker_id, error)

    queue.mark_succeeded = mark_succeeded
    queue.mark_failed = mark_failed

    assert run_worker.run_once(
        queue,
        "worker-a",
        execute_run=lambda run_id: None,
        load_run=lambda run_id: records[run_id],
    ) is True
    assert succeeded == ["run_waiting"]
    assert failed == []
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_run_worker.py::test_worker_marks_waiting_review_as_succeeded_queue_job -q
```

预期：失败，原因是 worker 只认 `success`。

- [ ] **步骤 3：调整 `_finish_run()` 和 worker status 处理**

在 `app/api.py` 中确保 `_execute_run()` 对 `run_status=waiting_review` 仍保存兼容 `status="success"`：

```python
    final_state = dict(final_state)
    record_status = "success"
    _finish_run(running, status=record_status, state=final_state)
```

在 `scripts/run_worker.py` 中将成功判断改为：

```python
        if status == "success" or record.get("summary", {}).get("run_status") == "waiting_review":
            queue.mark_succeeded(run_id, worker_id)
            logger.info("worker_succeeded run_id=%s worker_id=%s", run_id, worker_id)
```

- [ ] **步骤 4：运行 worker 测试**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_run_worker.py -q
```

预期：通过。

- [ ] **步骤 5：提交**

运行：

```powershell
git add 实施/xhs-agent/app/api.py 实施/xhs-agent/scripts/run_worker.py 实施/xhs-agent/tests/test_run_worker.py
git commit -m "feat: release worker jobs at review interrupt"
```

## 任务 7：从 LangGraph 主路径记录节点级事件

**文件：**
- 修改：`app/langgraph_runtime.py`
- 修改：`app/api.py`
- 修改：`tests/test_graph_run_events.py`

- [ ] **步骤 1：写失败测试，证明 langgraph 路径有 node_finished 事件**

在 `tests/test_graph_run_events.py` 追加：

```python
def test_run_langgraph_records_node_events(tmp_path: Path, monkeypatch) -> None:
    from app import api, graph
    from app.run_store import SQLiteRunStore

    db_path = tmp_path / "xhs_agent.sqlite3"
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_DB_SCHEMA", "foundation")
    monkeypatch.setenv("XHS_AGENT_BUSINESS_TABLES_ENABLED", "true")
    monkeypatch.setattr(api, "RUN_STORE", SQLiteRunStore(db_path, json_default=api._json_default))
    monkeypatch.setattr(api, "RUNTIME_CHECKPOINT_DB_PATH", db_path, raising=False)
    monkeypatch.setattr(graph, "load_user_input", lambda state: {"run_status": "running"})
    monkeypatch.setattr(graph, "check_account_stage", lambda state: {"account_stage": "cold_start"})
    monkeypatch.setattr(graph, "retrieve_graphrag_memory", lambda state: {"retrieved_memory": []})
    monkeypatch.setattr(graph, "analyze_topic_and_pain_points", lambda state: {"pain_points": []})
    monkeypatch.setattr(
        graph,
        "decide_content_strategy",
        lambda state: {"content_format": "image_text", "content_type": "step_tutorial"},
    )
    monkeypatch.setattr(graph, "generate_image_text", lambda state: {"titles": ["T"], "body": "B"})
    monkeypatch.setattr(graph, "check_compliance", lambda state: {"compliance_risk_level": "low"})

    record = api.create_run({"topic": "topic", "format": "image_text", "engine": "langgraph"})

    events = _event_rows(db_path, record["run_id"])
    assert any(row["event_type"] == "node_finished" and row["node_name"] == "generate_image_text" for row in events)
    assert any(row["event_type"] == "node_interrupted" and row["node_name"] == "human_review" for row in events)
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_graph_run_events.py::test_run_langgraph_records_node_events -q
```

预期：失败，原因是 runtime 没记录 LangGraph stream 事件。

- [ ] **步骤 3：在 runtime 使用 stream 记录事件**

在 `app/langgraph_runtime.py` 增加可选 `event_db_path`，并将 `_invoke_graph()` 从 `app.invoke()` 改为：

```python
    final_chunk: dict[str, Any] = {}
    for chunk in app.stream(payload, config, stream_mode="updates"):
        final_chunk = _merge_stream_chunk(final_chunk, chunk)
        _record_stream_chunk(chunk, run_id=run_id, event_db_path=event_db_path)
    result = app.get_state(config).values
    if final_chunk.get("__interrupt__"):
        result = dict(result, __interrupt__=final_chunk["__interrupt__"])
```

新增 helper：

```python
def _merge_stream_chunk(current: dict[str, Any], chunk: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current)
    for node_name, updates in chunk.items():
        if node_name == "__interrupt__":
            merged["__interrupt__"] = updates
        elif isinstance(updates, dict):
            merged.update(updates)
    return merged


def _record_stream_chunk(chunk: dict[str, Any], *, run_id: str, event_db_path: str | Path | None) -> None:
    if event_db_path is None:
        return
    from app.run_events import record_run_event

    for node_name, updates in chunk.items():
        if node_name == "__interrupt__":
            record_run_event(event_db_path, run_id=run_id, event_type="node_interrupted", node_name="human_review", status="waiting")
        else:
            record_run_event(
                event_db_path,
                run_id=run_id,
                event_type="node_finished",
                node_name=str(node_name),
                status="success",
                payload={"updates": sorted(str(key) for key in (updates or {}).keys()) if isinstance(updates, dict) else []},
            )
```

在 `app/api.py` 调用 `run_graph_thread()` 和 `resume_graph_thread()` 时传入 SQLite store 的 db_path：

```python
event_db_path = _event_db_path_for_settings(load_settings())
```

- [ ] **步骤 4：运行事件测试**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_graph_run_events.py -q
```

预期：通过。

- [ ] **步骤 5：提交**

运行：

```powershell
git add 实施/xhs-agent/app/langgraph_runtime.py 实施/xhs-agent/app/api.py 实施/xhs-agent/tests/test_graph_run_events.py
git commit -m "feat: record langgraph node events"
```

## 任务 8：收敛默认主路径并保留 local 显式兼容

**文件：**
- 修改：`app/main.py`
- 修改：`app/api.py`
- 修改：`scripts/check_api_run.py`
- 修改：相关测试中默认 engine 断言

- [ ] **步骤 1：写失败测试，证明默认 engine 是 langgraph 且 local 仅显式使用**

在 `tests/test_api_run_control.py` 或新建 `tests/test_api_engine_defaults.py` 写入：

```python
from app import api


def test_build_run_request_defaults_to_langgraph() -> None:
    request = api._build_run_request({"topic": "topic"})
    assert request["engine"] == "langgraph"


def test_build_run_request_accepts_explicit_local() -> None:
    request = api._build_run_request({"topic": "topic", "engine": "local"})
    assert request["engine"] == "local"
```

- [ ] **步骤 2：运行测试确认现状**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_engine_defaults.py -q
```

预期：通过或因文件不存在失败；如果失败，按步骤 1 新增文件后应通过。

- [ ] **步骤 3：将 CLI 默认 engine 改为 langgraph**

在 `app/main.py` 修改：

```python
parser.add_argument("--engine", choices=("local", "langgraph"), default="langgraph", help="流程运行引擎")
```

保留 `--engine local`。

- [ ] **步骤 4：运行相关测试**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_engine_defaults.py tests/test_api_run_control.py -q
```

预期：通过。

- [ ] **步骤 5：提交**

运行：

```powershell
git add 实施/xhs-agent/app/main.py 实施/xhs-agent/app/api.py 实施/xhs-agent/tests/test_api_engine_defaults.py 实施/xhs-agent/tests/test_api_run_control.py
git commit -m "chore: make langgraph the default engine"
```

## 任务 9：全量回归、文档记忆更新和最终验证

**文件：**
- 修改：`memory/current_progress.md`
- 修改：`memory/project_status_and_roadmap.md`
- 可选修改：`AGENTS.md`

- [ ] **步骤 1：运行编译检查**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
```

预期：`0` 退出码，无 Python 语法错误。

- [ ] **步骤 2：运行全量测试**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

预期：全部通过。若存在真实外部平台依赖失败，记录测试名、失败原因和是否与本次整改相关。

- [ ] **步骤 3：运行 API smoke**

运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_api_run.py --engine langgraph --collect-limit 1 --timeout 180
```

预期：提交 run 后进入可审核状态，脚本按新的 `waiting_review` 语义通过；如果脚本仍期待发布完成，先更新脚本断言。

- [ ] **步骤 4：更新项目记忆**

在 `memory/current_progress.md` 和 `memory/project_status_and_roadmap.md` 记录：

```markdown
## LangGraph-first 全盘运行时整改

- 默认主路径已改为 LangGraph runtime。
- 人工审核通过和驳回均通过同一个 LangGraph thread resume。
- 发布、creator 发布、复盘、写记忆回到图内节点。
- worker 处理到 human interrupt 后保存 waiting_review 并释放队列任务。
- RunStore 和业务表保留为 LangGraph state 投影。
- local executor 仅保留为显式兼容路径。
```

- [ ] **步骤 5：提交最终整理**

运行：

```powershell
git add 实施/xhs-agent/memory/current_progress.md 实施/xhs-agent/memory/project_status_and_roadmap.md 实施/xhs-agent/scripts/check_api_run.py
git commit -m "docs: record langgraph-first runtime migration"
```

## 自检清单

- spec 覆盖：任务 1 覆盖 runtime/checkpointer；任务 2 覆盖 interrupt/resume；任务 3 覆盖 graph 内驳回和 creator；任务 4-5 覆盖 API 降级为入口；任务 6 覆盖 worker；任务 7 覆盖事件；任务 8 覆盖默认主路径；任务 9 覆盖验证和记忆。
- 占位扫描：本计划的步骤均包含文件、测试、命令和预期结果。
- 类型一致：`run_status`、`review_action`、`creator_publish_*` 字段在 state、summary、测试和 API 投影中使用同名字段。
