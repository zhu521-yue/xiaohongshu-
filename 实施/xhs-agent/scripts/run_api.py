"""Run the minimal HTTP API server."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.api import run_server  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the XHS agent HTTP API.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", type=int, default=8010, help="Port to bind.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logger = configure_logging("api")
    logger.info("api_starting host=%s port=%s", args.host, args.port)
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
