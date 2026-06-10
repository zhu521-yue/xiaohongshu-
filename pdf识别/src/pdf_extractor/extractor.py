from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from .exporters import write_outputs
from .models import BBox, ExtractionResult, FigureResult, PageResult, TableResult
from .options import ExtractionOptions
from .utils import (
    bbox_area,
    bbox_overlap_ratio,
    ensure_directory,
    normalize_table,
    relative_to,
)


class MissingDependencyError(RuntimeError):
    pass


class PdfExtractor:
    def __init__(self, options: ExtractionOptions | None = None) -> None:
        self.options = options or ExtractionOptions()

    def extract(self, pdf_path: str | Path, output_dir: str | Path) -> ExtractionResult:
        fitz = _load_pymupdf()
        pdf_path = Path(pdf_path).expanduser().resolve()
        output_dir = Path(output_dir).expanduser().resolve()

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        if pdf_path.suffix.lower() != ".pdf":
            raise ValueError(f"Input must be a PDF file: {pdf_path}")

        ensure_directory(output_dir)
        figures_dir = ensure_directory(output_dir / "figures")

        doc = fitz.open(pdf_path)
        try:
            if doc.needs_pass and not doc.authenticate(self.options.password or ""):
                raise ValueError("PDF is encrypted. Provide the correct password.")

            metadata = dict(doc.metadata or {})
            page_numbers = self._selected_pages(len(doc))

            table_pages = self._extract_tables(pdf_path, len(doc), page_numbers)
            pages: list[PageResult] = []

            for page_index in page_numbers:
                page = doc.load_page(page_index - 1)
                text, ocr_used = self._extract_text(page)
                page_tables = table_pages.get(page_index, [])
                table_bboxes = [table.bbox for table in page_tables if table.bbox]

                figures: list[FigureResult] = []
                if self.options.extract_figures:
                    figures.extend(
                        self._extract_embedded_images(
                            doc=doc,
                            page=page,
                            page_number=page_index,
                            figures_dir=figures_dir,
                            output_dir=output_dir,
                        )
                    )
                    figures.extend(
                        self._extract_chart_candidates(
                            page=page,
                            page_number=page_index,
                            table_bboxes=table_bboxes,
                            figures_dir=figures_dir,
                            output_dir=output_dir,
                            start_index=len(figures) + 1,
                        )
                    )

                pages.append(
                    PageResult(
                        page_number=page_index,
                        width=float(page.rect.width),
                        height=float(page.rect.height),
                        text=text,
                        ocr_used=ocr_used,
                        tables=page_tables,
                        figures=figures,
                    )
                )

            result = ExtractionResult.build(
                source_pdf=pdf_path,
                output_dir=output_dir,
                page_count=len(doc),
                metadata=metadata,
                pages=pages,
            )
            write_outputs(result)
            return result
        finally:
            doc.close()

    def _selected_pages(self, page_count: int) -> list[int]:
        if self.options.pages is None:
            return list(range(1, page_count + 1))
        invalid = sorted(page for page in self.options.pages if page > page_count)
        if invalid:
            raise ValueError(f"Page number out of range: {invalid[0]} > {page_count}")
        return sorted(self.options.pages)

    def _extract_text(self, page: Any) -> tuple[str, bool]:
        text = page.get_text("text").strip()
        mode = self.options.ocr_mode
        if mode == "off":
            return text, False
        if mode == "auto" and text:
            return text, False
        if mode not in {"auto", "always"}:
            raise ValueError(f"Unsupported OCR mode: {mode}")

        ocr_text = _ocr_page(page, self.options.render_dpi, self.options.ocr_lang).strip()
        if mode == "always":
            return ocr_text, True
        return (ocr_text or text), bool(ocr_text)

    def _extract_tables(
        self,
        pdf_path: Path,
        page_count: int,
        page_numbers: list[int],
    ) -> dict[int, list[TableResult]]:
        if not self.options.extract_tables:
            return {}

        try:
            import pdfplumber
        except ImportError as exc:
            raise MissingDependencyError(
                "Missing dependency: pdfplumber. Install with `pip install -r requirements.txt`."
            ) from exc

        table_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "intersection_tolerance": 5,
            "snap_tolerance": 3,
            "join_tolerance": 3,
        }
        results: dict[int, list[TableResult]] = {}
        selected = set(page_numbers)
        with pdfplumber.open(str(pdf_path), password=self.options.password) as pdf:
            if len(pdf.pages) != page_count:
                page_count = min(page_count, len(pdf.pages))

            for page_number in page_numbers:
                if page_number > page_count or page_number not in selected:
                    continue
                plumber_page = pdf.pages[page_number - 1]
                tables = []
                try:
                    found_tables = plumber_page.find_tables(table_settings=table_settings)
                except Exception:
                    found_tables = []

                if found_tables:
                    for index, found_table in enumerate(found_tables, start=1):
                        rows = normalize_table(found_table.extract() or [])
                        if rows:
                            tables.append(
                                TableResult(
                                    page_number=page_number,
                                    index=index,
                                    rows=rows,
                                    bbox=_tuple_bbox(found_table.bbox),
                                )
                            )
                else:
                    raw_tables = plumber_page.extract_tables(table_settings=table_settings) or []
                    for index, raw_table in enumerate(raw_tables, start=1):
                        rows = normalize_table(raw_table)
                        if rows:
                            tables.append(
                                TableResult(page_number=page_number, index=index, rows=rows)
                            )

                results[page_number] = tables
        return results

    def _extract_embedded_images(
        self,
        doc: Any,
        page: Any,
        page_number: int,
        figures_dir: Path,
        output_dir: Path,
    ) -> list[FigureResult]:
        figures: list[FigureResult] = []
        seen_xrefs: set[int] = set()
        for image_info in page.get_images(full=True):
            xref = int(image_info[0])
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            image = doc.extract_image(xref)
            ext = image.get("ext", "png")
            data = image.get("image")
            if not data:
                continue

            index = len(figures) + 1
            path = figures_dir / f"page_{page_number:03d}_image_{index:02d}.{ext}"
            path.write_bytes(data)

            bbox = None
            rects = page.get_image_rects(xref)
            if rects:
                bbox = _rect_to_bbox(rects[0])

            figures.append(
                FigureResult(
                    page_number=page_number,
                    index=index,
                    kind="embedded_image",
                    path=relative_to(path, output_dir),
                    bbox=bbox,
                    width=float(image.get("width") or 0) or None,
                    height=float(image.get("height") or 0) or None,
                )
            )
        return figures

    def _extract_chart_candidates(
        self,
        page: Any,
        page_number: int,
        table_bboxes: list[BBox],
        figures_dir: Path,
        output_dir: Path,
        start_index: int,
    ) -> list[FigureResult]:
        fitz = _load_pymupdf()
        candidates = self._find_chart_candidate_bboxes(page, table_bboxes)
        figures: list[FigureResult] = []
        matrix = fitz.Matrix(self.options.render_dpi / 72, self.options.render_dpi / 72)

        for offset, bbox in enumerate(candidates, start=0):
            rect = fitz.Rect(*bbox)
            index = start_index + offset
            path = figures_dir / f"page_{page_number:03d}_chart_{index:02d}.png"
            pixmap = page.get_pixmap(matrix=matrix, clip=rect, alpha=False)
            pixmap.save(path)
            figures.append(
                FigureResult(
                    page_number=page_number,
                    index=index,
                    kind="chart_candidate",
                    path=relative_to(path, output_dir),
                    bbox=bbox,
                    width=float(rect.width),
                    height=float(rect.height),
                )
            )

        return figures

    def _find_chart_candidate_bboxes(self, page: Any, table_bboxes: list[BBox]) -> list[BBox]:
        page_area = float(page.rect.width * page.rect.height)
        drawing_bboxes = _drawing_bboxes(page)
        merged = _merge_bboxes(drawing_bboxes, self.options.chart_merge_gap)

        candidates: list[BBox] = []
        for bbox in merged:
            x0, y0, x1, y1 = bbox
            width = x1 - x0
            height = y1 - y0
            area = bbox_area(bbox)
            if width < self.options.min_chart_width:
                continue
            if height < self.options.min_chart_height:
                continue
            if area < self.options.min_chart_area:
                continue
            if page_area and area / page_area > 0.85:
                continue
            if any(bbox_overlap_ratio(bbox, table_bbox) > 0.65 for table_bbox in table_bboxes):
                continue
            candidates.append(_expand_bbox(bbox, margin=8, page_bbox=_rect_to_bbox(page.rect)))

        candidates.sort(key=lambda item: (item[1], item[0]))
        return candidates


