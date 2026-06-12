from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
STYLES_CSS = (ROOT / "app" / "static" / "styles.css").read_text(encoding="utf-8")
CHECK_WORKBENCH_UI = (ROOT / "scripts" / "check_workbench_ui.py").read_text(encoding="utf-8")


def test_side_stack_has_platform_status_panel():
    assert 'id="platformStatus"' in INDEX_HTML
    assert "platform-status" in INDEX_HTML


def test_workbench_fetches_and_renders_platform_status():
    assert 'apiGet("/platform/status")' in APP_JS
    assert "function renderPlatformStatus(platformStatus)" in APP_JS
    assert "platform.platform_status" in APP_JS
    assert "collector_runtime" in APP_JS
    assert "creator_runtime" in APP_JS
    assert "creator_publish_guardrail" in APP_JS


def test_platform_status_has_styles():
    assert ".platform-status" in STYLES_CSS
    assert ".platform-status-item" in STYLES_CSS


def test_workbench_smoke_script_checks_platform_status_panel():
    assert "#platformStatus" in CHECK_WORKBENCH_UI
    assert "平台状态" in CHECK_WORKBENCH_UI
    assert 'get_by_role("heading", name="平台状态")' in CHECK_WORKBENCH_UI
