from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, TypedDict


class Block(TypedDict):
    text: str
    block_type: str
    page: int
    anchor: str
    bbox: list[float]
    is_heading: bool


_converter: Any | None = None
_converter_lock = threading.Lock()

HEADING_LABELS = frozenset({"section_header"})
TABLE_LABELS = frozenset({"table"})


def get_converter() -> Any:
    """Return the process-wide DocumentConverter (model init is expensive)."""
    global _converter
    if _converter is None:
        with _converter_lock:
            if _converter is None:
                _converter = _build_converter()
    return _converter


def reset_converter() -> None:
    """Test helper: drop the singleton so the next call rebuilds it."""
    global _converter
    with _converter_lock:
        _converter = None


def _build_converter() -> Any:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    options.do_ocr = False
    options.do_table_structure = True
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options),
        }
    )


def normalize_bbox(
    left: float,
    top: float,
    right: float,
    bottom: float,
    page_width: float,
    page_height: float,
    *,
    origin: str = "BOTTOMLEFT",
) -> list[float]:
    """Convert a PDF-point bbox to normalized 0-1 top-left [l, t, r, b]."""
    origin_key = origin.replace("_", "").replace("-", "").upper()
    if origin_key in {"BOTTOMLEFT", "BOTTOMLEFTORIGIN"}:
        top = page_height - top
        bottom = page_height - bottom
    if page_width <= 0 or page_height <= 0:
        return [0.0, 0.0, 0.0, 0.0]
    return [
        left / page_width,
        top / page_height,
        right / page_width,
        bottom / page_height,
    ]


def extract_pdf(path: str | Path) -> tuple[list[Block], int]:
    converter = get_converter()
    result = converter.convert(str(path))
    document = result.document
    blocks = blocks_from_document(document)
    pages = getattr(document, "pages", None) or {}
    if pages:
        page_count = len(pages)
    else:
        page_count = max((block["page"] for block in blocks), default=0)
    return blocks, page_count


def blocks_from_document(document: Any) -> list[Block]:
    blocks: list[Block] = []
    page_indexes: dict[int, int] = {}
    for item, _level in document.iterate_items():
        label = _item_label(item)
        text = _item_text(item, document)
        if not text:
            continue
        page, bbox = _item_location(item, document)
        page_indexes[page] = page_indexes.get(page, 0) + 1
        blocks.append(
            {
                "text": text,
                "block_type": label,
                "page": page,
                "anchor": f"p{page}-{page_indexes[page]}",
                "bbox": bbox,
                "is_heading": label in HEADING_LABELS,
            }
        )
    return blocks


def _item_label(item: Any) -> str:
    label = getattr(item, "label", None)
    if label is None:
        return "paragraph"
    value = getattr(label, "value", None)
    if isinstance(value, str) and value:
        return value
    name = getattr(label, "name", None)
    if isinstance(name, str) and name:
        return name.lower()
    return str(label)


def _item_text(item: Any, document: Any) -> str:
    label = _item_label(item)
    if label in TABLE_LABELS or type(item).__name__ == "TableItem":
        return _table_text(item, document)
    text = getattr(item, "text", None)
    if isinstance(text, str):
        return text.strip()
    return ""


def _table_text(item: Any, document: Any) -> str:
    export_md = getattr(item, "export_to_markdown", None)
    if callable(export_md):
        try:
            markdown = export_md(doc=document)
        except TypeError:
            markdown = export_md()
        if isinstance(markdown, str) and markdown.strip():
            return markdown.strip()
    export_df = getattr(item, "export_to_dataframe", None)
    if callable(export_df):
        frame = export_df()
        to_csv = getattr(frame, "to_csv", None)
        if callable(to_csv):
            csv_text = to_csv(index=False)
            if isinstance(csv_text, str) and csv_text.strip():
                return csv_text.strip()
    text = getattr(item, "text", None)
    if isinstance(text, str):
        return text.strip()
    return ""


def _item_location(item: Any, document: Any) -> tuple[int, list[float]]:
    prov_list = getattr(item, "prov", None) or []
    prov = prov_list[0] if prov_list else None
    page = int(getattr(prov, "page_no", 1) or 1)
    width, height = _page_size(document, page)
    bbox_obj = getattr(prov, "bbox", None) if prov is not None else None
    if bbox_obj is None:
        return page, [0.0, 0.0, 0.0, 0.0]
    return page, _bbox_from_docling(bbox_obj, width, height)


def _page_size(document: Any, page_no: int) -> tuple[float, float]:
    pages = getattr(document, "pages", None) or {}
    page = None
    if isinstance(pages, dict):
        page = pages.get(page_no)
        if page is None:
            page = pages.get(page_no - 1)
    size = getattr(page, "size", None) if page is not None else None
    width = float(getattr(size, "width", 0.0) or 0.0)
    height = float(getattr(size, "height", 0.0) or 0.0)
    if width <= 0:
        width = 1.0
    if height <= 0:
        height = 1.0
    return width, height


def _bbox_from_docling(bbox: Any, page_width: float, page_height: float) -> list[float]:
    to_top_left = getattr(bbox, "to_top_left_origin", None)
    if callable(to_top_left):
        converted = to_top_left(page_height)
        return normalize_bbox(
            float(converted.l),
            float(converted.t),
            float(converted.r),
            float(converted.b),
            page_width,
            page_height,
            origin="TOPLEFT",
        )
    origin = "BOTTOMLEFT"
    coord = getattr(bbox, "coord_origin", None)
    if coord is not None:
        origin = str(getattr(coord, "name", coord))
    return normalize_bbox(
        float(bbox.l),
        float(bbox.t),
        float(bbox.r),
        float(bbox.b),
        page_width,
        page_height,
        origin=origin,
    )
