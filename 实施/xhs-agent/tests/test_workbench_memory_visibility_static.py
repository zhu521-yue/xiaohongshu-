from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
STYLES_CSS = (ROOT / "app" / "static" / "styles.css").read_text(encoding="utf-8")


def test_memory_cards_render_creator_publish_and_performance_status():
    assert "memoryMetaGrid" in APP_JS
    assert 'creatorPublishStatusLabel(record.creator_publish_status)' in APP_JS
    assert 'performanceStatusLabel(record.status)' in APP_JS
    assert 'performanceDataSummary(record.performance_data)' in APP_JS
    assert "record.creator_note_id" in APP_JS
    assert "record.performance_score" in APP_JS
    assert 'if (status === "draft_saved") return "待录入";' in APP_JS


def test_memory_cards_can_fill_performance_form():
    assert "fillPerformanceFromMemoryRecord" in APP_JS
    assert 'data-post-id="${escapeHtml(record.post_id || "")}"' in APP_JS
    assert 'data-creator-note-id="${escapeHtml(record.creator_note_id || "")}"' in APP_JS
    assert "elements.performanceForm.elements.post_id.value = record.postId || \"\";" in APP_JS
    assert "elements.performanceForm.elements.creator_note_id.value = record.creatorNoteId || \"\";" in APP_JS
    assert "用这条记录录入表现" in APP_JS


def test_memory_visibility_has_compact_responsive_styles():
    assert ".memory-meta-grid" in STYLES_CSS
    assert ".memory-actions" in STYLES_CSS
    assert ".memory-action-button" in STYLES_CSS


def test_workbench_has_memory_recall_evidence_panel():
    assert 'id="memoryRecallEvidence"' in INDEX_HTML
    assert "renderMemoryRecallEvidence" in APP_JS
    assert 'apiGet(`/memory/graph?topic=${encodeURIComponent(topic)}&limit=5`)' in APP_JS
    assert "recommended_content_types" in APP_JS
    assert "related_pain_points" in APP_JS
    assert "recall_evidence" in APP_JS
    assert ".memory-recall-evidence" in STYLES_CSS
