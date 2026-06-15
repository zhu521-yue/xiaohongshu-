from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

from memory import operation_store
from scripts import check_api_run


def test_build_headers_empty_without_api_token() -> None:
    assert check_api_run.build_headers(None) == {}
    assert check_api_run.build_headers("") == {}


def test_build_headers_uses_bearer_token() -> None:
    assert check_api_run.build_headers("secret-token") == {
        "Authorization": "Bearer secret-token"
    }


def test_parser_accepts_api_token() -> None:
    args = check_api_run.build_parser().parse_args(["--api-token", "secret-token"])

    assert args.api_token == "secret-token"


def test_parser_accepts_memory_context_requirements() -> None:
    args = check_api_run.build_parser().parse_args(
        [
            "--require-memory-context",
            "--min-recall-explanations",
            "2",
            "--require-recall-explanation-type",
            "historical_compliance_risk",
            "--require-recall-explanation-type",
            "semantic_recall",
            "--seed-recall-memory",
        ]
    )

    assert args.require_memory_context is True
    assert args.min_recall_explanations == 2
    assert args.required_recall_explanation_types == ["historical_compliance_risk", "semantic_recall"]
    assert args.seed_recall_memory is True


def test_seed_recall_memory_writes_operation_record_for_mock_recall(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite3"))
    operation_store.MEMORY_BACKEND = None
    try:
        record = check_api_run.seed_recall_memory(
            topic="小红书新手选题方法",
            target_user="内容创作新手",
            content_format="image_text",
        )

        records = operation_store.find_relevant_records("小红书新手选题方法", limit=5)
        graph = check_api_run.build_seed_recall_probe_graph("小红书新手选题方法", records)
    finally:
        operation_store.MEMORY_BACKEND = None

    assert record["record_id"].startswith("op_")
    assert record["publish_status"] == "success"
    assert records[0]["record_id"] == record["record_id"]
    assert graph["recall_explanations"][0]["type"] == "similar_experience"
    assert "不知道「小红书新手选题方法」从哪里开始，需要清晰的入门步骤" in graph["recall_explanations"][0]["matched_terms"]


def test_seed_recall_memory_can_probe_historical_compliance_risk(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite3"))
    operation_store.MEMORY_BACKEND = None
    try:
        check_api_run.seed_recall_memory(
            topic="小红书新手选题方法一定有效",
            target_user="内容创作新手",
            content_format="image_text",
        )

        records = operation_store.find_relevant_records("小红书新手选题方法一定有效", limit=5)
        graph = check_api_run.build_seed_recall_probe_graph(
            "小红书新手选题方法一定有效",
            records,
            compliance_risk_level="medium",
            compliance_issues=["内容中包含绝对词：一定"],
        )
    finally:
        operation_store.MEMORY_BACKEND = None

    assert any(
        item["type"] == "historical_compliance_risk"
        for item in graph["recall_explanations"]
    )
    assert graph["historical_compliance_risks"][0]["record_id"] == records[0]["record_id"]


def test_cli_seed_recall_memory_can_import_project_modules(tmp_path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.update(
        {
            "XHS_AGENT_MEMORY_STORE": "sqlite",
            "XHS_AGENT_MEMORY_DB_PATH": str(tmp_path / "memory.sqlite3"),
            "COLLECTOR_MODE": "mock",
            "LLM_MODEL_NAME": "mock",
            "CREATOR_MODE": "mock",
        }
    )

    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "scripts" / "check_api_run.py"),
            "--base-url",
            "http://127.0.0.1:9",
            "--engine",
            "langgraph",
            "--seed-recall-memory",
            "--timeout",
            "0.1",
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    output = result.stdout + result.stderr
    assert "No module named" not in output
    assert "seed_recall_record_id:" in output
    assert "API request failed:" in output


def test_validate_final_run_requires_langgraph_memory_context_summary() -> None:
    assert check_api_run.validate_final_run(
        {
            "status": "success",
            "summary": {
                "run_status": "waiting_review",
                "memory_context_summary": {
                    "enabled": False,
                    "query": "",
                    "graph_record_count": 0,
                    "recommended_content_type_count": 0,
                    "recall_evidence_count": 0,
                    "semantic_recall_count": 0,
                    "semantic_embedding_model": "",
                    "semantic_embedding_dimensions": 0,
                    "semantic_recall_top_score": 0.0,
                    "semantic_recall_threshold": 0.08,
                    "similar_experience_count": 0,
                    "historical_compliance_risk_count": 0,
                    "recall_explanation_count": 0,
                    "recall_explanations": [],
                },
            },
        },
        engine="langgraph",
    ) == []

    assert check_api_run.validate_final_run(
        {"status": "success", "summary": {"run_status": "waiting_review"}},
        engine="langgraph",
    ) == ["missing memory_context_summary in LangGraph run summary"]


def test_validate_final_run_rejects_malformed_langgraph_memory_context_summary() -> None:
    issues = check_api_run.validate_final_run(
        {
            "status": "success",
            "summary": {
                "run_status": "waiting_review",
                "memory_context_summary": {
                    "enabled": "false",
                    "graph_record_count": "0",
                    "semantic_recall_count": "1",
                    "semantic_embedding_model": 123,
                    "semantic_embedding_dimensions": "64",
                    "semantic_recall_top_score": "0.2",
                    "semantic_recall_threshold": None,
                    "recall_explanation_count": 1,
                    "recall_explanations": [{}, {}],
                },
            },
        },
        engine="langgraph",
    )

    assert "memory_context_summary.enabled must be boolean" in issues
    assert "memory_context_summary.query must be a string" in issues
    assert "memory_context_summary.graph_record_count must be a non-negative integer" in issues
    assert "memory_context_summary.recommended_content_type_count must be a non-negative integer" in issues
    assert "memory_context_summary.semantic_recall_count must be a non-negative integer" in issues
    assert "memory_context_summary.semantic_embedding_model must be a string" in issues
    assert "memory_context_summary.semantic_embedding_dimensions must be a non-negative integer" in issues
    assert "memory_context_summary.semantic_recall_top_score must be a non-negative number" in issues
    assert "memory_context_summary.semantic_recall_threshold must be a non-negative number" in issues
    assert "memory_context_summary.recall_explanations has more samples than recall_explanation_count" in issues


def test_validate_final_run_can_require_enabled_memory_context() -> None:
    final = {
        "status": "success",
        "summary": {
            "run_status": "waiting_review",
            "memory_context_summary": {
                "enabled": False,
                "query": "",
                "graph_record_count": 0,
                "recommended_content_type_count": 0,
                "recall_evidence_count": 0,
                "semantic_recall_count": 0,
                "semantic_embedding_model": "",
                "semantic_embedding_dimensions": 0,
                "semantic_recall_top_score": 0.0,
                "semantic_recall_threshold": 0.08,
                "similar_experience_count": 0,
                "historical_compliance_risk_count": 0,
                "recall_explanation_count": 0,
                "recall_explanations": [],
            },
        },
    }

    assert check_api_run.validate_final_run(
        final,
        engine="langgraph",
        require_memory_context=True,
    ) == ["memory_context_summary.enabled is false; expected recalled memory context"]


def test_validate_final_run_can_require_recall_explanation_minimum() -> None:
    final = {
        "status": "success",
        "summary": {
            "run_status": "waiting_review",
            "memory_context_summary": {
                "enabled": True,
                "query": "小红书选题",
                "graph_record_count": 3,
                "recommended_content_type_count": 1,
                "recall_evidence_count": 1,
                "semantic_recall_count": 0,
                "semantic_embedding_model": "",
                "semantic_embedding_dimensions": 0,
                "semantic_recall_top_score": 0.0,
                "semantic_recall_threshold": 0.08,
                "similar_experience_count": 1,
                "historical_compliance_risk_count": 0,
                "recall_explanation_count": 1,
                "recall_explanations": [{"type": "similar_experience"}],
            },
        },
    }

    assert check_api_run.validate_final_run(
        final,
        engine="langgraph",
        min_recall_explanations=2,
    ) == ["memory_context_summary.recall_explanation_count is 1, below required minimum 2"]


def test_validate_final_run_can_require_recall_explanation_type() -> None:
    final = {
        "status": "success",
        "summary": {
            "run_status": "waiting_review",
            "memory_context_summary": {
                "enabled": True,
                "query": "小红书选题",
                "graph_record_count": 3,
                "recommended_content_type_count": 1,
                "recall_evidence_count": 1,
                "semantic_recall_count": 0,
                "semantic_embedding_model": "",
                "semantic_embedding_dimensions": 0,
                "semantic_recall_top_score": 0.0,
                "semantic_recall_threshold": 0.08,
                "similar_experience_count": 1,
                "historical_compliance_risk_count": 0,
                "recall_explanation_count": 1,
                "recall_explanations": [{"type": "similar_experience"}],
            },
        },
    }

    assert check_api_run.validate_final_run(
        final,
        engine="langgraph",
        required_recall_explanation_types=["historical_compliance_risk"],
    ) == [
        "memory_context_summary.recall_explanations missing required type: "
        "historical_compliance_risk"
    ]


def test_validate_final_run_requires_semantic_recall_explanation_embedding_metadata() -> None:
    final = {
        "status": "success",
        "summary": {
            "run_status": "waiting_review",
            "memory_context_summary": {
                "enabled": True,
                "query": "小红书选题",
                "graph_record_count": 3,
                "recommended_content_type_count": 1,
                "recall_evidence_count": 1,
                "semantic_recall_count": 1,
                "semantic_embedding_model": "local_hashing_embedding_v1",
                "semantic_embedding_dimensions": 64,
                "semantic_recall_top_score": 0.0,
                "semantic_recall_threshold": 0.08,
                "similar_experience_count": 0,
                "historical_compliance_risk_count": 0,
                "recall_explanation_count": 1,
                "recall_explanations": [{"type": "semantic_recall"}],
            },
        },
    }

    assert check_api_run.validate_final_run(final, engine="langgraph") == [
        "memory_context_summary.semantic_recall_top_score must be positive when semantic recall exists",
        "memory_context_summary.recall_explanations[0].embedding_model is required for semantic_recall",
        "memory_context_summary.recall_explanations[0].embedding_dimensions must be positive for semantic_recall",
        "memory_context_summary.recall_explanations[0].semantic_score must be a non-negative number for semantic_recall",
    ]


def test_validate_final_run_can_require_recall_explanation_type_from_full_state() -> None:
    final = {
        "status": "success",
        "summary": {
            "run_status": "waiting_review",
            "memory_context_summary": {
                "enabled": True,
                "query": "小红书选题",
                "graph_record_count": 3,
                "recommended_content_type_count": 1,
                "recall_evidence_count": 1,
                "semantic_recall_count": 1,
                "semantic_embedding_model": "local_hashing_embedding_v1",
                "semantic_embedding_dimensions": 64,
                "semantic_recall_top_score": 0.42,
                "semantic_recall_threshold": 0.08,
                "similar_experience_count": 1,
                "historical_compliance_risk_count": 1,
                "recall_explanation_count": 3,
                "recall_explanations": [
                    {"type": "similar_experience"},
                    {"type": "historical_compliance_risk"},
                ],
            },
        },
        "state": {
            "graphrag_memory": {
                "recall_explanations": [
                    {"type": "similar_experience"},
                    {"type": "historical_compliance_risk"},
                    {"type": "semantic_recall"},
                ]
            }
        },
    }

    assert check_api_run.validate_final_run(
        final,
        engine="langgraph",
        required_recall_explanation_types=["semantic_recall"],
    ) == []


def test_print_json_handles_gbk_stdout_with_emoji(monkeypatch) -> None:
    raw = io.BytesIO()
    stdout = io.TextIOWrapper(raw, encoding="gbk", errors="strict")
    monkeypatch.setattr(sys, "stdout", stdout)

    check_api_run._print_json({"title": "真实结果⭐"})

    stdout.flush()
    output = raw.getvalue().decode("gbk")
    assert "真实结果" in output
    assert "\\u2b50" in output
