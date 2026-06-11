from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")


def test_review_area_has_creator_asset_controls():
    assert 'id="creatorAssetInput"' in INDEX_HTML
    assert 'accept="image/*"' in INDEX_HTML
    assert "multiple" in INDEX_HTML
    assert 'id="attachCreatorAssetsButton"' in INDEX_HTML
    assert "绑定发布图片" in INDEX_HTML


def test_creator_asset_upload_uses_run_asset_endpoint():
    assert "fileToCreatorAssetPayload" in APP_JS
    assert "attachCreatorAssets" in APP_JS
    assert "content_base64" in APP_JS
    assert "filename: file.name" in APP_JS
    assert 'apiPost(`/runs/${encodeURIComponent(state.currentRunId)}/creator-assets`' in APP_JS


def test_summary_renders_creator_asset_count():
    assert 'metric("发布图片", summary.creator_images_count)' in APP_JS
    assert "elements.creatorAssetInput.disabled = !canBindAssets;" in APP_JS
    assert "elements.attachCreatorAssetsButton.disabled = !canBindAssets;" in APP_JS