def _load_pymupdf() -> Any:
    try:
        import pymupdf as fitz

        return fitz
    except ImportError:
        try:
            import fitz

            return fitz
        except ImportError as exc:
            raise MissingDependencyError(
                "Missing dependency: PyMuPDF. Install with `pip install -r requirements.txt`."
            ) from exc


def _ocr_page(page: Any, dpi: int, lang: str) -> str:
    try:
        from PIL import Image
        import pytesseract
    except ImportError as exc:
        raise MissingDependencyError(
            "Missing OCR dependency. Install `requirements-ocr.txt` and Tesseract."
        ) from exc

    fitz = _load_pymupdf()
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
    return pytesseract.image_to_string(image, lang=lang)


def _drawing_bboxes(page: Any) -> list[BBox]:
    bboxes: list[BBox] = []
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect is not None:
            bbox = _rect_to_bbox(rect)
            if bbox_area(bbox) > 0:
                bboxes.append(bbox)
                continue

        item_bboxes = [_drawing_item_bbox(item) for item in drawing.get("items", [])]
        item_bboxes = [bbox for bbox in item_bboxes if bbox is not None]
        if item_bboxes:
            bboxes.append(_union_bboxes(item_bboxes))
    return bboxes


def _drawing_item_bbox(item: Any) -> BBox | None:
    points: list[tuple[float, float]] = []
    for value in item:
        if hasattr(value, "x") and hasattr(value, "y"):
            points.append((float(value.x), float(value.y)))
        elif hasattr(value, "x0") and hasattr(value, "y0") and hasattr(value, "x1"):
            return _rect_to_bbox(value)

    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _merge_bboxes(bboxes: list[BBox], gap: float) -> list[BBox]:
    remaining = list(bboxes)
    merged: list[BBox] = []

    while remaining:
        current = remaining.pop(0)
        changed = True
        while changed:
            changed = False
            next_remaining: list[BBox] = []
            for candidate in remaining:
                if _bboxes_touch(current, candidate, gap):
                    current = _union_bboxes([current, candidate])
                    changed = True
                else:
                    next_remaining.append(candidate)
            remaining = next_remaining
        merged.append(current)

    return merged


def _bboxes_touch(first: BBox, second: BBox, gap: float) -> bool:
    ax0, ay0, ax1, ay1 = first
    bx0, by0, bx1, by1 = second
    return not (
        ax1 + gap < bx0
        or bx1 + gap < ax0
        or ay1 + gap < by0
        or by1 + gap < ay0
    )


def _union_bboxes(bboxes: list[BBox]) -> BBox:
    return (
        min(bbox[0] for bbox in bboxes),
        min(bbox[1] for bbox in bboxes),
        max(bbox[2] for bbox in bboxes),
        max(bbox[3] for bbox in bboxes),
    )


def _expand_bbox(bbox: BBox, margin: float, page_bbox: BBox) -> BBox:
    x0, y0, x1, y1 = bbox
    px0, py0, px1, py1 = page_bbox
    return (
        max(px0, x0 - margin),
        max(py0, y0 - margin),
        min(px1, x1 + margin),
        min(py1, y1 + margin),
    )


def _rect_to_bbox(rect: Any) -> BBox:
    return (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))


def _tuple_bbox(value: Any) -> BBox | None:
    if value is None:
        return None
    x0, y0, x1, y1 = value
    return (float(x0), float(y0), float(x1), float(y1))
