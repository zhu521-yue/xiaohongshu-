from __future__ import annotations

from pathlib import Path

import pytest

from conftest import _should_relax_windows_pytest_tmp_mode
from app import api
from app.graph import build_langgraph
from app.langgraph_checkpoint import SQLiteSnapshotSaver
from app.langgraph_runtime import graph_thread_config
from app.run_store import LocalRunStore
from memory import operation_store
from nodes import publish_node


def _reset_services() -> None:
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    operation_store.MEMORY_BACKEND = None


@pytest.fixture()
def isolated_api(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "json")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "json")
    monkeypatch.setenv("CREATOR_MODE", "mock")
    monkeypatch.setenv("COLLECTOR_MODE", "mock")
    monkeypatch.setenv("LLM_MODEL_NAME", "mock")
    monkeypatch.setattr(api, "RUN_STORE", LocalRunStore(tmp_path / "runs", json_default=api._json_default))
    monkeypatch.setattr(api, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(api, "RUNTIME_CHECKPOINT_DB_PATH", tmp_path / "runtime.sqlite3", raising=False)
    monkeypatch.setattr(api, "RUN_QUEUE_SERVICE", None)
    monkeypatch.setattr(
        operation_store,
        "MEMORY_BACKEND",
        operation_store.JsonOperationMemoryBackend(tmp_path / "operation_history.json"),
    )
    monkeypatch.setattr(publish_node, "OUTPUT_DIR", tmp_path / "markdown_exports")
    yield tmp_path
    _reset_services()


def _generated_record(run_id: str = "run_creator_001", *, content_format: str = "image_text") -> dict:
    return api.create_run(
        {
            "topic": f"XHS topic method {run_id}",
            "target_user": "new creators",
            "format": content_format,
            "engine": "langgraph",
            "collect_limit": 1,
        }
    )


def _save_generated(record: dict) -> None:
    api._save_run(record)
    if api.RUNTIME_CHECKPOINT_DB_PATH is not None:
        graph = build_langgraph(checkpointer=SQLiteSnapshotSaver(api.RUNTIME_CHECKPOINT_DB_PATH))
        graph.update_state(graph_thread_config(record["run_id"]), record.get("state") or {})


def test_approve_without_creator_publish_does_not_call_creator_adapter(isolated_api, monkeypatch) -> None:
    calls = []

    def fail_if_called(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("creator adapter should not be called")

    monkeypatch.setattr(api.creator_platform, "publish_private_image_text", fail_if_called)
    record = _generated_record()
    _save_generated(record)

    reviewed = api.approve_run(record["run_id"], {"feedback": "approved"})

    assert calls == []
    assert reviewed["summary"]["publish_status"] == "success"
    assert reviewed["summary"]["creator_publish_requested"] is False
    assert reviewed["summary"]["creator_publish_status"] == "not_requested"
    assert reviewed["state"]["operation_memory_written"] is True

    history = operation_store.load_history()
    saved = history["records"][-1]
    assert saved["creator_publish_requested"] is False
    assert saved["creator_publish_status"] == "not_requested"


def test_approve_with_creator_publish_records_mock_creator_note(isolated_api) -> None:
    record = _generated_record()
    _save_generated(record)

    reviewed = api.approve_run(
        record["run_id"],
        {
            "feedback": "approved",
            "creator_publish": True,
            "creator_publish_private": True,
            "creator_human_confirmed": True,
        },
    )

    assert reviewed["summary"]["publish_status"] == "success"
    assert reviewed["summary"]["creator_publish_requested"] is True
    assert reviewed["summary"]["creator_publish_status"] == "success"
    assert reviewed["summary"]["creator_publish_mode"] == "mock"
    assert reviewed["summary"]["creator_note_id"].startswith("mock_private_")
    assert reviewed["state"]["creator_publish_result"]["visibility"] == "private"
    assert reviewed["state"]["operation_memory_written"] is True

    history = operation_store.load_history()
    saved = history["records"][-1]
    assert saved["creator_publish_requested"] is True
    assert saved["creator_publish_status"] == "success"
    assert saved["creator_note_id"].startswith("mock_private_")
    assert saved["post_id"] == reviewed["summary"]["post_id"]


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        ({"feedback": "approved", "creator_publish": True, "creator_publish_private": True}, "creator_human_confirmed"),
        ({"feedback": "approved", "creator_publish": True, "creator_human_confirmed": True}, "creator_publish_private"),
    ],
)
def test_creator_publish_requires_explicit_flags(isolated_api, monkeypatch, payload: dict, field_name: str) -> None:
    calls = []
    monkeypatch.setattr(
        api.creator_platform,
        "publish_private_image_text",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    record = _generated_record(f"run_missing_{field_name}")
    _save_generated(record)

    with pytest.raises(ValueError, match=field_name):
        api.approve_run(record["run_id"], payload)

    assert calls == []


def test_video_creator_publish_request_records_failed_without_calling_adapter(isolated_api, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        api.creator_platform,
        "publish_private_image_text",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    record = _generated_record("run_creator_video", content_format="video")
    _save_generated(record)

    reviewed = api.approve_run(
        record["run_id"],
        {
            "feedback": "approved",
            "creator_publish": True,
            "creator_publish_private": True,
            "creator_human_confirmed": True,
        },
    )

    assert calls == []
    assert reviewed["summary"]["publish_status"] == "success"
    assert reviewed["summary"]["creator_publish_requested"] is True
    assert reviewed["summary"]["creator_publish_status"] == "failed"
    assert "image_text" in reviewed["summary"]["creator_publish_error"]
    assert reviewed["state"]["operation_memory_written"] is True


def test_creator_adapter_exception_records_failure_after_local_save(isolated_api, monkeypatch) -> None:
    def raise_adapter_error(*args, **kwargs):
        raise RuntimeError("creator adapter unavailable")

    monkeypatch.setattr(api.creator_platform, "publish_private_image_text", raise_adapter_error)
    record = _generated_record()
    _save_generated(record)

    reviewed = api.approve_run(
        record["run_id"],
        {
            "feedback": "approved",
            "creator_publish": True,
            "creator_publish_private": True,
            "creator_human_confirmed": True,
        },
    )

    assert reviewed["summary"]["publish_status"] == "success"
    assert reviewed["summary"]["post_id"]
    assert reviewed["summary"]["creator_publish_status"] == "failed"
    assert "creator adapter unavailable" in reviewed["summary"]["creator_publish_error"]
    assert reviewed["state"]["operation_memory_written"] is True

    history = operation_store.load_history()
    saved = history["records"][-1]
    assert saved["creator_publish_status"] == "failed"
    assert "creator adapter unavailable" in saved["creator_publish_error"]


def test_real_creator_mode_without_image_bytes_records_failed_without_calling_adapter(isolated_api, monkeypatch) -> None:
    calls = []
    monkeypatch.setenv("CREATOR_MODE", "spider_xhs")
    monkeypatch.setattr(
        api.creator_platform,
        "publish_private_image_text",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    record = _generated_record("run_creator_real_no_images")
    _save_generated(record)

    reviewed = api.approve_run(
        record["run_id"],
        {
            "feedback": "approved",
            "creator_publish": True,
            "creator_publish_private": True,
            "creator_human_confirmed": True,
        },
    )

    assert calls == []
    assert reviewed["summary"]["publish_status"] == "success"
    assert reviewed["summary"]["creator_publish_requested"] is True
    assert reviewed["summary"]["creator_publish_status"] == "failed"
    assert "image bytes" in reviewed["summary"]["creator_publish_error"]


def test_real_creator_mode_rejects_non_byte_image_placeholders_before_adapter(isolated_api, monkeypatch) -> None:
    calls = []
    monkeypatch.setenv("CREATOR_MODE", "spider_xhs")
    monkeypatch.setattr(
        api.creator_platform,
        "publish_private_image_text",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    record = _generated_record("run_creator_real_placeholder_images")
    record["state"]["creator_images"] = ["not-bytes"]
    _save_generated(record)

    reviewed = api.approve_run(
        record["run_id"],
        {
            "feedback": "approved",
            "creator_publish": True,
            "creator_publish_private": True,
            "creator_human_confirmed": True,
        },
    )

    assert calls == []
    assert reviewed["summary"]["publish_status"] == "success"
    assert reviewed["summary"]["creator_publish_status"] == "failed"
    assert "image bytes" in reviewed["summary"]["creator_publish_error"]


def test_real_creator_mode_rejects_fake_byte_image_payloads_before_adapter(isolated_api, monkeypatch) -> None:
    calls = []
    monkeypatch.setenv("CREATOR_MODE", "spider_xhs")
    monkeypatch.setattr(
        api.creator_platform,
        "publish_private_image_text",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    record = _generated_record("run_creator_real_fake_bytes")
    record["state"]["creator_image_bytes"] = [b"fake-image-bytes"]
    _save_generated(record)

    reviewed = api.approve_run(
        record["run_id"],
        {
            "feedback": "approved",
            "creator_publish": True,
            "creator_publish_private": True,
            "creator_human_confirmed": True,
        },
    )

    assert calls == []
    assert reviewed["summary"]["publish_status"] == "success"
    assert reviewed["summary"]["creator_publish_status"] == "failed"
    assert "image bytes" in reviewed["summary"]["creator_publish_error"]


def test_creator_adapter_error_is_redacted_in_summary_and_operation_memory(isolated_api, monkeypatch) -> None:
    def raise_adapter_error(*args, **kwargs):
        raise RuntimeError("cookie=a1=secret; token=abc123 authorization=Bearer xyz")

    monkeypatch.setattr(api.creator_platform, "publish_private_image_text", raise_adapter_error)
    record = _generated_record("run_creator_redacted_error")
    _save_generated(record)

    reviewed = api.approve_run(
        record["run_id"],
        {
            "feedback": "approved",
            "creator_publish": True,
            "creator_publish_private": True,
            "creator_human_confirmed": True,
        },
    )

    summary_error = reviewed["summary"]["creator_publish_error"]
    result_error = reviewed["state"]["creator_publish_result"]["error"]
    assert "[REDACTED]" in summary_error
    assert "[REDACTED]" in result_error
    for secret in ("secret", "abc123", "Bearer xyz"):
        assert secret not in summary_error
        assert secret not in result_error

    history = operation_store.load_history()
    saved = history["records"][-1]
    memory_text = repr(saved)
    assert "[REDACTED]" in memory_text
    for secret in ("secret", "abc123", "Bearer xyz"):
        assert secret not in memory_text


def test_creator_adapter_error_redacts_quoted_headers_and_cookie_segments(isolated_api, monkeypatch) -> None:
    def raise_adapter_error(*args, **kwargs):
        raise RuntimeError(
            '{"authorization": "Bearer xyz", "api_key": "sk-live"} '
            "{'password': 'pw123'} cookie=a=secret; session=leak"
        )

    monkeypatch.setattr(api.creator_platform, "publish_private_image_text", raise_adapter_error)
    record = _generated_record("run_creator_redacted_structured_error")
    _save_generated(record)

    reviewed = api.approve_run(
        record["run_id"],
        {
            "feedback": "approved",
            "creator_publish": True,
            "creator_publish_private": True,
            "creator_human_confirmed": True,
        },
    )

    persisted_text = repr(
        {
            "summary": reviewed["summary"],
            "result": reviewed["state"]["creator_publish_result"],
            "memory": operation_store.load_history()["records"][-1],
        }
    )
    assert "[REDACTED]" in persisted_text
    for secret in ("Bearer xyz", "sk-live", "pw123", "a=secret", "session=leak"):
        assert secret not in persisted_text


def test_windows_pytest_tmp_mode_relaxation_is_limited_to_safe_temp_root() -> None:
    safe_root = Path("data") / "pytest_tmp_safe"
    assert _should_relax_windows_pytest_tmp_mode(safe_root / "case", 0o700) is True
    assert _should_relax_windows_pytest_tmp_mode(safe_root, 0o700) is True
    assert _should_relax_windows_pytest_tmp_mode(Path("data") / "other_tmp" / "case", 0o700) is False
    assert _should_relax_windows_pytest_tmp_mode(Path("unrelated"), 0o700) is False
    assert _should_relax_windows_pytest_tmp_mode(safe_root / "case", 0o755) is False
