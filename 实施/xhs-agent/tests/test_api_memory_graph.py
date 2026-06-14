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


def test_state_summary_exposes_langgraph_memory_context_summary() -> None:
    summary = api._state_summary(
        {
            "graphrag_memory": {
                "query": "小红书选题",
                "graph": {"record_count": 3},
                "recommended_content_types": [
                    {"content_type": "step_tutorial", "count": 2, "max_score": 90}
                ],
                "recall_evidence": [{"record_id": "op_1"}, {"record_id": "op_2"}],
                "semantic_recall_records": [{"record_id": "op_semantic", "reason": "semantic_recall"}],
                "similar_experience_records": [{"record_id": "op_sim", "reason": "痛点相似"}],
                "historical_compliance_risks": [
                    {"record_id": "op_risk", "risk_level": "medium", "reason": "风险相似"}
                ],
                "recall_explanations": [
                    {
                        "type": "similar_experience",
                        "record_id": "op_sim",
                        "matched_terms": ["第一步"],
                        "matched_fields": ["pain_points"],
                        "reason": "当前痛点与历史记录相似。",
                    },
                    {
                        "type": "historical_compliance_risk",
                        "record_id": "op_risk",
                        "matched_terms": ["一定"],
                        "matched_fields": ["compliance_summary"],
                        "reason": "当前合规问题与历史风险相似。",
                    },
                    {
                        "type": "similar_experience",
                        "record_id": "op_extra",
                        "matched_terms": ["多余"],
                        "matched_fields": ["review_summary"],
                        "reason": "第三条不进入摘要样本。",
                    },
                ],
            }
        }
    )

    assert summary["memory_context_summary"] == {
        "enabled": True,
        "query": "小红书选题",
        "graph_record_count": 3,
        "recommended_content_type_count": 1,
        "recall_evidence_count": 2,
        "semantic_recall_count": 1,
        "similar_experience_count": 1,
        "historical_compliance_risk_count": 1,
        "recall_explanation_count": 3,
        "recall_explanations": [
            {
                "type": "similar_experience",
                "record_id": "op_sim",
                "matched_terms": ["第一步"],
                "matched_fields": ["pain_points"],
                "reason": "当前痛点与历史记录相似。",
            },
            {
                "type": "historical_compliance_risk",
                "record_id": "op_risk",
                "matched_terms": ["一定"],
                "matched_fields": ["compliance_summary"],
                "reason": "当前合规问题与历史风险相似。",
            },
        ],
    }


def test_memory_context_summary_counts_raw_memory_items_but_limits_samples() -> None:
    summary = api._state_summary(
        {
            "graphrag_memory": {
                "query": "小红书选题",
                "graph": {"record_count": 8},
                "recommended_content_types": [
                    {"content_type": "step_tutorial"},
                    {"content_type": "avoid_mistakes"},
                    {"content_type": "checklist"},
                    {"content_type": "case_review"},
                ],
                "recall_evidence": [
                    {"record_id": "op_1"},
                    {"record_id": "op_2"},
                    {"record_id": "op_3"},
                    {"record_id": "op_4"},
                ],
                "semantic_recall_records": [
                    {"record_id": "op_sem_1", "reason": "semantic_recall"},
                    {"record_id": "op_sem_2", "reason": "semantic_recall"},
                    {"record_id": "op_sem_3", "reason": "semantic_recall"},
                    {"record_id": "op_sem_4", "reason": "semantic_recall"},
                ],
                "similar_experience_records": [
                    {"record_id": "op_sim_1", "reason": "痛点相似"},
                    {"record_id": "op_sim_2", "reason": "评论洞察相似"},
                    {"record_id": "op_sim_3", "reason": "复盘摘要相似"},
                    {"record_id": "op_sim_4", "reason": "下一步建议相似"},
                ],
                "historical_compliance_risks": [
                    {"record_id": "op_risk_1", "risk_level": "medium"},
                    {"record_id": "op_risk_2", "risk_level": "high"},
                    {"record_id": "op_risk_3", "risk_level": "medium"},
                    {"record_id": "op_risk_4", "risk_level": "high"},
                ],
                "recall_explanations": [
                    {"type": "similar_experience", "record_id": "op_sim_1", "reason": "第一条"},
                    {"type": "similar_experience", "record_id": "op_sim_2", "reason": "第二条"},
                    {"type": "historical_compliance_risk", "record_id": "op_risk_1", "reason": "第三条"},
                    {"type": "historical_compliance_risk", "record_id": "op_risk_2", "reason": "第四条"},
                ],
            }
        }
    )

    memory_summary = summary["memory_context_summary"]
    assert memory_summary["recommended_content_type_count"] == 4
    assert memory_summary["recall_evidence_count"] == 4
    assert memory_summary["semantic_recall_count"] == 4
    assert memory_summary["similar_experience_count"] == 4
    assert memory_summary["historical_compliance_risk_count"] == 4
    assert memory_summary["recall_explanation_count"] == 4
    assert len(memory_summary["recall_explanations"]) == 2


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
