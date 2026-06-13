import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
STYLES_CSS = (ROOT / "app" / "static" / "styles.css").read_text(encoding="utf-8")


def test_result_panel_has_event_timeline_container():
    assert 'id="runTimeline"' in INDEX_HTML
    assert "run-timeline" in INDEX_HTML


def test_app_fetches_and_renders_business_timeline():
    assert "async function loadBusinessRunSnapshot(runId)" in APP_JS
    assert "/business/runs/${encodeURIComponent(runId)}" in APP_JS
    assert "function renderRunTimeline(businessRun)" in APP_JS
    assert "事件时间线" in APP_JS
    assert "queue_claimed" in APP_JS
    assert "queue_heartbeat" in APP_JS
    assert "node_finished" in APP_JS
    assert "renderRunTimeline(data.business_run || null);" in APP_JS


def test_queue_diagnostics_render_jobs_and_controls():
    assert "function renderQueueJob(job)" in APP_JS
    assert "queue.jobs || []" in APP_JS
    assert "data-cancel-run" in APP_JS
    assert "data-timeout-run" in APP_JS
    assert 'apiPost(`/runs/${encodeURIComponent(runId)}/cancel`, payload)' in APP_JS
    assert 'apiPost(`/runs/${encodeURIComponent(runId)}/timeout`, payload)' in APP_JS


def test_event_timeline_has_responsive_styles():
    assert ".run-timeline" in STYLES_CSS
    assert ".timeline-list" in STYLES_CSS
    assert ".timeline-item" in STYLES_CSS
    assert ".queue-job" in STYLES_CSS


def test_compact_time_formats_zoned_event_time_as_local_seconds():
    start = APP_JS.index("function compactTime(value)")
    end = APP_JS.index("function renderRunList", start)
    script = (
        APP_JS[start:end]
        + "\nprocess.stdout.write(compactTime('2026-06-12T15:19:48.230212+00:00'));"
    )
    env = {**os.environ, "TZ": "Asia/Shanghai"}

    result = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.stdout == "2026-06-12 23:19:48"


def test_timeline_events_are_sorted_after_mixed_timezone_api_order():
    start = APP_JS.index("function timelineEventTimeBucket(event)")
    end = APP_JS.index("function renderTimelineItem", start)
    script = (
        APP_JS[start:end]
        + """
const events = [
  { event_type: "queue_enqueued", created_at: "2026-06-12T15:19:48.230212+00:00" },
  { event_type: "queue_claimed", created_at: "2026-06-12T15:19:48.866333+00:00" },
  { event_type: "queue_heartbeat", created_at: "2026-06-12T15:19:48.900333+00:00" },
  { event_type: "queue_succeeded", created_at: "2026-06-12T15:19:49.046011+00:00" },
  { event_type: "queued", created_at: "2026-06-12T23:19:48" },
  { event_type: "running", created_at: "2026-06-12T23:19:48" },
  { event_type: "success", created_at: "2026-06-12T23:19:48" },
];
process.stdout.write(JSON.stringify(sortedTimelineEvents(events).map((event) => event.event_type)));
"""
    )
    env = {**os.environ, "TZ": "Asia/Shanghai"}

    result = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.stdout == (
        '["queued","queue_enqueued","queue_claimed","queue_heartbeat","running","success","queue_succeeded"]'
    )
