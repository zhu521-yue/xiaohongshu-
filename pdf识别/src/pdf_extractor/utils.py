from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def normalize_table(rows: Iterable[Iterable[object]]) -> list[list[str]]:
    return [[normalize_cell(cell) for cell in row] for row in rows]


def safe_stem(value: str, fallback: str = "pdf") -> str:
    stem = Path(value).stem or fallback
    stem = re.sub(r"[^\w.-]+", "_", stem, flags=re.UNICODE).strip("._")
    return stem or fallback


def relative_to(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def bbox_area(bbox: tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = bbox
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def bbox_intersection_area(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    ax0, ay0, ax1, ay1 = first
    bx0, by0, bx1, by1 = second
    x0 = max(ax0, bx0)
    y0 = max(ay0, by0)
    x1 = min(ax1, bx1)
    y1 = min(ay1, by1)
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def bbox_overlap_ratio(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    area = bbox_area(first)
    if area <= 0:
        return 0.0
    return bbox_intersection_area(first, second) / area
