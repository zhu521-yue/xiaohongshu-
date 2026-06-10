from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .extractor import MissingDependencyError, PdfExtractor
from .options import ExtractionOptions, parse_pages_spec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-extractor",
        description="Extract text, tables, images, and chart candidates from PDF files.",
    )
    parser.add_argument("pdf", help="Path to the PDF file.")
    parser.add_argument("-o", "--output", help="Output directory. Defaults to outputs/<pdf-name>.")
    parser.add_argument("--pages", help="1-based page spec, for example: 1,3-5.")
    parser.add_argument("--password", help="Password for encrypted PDFs.")
    parser.add_argument(
        "--ocr",
        choices=("off", "auto", "always"),
        default="off",
        help="OCR mode. auto only OCRs pages with no extracted text.",
    )
    parser.add_argument("--ocr-lang", default="eng", help="Tesseract language, e.g. chi_sim+eng.")
    parser.add_argument("--render-dpi", type=int, default=180, help="DPI for OCR and chart crops.")
    parser.add_argument("--no-tables", action="store_true", help="Skip table extraction.")
    parser.add_argument("--no-figures", action="store_true", help="Skip images and chart crops.")
    parser.add_argument(
        "--min-chart-width",
        type=float,
        default=120.0,
        help="Minimum chart candidate width in PDF points.",
    )
    parser.add_argument(
        "--min-chart-height",
        type=float,
        default=80.0,
        help="Minimum chart candidate height in PDF points.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        pages = parse_pages_spec(args.pages)
    except ValueError as exc:
        parser.error(str(exc))

    pdf_path = Path(args.pdf)
    output_dir = Path(args.output) if args.output else Path("outputs") / pdf_path.stem
    options = ExtractionOptions(
        pages=pages,
        password=args.password,
        extract_tables=not args.no_tables,
        extract_figures=not args.no_figures,
        ocr_mode=args.ocr,
        ocr_lang=args.ocr_lang,
        render_dpi=args.render_dpi,
        min_chart_width=args.min_chart_width,
        min_chart_height=args.min_chart_height,
    )

    try:
        result = PdfExtractor(options).extract(pdf_path, output_dir)
    except (FileNotFoundError, ValueError, MissingDependencyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Done: {result.processed_pages}/{result.page_count} pages")
    print(f"Text characters: {result.text_length}")
    print(f"Tables: {result.table_count}")
    print(f"Figures: {result.figure_count}")
    print(f"Output: {Path(result.output_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
