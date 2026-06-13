from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")


def test_performance_panel_has_creator_note_controls():
    assert 'name="creator_note_id"' in INDEX_HTML
    assert 'id="syncCreatorNotesButton"' in INDEX_HTML
    assert "同步作品列表" in INDEX_HTML
    assert 'id="creatorNotesList"' in INDEX_HTML


def test_workbench_fetches_and_renders_creator_notes():
    assert 'apiGet("/creator/notes?limit=20")' in APP_JS
    assert "renderCreatorNotes" in APP_JS
    assert "creatorNotesList" in APP_JS
    assert "creator_note_id" in APP_JS


def test_performance_payload_includes_creator_note_id():
    assert "creator_note_id: form.get(\"creator_note_id\")" in APP_JS
    assert "elements.performanceForm.elements.creator_note_id.value" in APP_JS


def test_creator_notes_render_status_summary():
    assert "renderCreatorNoteStatus(note)" in APP_JS
    assert "note.visibility_label" in APP_JS
    assert "metricsSnapshot.views" in APP_JS
    assert "平台状态" in APP_JS


def test_creator_notes_can_refresh_single_note_status_with_wait():
    assert "refreshCreatorNoteStatus" in APP_JS
    assert "/creator/notes/status" in APP_JS
    assert "wait=true" in APP_JS
    assert "data-note-status-id" in APP_JS
    assert "刷新状态" in APP_JS
