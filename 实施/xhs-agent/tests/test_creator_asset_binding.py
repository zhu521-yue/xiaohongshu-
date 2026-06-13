from __future__ import annotations

import base64
from pathlib import Path

import pytest

from app import api
from app.run_store import LocalRunStore
from memory import operation_store
from platforms import creator_publish_flow


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _reset_services() -> None:
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    operation_store.MEMORY_BACKEND = None


@pytest.fixture()
def isolated_api(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "json")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "json")
    monkeypatch.setenv("LLM_MODEL_NAME", "mock")
    monkeypatch.setenv("COLLECTOR_MODE", "mock")
    monkeypatch.setenv("CREATOR_MODE", "mock")
    monkeypatch.setattr(api, "RUN_STORE", LocalRunStore(tmp_path / "runs", json_default=api._json_default))
    monkeypatch.setattr(api, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(api, "CREATOR_ASSETS_DIR", tmp_path / "creator_assets", raising=False)
    monkeypatch.setattr(creator_publish_flow, "CREATOR_ASSETS_DIR", tmp_path / "creator_assets", raising=False)
    monkeypatch.setattr(api, "RUNTIME_CHECKPOINT_DB_PATH", tmp_path / "runtime.sqlite3", raising=False)
    monkeypatch.setattr(
        operation_store,
        "MEMORY_BACKEND",
        operation_store.JsonOperationMemoryBackend(tmp_path / "operation_history.json"),
    )
    monkeypatch.setattr(api.publish_node, "OUTPUT_DIR", tmp_path / "markdown_exports")
    yield tmp_path
    _reset_services()


def _generated_record(run_id: str = "run_asset_001") -> dict:
    return api.create_run(
        {
            "topic": f"XHS topic method {run_id}",
            "target_user": "new creators",
            "format": "image_text",
            "engine": "langgraph",
            "collect_limit": 1,
        }
    )


def _asset_payload(filename: str = "cover.png", data: bytes = PNG_BYTES) -> dict:
    return {
        "images": [
            {
                "filename": filename,
                "content_base64": base64.b64encode(data).decode("ascii"),
            }
        ]
    }


def _resolve_asset_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else api.PROJECT_ROOT / path


def test_attach_creator_assets_writes_files_and_updates_run(isolated_api) -> None:
    record = _generated_record()
    api._save_run(record)

    updated = api.attach_creator_assets(record["run_id"], _asset_payload())

    assert updated["summary"]["creator_images_count"] == 1
    assert updated["state"]["creator_images_count"] == 1
    asset_files = updated["state"]["creator_image_files"]
    assert len(asset_files) == 1
    asset_path = _resolve_asset_path(asset_files[0])
    assert asset_path.exists()
    assert asset_path.read_bytes() == PNG_BYTES


def test_creator_publish_loads_bound_asset_bytes_in_real_mode(isolated_api, monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "spider_xhs")
    record = _generated_record("run_asset_publish")
    api._save_run(record)
    api.attach_creator_assets(record["run_id"], _asset_payload())
    captured: dict = {}

    def fake_publish_private_image_text(draft: dict, *, human_confirmed: bool) -> dict:
        captured["draft"] = draft
        captured["human_confirmed"] = human_confirmed
        return {
            "ok": True,
            "mode": "spider_xhs",
            "platform": "xhs_creator",
            "visibility": "private",
            "note_id": "real_note_001",
        }

    monkeypatch.setattr(api.creator_platform, "publish_private_image_text", fake_publish_private_image_text)

    reviewed = api.approve_run(
        record["run_id"],
        {
            "feedback": "approved",
            "creator_publish": True,
            "creator_publish_private": True,
            "creator_human_confirmed": True,
        },
    )

    assert captured["human_confirmed"] is True
    assert captured["draft"]["images"] == [PNG_BYTES]
    assert reviewed["summary"]["creator_publish_status"] == "success"
    assert reviewed["summary"]["creator_note_id"] == "real_note_001"


def test_attach_creator_assets_rejects_invalid_image_bytes(isolated_api) -> None:
    record = _generated_record("run_asset_invalid")
    api._save_run(record)

    with pytest.raises(ValueError, match="valid image"):
        api.attach_creator_assets(record["run_id"], _asset_payload(filename="bad.txt", data=b"not an image"))
