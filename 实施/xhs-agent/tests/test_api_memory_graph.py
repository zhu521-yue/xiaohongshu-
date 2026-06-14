from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from app import api


def _start_test_server(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(api, "RUNS_DIR", tmp_path / "runs")
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    server = ThreadingHTTPServer(("127.0.0.1", 0), api.XHSAgentAPIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        api.RUN_STORE = None
        api.RUN_QUEUE_SERVICE = None


def _read_json(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=10) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def test_state_summary_exposes_operation_memory_skip_detail() -> None:
    summary = api._state_summary(
        {
            "operation_memory_written": False,
            "operation_memory_skip_reason": "rag_eligibility_blocked",
            "operation_memory_skip_detail": {
                "level": "blocked",
                "score": 20,
                "blocking_reasons": ["评论样本较少"],
                "recommended_action": "重新采集更多候选和评论后再进入 RAG 入库。",
            },
        }
    )

    assert summary["operation_memory_written"] is False
    assert summary["operation_memory_skip_reason"] == "rag_eligibility_blocked"
    assert summary["operation_memory_skip_detail"]["blocking_reasons"] == ["评论样本较少"]


def test_compact_memory_record_exposes_rag_eligibility() -> None:
    compact = api._compact_memory_record(
        {
            "record_id": "op_1",
            "topic": "小红书选题",
            "title": "选题三步法",
            "rag_eligibility": {
                "eligible": True,
                "level": "eligible",
                "score": 90,
            },
        }
    )

    assert compact["rag_eligibility"] == {
        "eligible": True,
        "level": "eligible",
        "score": 90,
    }


def test_compact_memory_record_exposes_compliance_trace() -> None:
    compact = api._compact_memory_record(
        {
            "record_id": "op_1",
            "compliance_risk_level": "medium",
            "compliance_issues": ["内容中包含绝对词：一定"],
            "revised_content": "发布前提醒：内容仅作经验分享。",
            "compliance_summary": {
                "risk_level": "medium",
                "issue_count": 1,
                "issues": ["内容中包含绝对词：一定"],
                "has_revision": True,
            },
        }
    )

    assert compact["compliance_risk_level"] == "medium"
    assert compact["compliance_issues"] == ["内容中包含绝对词：一定"]
    assert compact["revised_content"] == "发布前提醒：内容仅作经验分享。"
    assert compact["compliance_summary"]["has_revision"] is True


def test_http_memory_graph_endpoint_returns_topic_graph(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")
    captured: dict = {}

    def fake_graph(*, topic: str, limit: int = 20) -> dict:
        captured["topic"] = topic
        captured["limit"] = limit
        return {
            "memory_graph": {
                "query": topic,
                "graph": {"record_count": 1, "nodes": [], "edges": []},
            }
        }

    monkeypatch.setattr(api, "get_memory_graph", fake_graph, raising=False)

    server_urls = _start_test_server(monkeypatch, tmp_path)
    base_url = next(server_urls)
    try:
        status, data = _read_json(
            f"{base_url}/memory/graph?topic={quote('小红书选题')}&limit=3",
            {"Authorization": "Bearer secret-token"},
        )
    finally:
        try:
            next(server_urls)
        except StopIteration:
            pass

    assert status == 200
    assert data["ok"] is True
    assert data["memory_graph"]["query"] == "小红书选题"
    assert captured == {"topic": "小红书选题", "limit": 3}
