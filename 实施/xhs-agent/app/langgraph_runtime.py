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
        state.setdefault("human_approved", False)
        state.setdefault("publish_status", "pending")
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
