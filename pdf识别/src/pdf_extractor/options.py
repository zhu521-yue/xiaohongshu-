from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractionOptions:
    pages: set[int] | None = None
    password: str | None = None
    extract_tables: bool = True
    extract_figures: bool = True
    ocr_mode: str = "off"
    ocr_lang: str = "eng"
    render_dpi: int = 180
    chart_merge_gap: float = 10.0
    min_chart_width: float = 120.0
    min_chart_height: float = 80.0
    min_chart_area: float = 12_000.0


def parse_pages_spec(value: str | None) -> set[int] | None:
    """Parse a 1-based page spec like '1,3-5' into a set of page numbers."""
    if value is None or not value.strip():
        return None

    pages: set[int] = set()
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            start_raw, end_raw = part.split("-", 1)
            start = _parse_positive_int(start_raw.strip(), raw_part)
            end = _parse_positive_int(end_raw.strip(), raw_part)
            if start > end:
                raise ValueError(f"Invalid page range: {raw_part!r}")
            pages.update(range(start, end + 1))
        else:
            pages.add(_parse_positive_int(part, raw_part))

    return pages or None


def _parse_positive_int(value: str, source: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid page number in {source!r}") from exc
    if number < 1:
        raise ValueError(f"Page numbers are 1-based and must be positive: {source!r}")
    return number
