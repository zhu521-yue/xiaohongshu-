from __future__ import annotations

import io
import sys

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


def test_validate_final_run_requires_langgraph_memory_context_summary() -> None:
    assert check_api_run.validate_final_run(
        {
            "status": "success",
            "summary": {
                "run_status": "waiting_review",
                "memory_context_summary": {"enabled": False},
            },
        },
        engine="langgraph",
    ) == []

    assert check_api_run.validate_final_run(
        {"status": "success", "summary": {"run_status": "waiting_review"}},
        engine="langgraph",
    ) == ["missing memory_context_summary in LangGraph run summary"]


def test_print_json_handles_gbk_stdout_with_emoji(monkeypatch) -> None:
    raw = io.BytesIO()
    stdout = io.TextIOWrapper(raw, encoding="gbk", errors="strict")
    monkeypatch.setattr(sys, "stdout", stdout)

    check_api_run._print_json({"title": "真实结果⭐"})

    stdout.flush()
    output = raw.getvalue().decode("gbk")
    assert "真实结果" in output
    assert "\\u2b50" in output
