"""Generate an OpenAI image asset from a run and optionally bind it to the API run."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from platforms import openai_image  # noqa: E402


def build_headers(api_token: str | None) -> dict[str, str]:
    token = str(api_token or "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def build_creator_asset_payload(*, image_bytes: bytes, filename: str) -> dict[str, Any]:
    return {
        "images": [
            {
                "filename": filename,
                "content_base64": base64.b64encode(image_bytes).decode("ascii"),
            }
        ]
    }


def write_prompt(path: Path, prompt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(prompt, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and bind a creator image asset for a run.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010", help="API base URL.")
    parser.add_argument("--run-id", required=True, help="Run ID to generate an image for.")
    parser.add_argument("--api-token", default=None, help="API token for guarded API mode.")
    parser.add_argument("--bind", action="store_true", help="Bind generated image to the run via creator-assets.")
    parser.add_argument("--prompt-out", default=None, help="Optional path to write the generated image prompt.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_url = args.base_url.rstrip("/")
    headers = build_headers(args.api_token)

    try:
        response = requests.get(f"{base_url}/runs/{args.run_id}", headers=headers, timeout=30)
        response.raise_for_status()
        run_data = response.json()
    except (requests.RequestException, ValueError) as exc:
        _print_json({"ok": False, "error": f"failed to load run: {exc}"})
        return 2

    if not run_data.get("ok"):
        _print_json({"ok": False, "error": run_data.get("error") or "run API returned ok=false"})
        return 2
    run = run_data["run"]
    if run.get("status") != "success":
        _print_json({"ok": False, "error": "run must be successful before image generation"})
        return 2

    prompt = openai_image.build_image_prompt(run)
    if args.prompt_out:
        write_prompt(Path(args.prompt_out), prompt)

    settings = openai_image.load_image_settings()
    try:
        generated = openai_image.generate_image(settings, prompt)
        image_path = openai_image.save_generated_image(
            run_id=args.run_id,
            image_bytes=generated.image_bytes,
        )
    except openai_image.OpenAIImageError as exc:
        _print_json({"ok": False, "error": str(exc)})
        return 1

    output: dict[str, Any] = {
        "ok": True,
        "run_id": args.run_id,
        "image_path": str(image_path),
        "model": generated.model,
        "provider_mode": generated.provider_mode,
        "usage": generated.usage,
        "raw_metadata": generated.raw_metadata,
        "bound": False,
    }

    if args.bind:
        payload = build_creator_asset_payload(
            image_bytes=generated.image_bytes,
            filename=image_path.name,
        )
        try:
            bind_response = requests.post(
                f"{base_url}/runs/{args.run_id}/creator-assets",
                json=payload,
                headers=headers,
                timeout=60,
            )
            bind_response.raise_for_status()
            bind_data = bind_response.json()
        except (requests.RequestException, ValueError) as exc:
            output.update({"ok": False, "bind_error": f"failed to bind image: {exc}"})
            _print_json(output)
            return 2
        output["bind_response"] = _compact_bind_response(bind_data)
        output["bound"] = bool(bind_data.get("ok"))
        if not bind_data.get("ok"):
            output["ok"] = False
            output["bind_error"] = bind_data.get("error") or "bind API returned ok=false"
            _print_json(output)
            return 2

    _print_json(output)
    return 0


def _compact_bind_response(data: dict[str, Any]) -> dict[str, Any]:
    run = data.get("run") or {}
    summary = run.get("summary") or {}
    state = run.get("state") or {}
    return {
        "ok": data.get("ok"),
        "run_id": run.get("run_id"),
        "creator_images_count": summary.get("creator_images_count"),
        "creator_image_files": state.get("creator_image_files") or [],
        "error": data.get("error"),
    }


def _print_json(data: Any) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe_text = text.encode(encoding, errors="backslashreplace").decode(
            encoding,
            errors="replace",
        )
        sys.stdout.write(safe_text)


if __name__ == "__main__":
    raise SystemExit(main())
