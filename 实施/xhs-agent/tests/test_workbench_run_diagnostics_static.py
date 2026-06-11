from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
STYLES_CSS = (ROOT / "app" / "static" / "styles.css").read_text(encoding="utf-8")


def test_result_panel_has_run_diagnostics_container():
    assert 'id="runDiagnostics"' in INDEX_HTML
    assert "run-diagnostics" in INDEX_HTML


def test_app_renders_run_diagnostics_and_failure_category():
    assert "function renderRunDiagnostics(run)" in APP_JS
    assert "function diagnoseRunFailure(run)" in APP_JS
    assert "run?.failure_category_label" in APP_JS
    assert "run?.summary?.failure_category_label" in APP_JS
    assert "运行诊断" in APP_JS
    assert "错误详情" in APP_JS
    assert "创作者平台或发布素材问题" in APP_JS
    assert "LLM 生成或解析问题" in APP_JS
    assert "采集或 Cookie 问题" in APP_JS
    assert "合规拦截" in APP_JS
    assert "未分类失败，请查看错误详情" in APP_JS
    assert "renderRunDiagnostics(run);" in APP_JS


def test_resubmit_uses_current_run_request_payload():
    assert "function resubmitRunFromCurrent()" in APP_JS
    assert "const request = state.currentRun?.request || {};" in APP_JS
    assert "topic: request.topic" in APP_JS
    assert "target_user: request.target_user" in APP_JS
    assert "format: request.format" in APP_JS
    assert "engine: request.engine" in APP_JS
    assert "collect_limit: Number(request.collect_limit || 5)" in APP_JS
    assert "approve: Boolean(request.approve)" in APP_JS
    assert 'apiPost("/runs", payload)' in APP_JS
    assert "startRunPolling(data.run.run_id);" in APP_JS


def test_run_diagnostics_has_responsive_styles():
    assert ".run-diagnostics" in STYLES_CSS
    assert ".diagnostics-grid" in STYLES_CSS
    assert ".diagnostic-alert" in STYLES_CSS
    assert ".diagnostic-actions" in STYLES_CSS
