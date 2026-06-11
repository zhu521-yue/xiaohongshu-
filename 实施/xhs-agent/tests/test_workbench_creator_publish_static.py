from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")


def test_review_area_has_creator_publish_checkbox():
    assert 'id="creatorPublishCheckbox"' in INDEX_HTML
    assert 'name="creator_publish"' in INDEX_HTML
    assert "review-publish-option" in INDEX_HTML
    assert "同时私密发布到创作者平台" in INDEX_HTML


def test_approve_payload_adds_creator_flags_only_when_checked():
    assert "const reviewPayload = {" in APP_JS
    assert "elements.creatorPublishCheckbox.checked" in APP_JS
    assert "reviewPayload.creator_publish = true;" in APP_JS
    assert "reviewPayload.creator_publish_private = true;" in APP_JS
    assert "reviewPayload.creator_human_confirmed = true;" in APP_JS
    assert "isApprove && elements.creatorPublishCheckbox.checked" in APP_JS


def test_summary_and_notice_render_creator_publish_result():
    assert "creatorPublishStatusLabel" in APP_JS
    assert 'metric("创作发布", creatorPublishStatusLabel(summary.creator_publish_status))' in APP_JS
    assert 'metric("平台笔记", summary.creator_note_id)' in APP_JS
    assert "creator_publish_error" in APP_JS
    assert "creatorPublishError(summary)" in APP_JS
