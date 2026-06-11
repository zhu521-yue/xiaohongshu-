from __future__ import annotations

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
