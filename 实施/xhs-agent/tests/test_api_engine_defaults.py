from app import api
from app.main import build_parser


def test_build_run_request_defaults_to_langgraph() -> None:
    request = api._build_run_request({"topic": "topic"})
    assert request["engine"] == "langgraph"


def test_build_run_request_accepts_explicit_local() -> None:
    request = api._build_run_request({"topic": "topic", "engine": "local"})
    assert request["engine"] == "local"


def test_cli_defaults_to_langgraph() -> None:
    args = build_parser().parse_args(["--topic", "topic"])
    assert args.engine == "langgraph"
