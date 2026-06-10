from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BBox = tuple[float, float, float, float]


@dataclass
class TableResult:
    page_number: int
    index: int
    rows: list[list[str]]
    csv_path: str | None = None
    bbox: BBox | None = None

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        return max((len(row) for row in self.rows), default=0)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["row_count"] = self.row_count
        data["column_count"] = self.column_count
        return data


@dataclass
class FigureResult:
    page_number: int
    index: int
    kind: str
    path: str
    bbox: BBox | None = None
    width: float | None = None
    height: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PageResult:
    page_number: int
    width: float
    height: float
    text: str
    ocr_used: bool = False
    tables: list[TableResult] = field(default_factory=list)
    figures: list[FigureResult] = field(default_factory=list)

    def to_dict(self, include_text: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "page_number": self.page_number,
            "width": self.width,
            "height": self.height,
            "ocr_used": self.ocr_used,
            "text_length": len(self.text),
            "tables": [table.to_dict() for table in self.tables],
            "figures": [figure.to_dict() for figure in self.figures],
        }
        if include_text:
            data["text"] = self.text
        return data


@dataclass
class ExtractionResult:
    source_pdf: str
    output_dir: str
    page_count: int
    processed_pages: int
    metadata: dict[str, Any]
    pages: list[PageResult]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    @property
    def table_count(self) -> int:
        return sum(len(page.tables) for page in self.pages)

    @property
    def figure_count(self) -> int:
        return sum(len(page.figures) for page in self.pages)

    @property
    def text_length(self) -> int:
        return sum(len(page.text) for page in self.pages)

    def to_dict(self, include_text: bool = True) -> dict[str, Any]:
        return {
            "source_pdf": self.source_pdf,
            "output_dir": self.output_dir,
            "page_count": self.page_count,
            "processed_pages": self.processed_pages,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "summary": {
                "text_length": self.text_length,
                "table_count": self.table_count,
                "figure_count": self.figure_count,
            },
            "pages": [page.to_dict(include_text=include_text) for page in self.pages],
        }

    @classmethod
    def build(
        cls,
        source_pdf: Path,
        output_dir: Path,
        page_count: int,
        metadata: dict[str, Any],
        pages: list[PageResult],
    ) -> "ExtractionResult":
        return cls(
            source_pdf=str(source_pdf),
            output_dir=str(output_dir),
            page_count=page_count,
            processed_pages=len(pages),
            metadata=metadata,
            pages=pages,
        )
