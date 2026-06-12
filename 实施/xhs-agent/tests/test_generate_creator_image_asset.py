from __future__ import annotations

import base64
from pathlib import Path

from scripts import generate_creator_image_asset


PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png"


def test_build_creator_asset_payload_encodes_generated_image() -> None:
    payload = generate_creator_image_asset.build_creator_asset_payload(
        image_bytes=PNG_BYTES,
        filename="cover.png",
    )

    assert payload == {
        "images": [
            {
                "filename": "cover.png",
                "content_base64": base64.b64encode(PNG_BYTES).decode("ascii"),
            }
        ]
    }


def test_build_headers_uses_optional_api_token() -> None:
    assert generate_creator_image_asset.build_headers("") == {}
    assert generate_creator_image_asset.build_headers("secret") == {
        "Authorization": "Bearer secret"
    }


def test_write_prompt_creates_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "prompt.txt"

    generate_creator_image_asset.write_prompt(target, "生成一张封面")

    assert target.read_text(encoding="utf-8") == "生成一张封面"
