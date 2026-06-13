"""Check real creator-note performance closure without platform writes."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import api  # noqa: E402
from memory import operation_store  # noqa: E402
from platforms import creator as creator_platform  # noqa: E402


_ENV_KEYS = (
    "XHS_AGENT_RUN_STORE",
    "XHS_AGENT_RUN_DB_PATH",
    "XHS_AGENT_RUN_QUEUE",
    "XHS_AGENT_MEMORY_STORE",
    "XHS_AGENT_MEMORY_DB_PATH",
    "XHS_AGENT_DB_SCHEMA",
    "XHS_AGENT_BUSINESS_TABLES_ENABLED",
    "COLLECTOR_MODE",
    "LLM_MODEL_NAME",
    "CREATOR_MODE",
)

_METRIC_KEYS = ("views", "likes", "collects", "comments", "follows")


def _reset_services() -> None:
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    operation_store.MEMORY_BACKEND = None


@contextmanager
def _sqlite_closure_environment(db_path: Path) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in _ENV_KEYS}
    os.environ.update(
        {
            "XHS_AGENT_RUN_STORE": "sqlite",
            "XHS_AGENT_RUN_DB_PATH": str(db_path),
            "XHS_AGENT_RUN_QUEUE": "local",
            "XHS_AGENT_MEMORY_STORE": "sqlite",
            "XHS_AGENT_MEMORY_DB_PATH": str(db_path),
            "XHS_AGENT_DB_SCHEMA": "foundation",
            "XHS_AGENT_BUSINESS_TABLES_ENABLED": "true",
            "COLLECTOR_MODE": "mock",
            "LLM_MODEL_NAME": "mock",
            "CREATOR_MODE": "spider_xhs",
        }
    )
    _reset_services()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _reset_services()


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _load_run_record(run_id: str, runs_dir: Path) -> dict[str, Any]:
    path = runs_dir / f"{run_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Run file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Run file is not a JSON object: {path}")
    return data


def _note_identifier(note: dict[str, Any]) -> str:
    return str(note.get("note_id") or note.get("creator_note_id") or note.get("id") or "").strip()


def _find_platform_note(list_result: dict[str, Any], creator_note_id: str) -> dict[str, Any] | None:
    notes = list_result.get("notes")
    if not isinstance(notes, list):
        data = list_result.get("data")
        notes = data.get("notes") if isinstance(data, dict) else []
    for note in notes or []:
        if isinstance(note, dict) and _note_identifier(note) == creator_note_id:
            return note
    return None


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _platform_metrics(note: dict[str, Any] | None) -> dict[str, int]:
    if not isinstance(note, dict):
        return {}
    candidates = [
        note.get("metrics"),
        note.get("metrics_snapshot"),
        note.get("statistics"),
        note,
    ]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        metrics = {key: _int(candidate.get(key)) for key in _METRIC_KEYS if candidate.get(key) is not None}
        if metrics:
            return metrics
    return {}


def _performance_payload(
    *,
    creator_note_id: str,
    metrics: dict[str, Any] | None,
    platform_note: dict[str, Any] | None,
    use_platform_metrics: bool,
) -> dict[str, Any]:
    payload = {"creator_note_id": creator_note_id, "notes": "real performance closure check"}
    selected_metrics = {key: _int((metrics or {}).get(key)) for key in _METRIC_KEYS}
    if use_platform_metrics:
        for key, value in _platform_metrics(platform_note).items():
            if selected_metrics.get(key, 0) == 0:
                selected_metrics[key] = value
    payload.update(selected_metrics)
    return payload


def _prepare_run_record(run_record: dict[str, Any], memory_record: dict[str, Any]) -> dict[str, Any]:
    state = run_record.get("state") if isinstance(run_record.get("state"), dict) else {}
    state = dict(state)
    state["operation_record_id"] = memory_record.get("record_id") or state.get("operation_record_id")
    merged = dict(run_record)
    merged["state"] = state
    merged["summary"] = api._state_summary(state)
    merged["content"] = api._content_payload(state)
    merged["insights"] = api._insight_payload(state)
    merged["paths"] = {
        **(run_record.get("paths") if isinstance(run_record.get("paths"), dict) else {}),
        "post_id": state.get("post_id"),
        "operation_memory_path": state.get("operation_memory_path"),
        "collection_path": state.get("collection_path"),
    }
    return merged


def _performance_record(snapshot: dict[str, Any]) -> dict[str, Any]:
    records = snapshot.get("performance_records") if isinstance(snapshot, dict) else []
    if isinstance(records, list) and records:
        return records[-1]
    return {}


def run_real_performance_closure_check(
    *,
    run_id: str,
    creator_note_id: str,
    db_path: str | Path,
    runs_dir: str | Path | None = None,
    limit: int = 20,
    use_platform_metrics: bool = False,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_db_path = Path(db_path)
    resolved_db_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_runs_dir = Path(runs_dir) if runs_dir is not None else ROOT / "data" / "api_runs"

    with _sqlite_closure_environment(resolved_db_path):
        list_result = creator_platform.list_published_notes(limit=max(1, int(limit or 20)))
        platform_note = _find_platform_note(list_result, creator_note_id)
        run_record = _load_run_record(run_id, resolved_runs_dir)
        state = run_record.get("state") if isinstance(run_record.get("state"), dict) else {}
        memory_record = operation_store.upsert_record_from_state(state)
        prepared = _prepare_run_record(run_record, memory_record)
        api._save_run(prepared)

        payload = _performance_payload(
            creator_note_id=creator_note_id,
            metrics=metrics,
            platform_note=platform_note,
            use_platform_metrics=use_platform_metrics,
        )
        performance_result = api.record_performance(payload)
        business_run = api.get_business_run_snapshot(run_id)["business_run"]
        performance_record = _performance_record(business_run)
        loaded_run = api._load_run(run_id) or {}
        loaded_state = loaded_run.get("state") if isinstance(loaded_run.get("state"), dict) else {}
        updated_record = performance_result.get("updated_record") or {}
        business_sync = performance_result.get("business_sync") or {}
        business_counts = business_run.get("counts") or {}

        checks = {
            "platform_note_found": platform_note is not None,
            "memory_updated": updated_record.get("status") == "performance_recorded",
            "business_sync_success": business_sync.get("status") == "success",
            "run_state_synced": loaded_state.get("performance_data") == updated_record.get("performance_data"),
            "performance_record_written": int(business_counts.get("performance_records") or 0) >= 1,
            "creator_note_id_match": performance_record.get("creator_note_id") == creator_note_id,
        }
        return {
            "ok": all(checks.values()),
            "run_id": run_id,
            "creator_note_id": creator_note_id,
            "db_path": str(resolved_db_path),
            "platform_note": {
                "found": platform_note is not None,
                "source": list_result.get("source"),
                "note": platform_note or {},
            },
            "performance_result": performance_result,
            "business_sync": business_sync,
            "business_counts": business_counts,
            "performance_record": performance_record,
            "checks": checks,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check real creator-note performance closure without platform writes.")
    parser.add_argument("--run-id", required=True, help="Existing run id to import from data/api_runs.")
    parser.add_argument("--creator-note-id", required=True, help="Creator note id to match in the read-only list.")
    parser.add_argument("--db-path", default=None, help="Temporary SQLite DB path.")
    parser.add_argument("--runs-dir", default=None, help="Run JSON directory. Defaults to data/api_runs.")
    parser.add_argument("--limit", type=int, default=20, help="Read-only creator note list limit.")
    parser.add_argument("--use-platform-metrics", action="store_true", help="Use metrics from creator list when present.")
    parser.add_argument("--views", type=int, default=0)
    parser.add_argument("--likes", type=int, default=0)
    parser.add_argument("--collects", type=int, default=0)
    parser.add_argument("--comments", type=int, default=0)
    parser.add_argument("--follows", type=int, default=0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db_path = Path(args.db_path) if args.db_path else ROOT / "data" / f"real_performance_closure_{uuid.uuid4().hex[:8]}.sqlite3"
    result = run_real_performance_closure_check(
        run_id=args.run_id,
        creator_note_id=args.creator_note_id,
        db_path=db_path,
        runs_dir=Path(args.runs_dir) if args.runs_dir else None,
        limit=args.limit,
        use_platform_metrics=args.use_platform_metrics,
        metrics={
            "views": args.views,
            "likes": args.likes,
            "collects": args.collects,
            "comments": args.comments,
            "follows": args.follows,
        },
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
