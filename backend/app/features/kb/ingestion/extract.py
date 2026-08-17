from __future__ import annotations

import csv
import json
import re
import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from typing import Any, Literal, TypedDict

from docling_core.types.doc.items.picture.picture import PictureItem
from markdown_it import MarkdownIt
from PIL import Image


class Block(TypedDict):
    text: str
    block_type: str
    page: int | None
    anchor: str
    bbox: list[float] | None
    is_heading: bool


@dataclass(frozen=True)
class ExtractedImage:
    image: Image.Image
    insert_at: int
    page: int
    anchor: str
    bbox: list[float]


@dataclass(frozen=True)
class ProseExtraction:
    kind: Literal["prose"]
    blocks: list[Block]
    page_count: int | None
    images: list[ExtractedImage] = field(default_factory=list)


@dataclass(frozen=True)
class TableExtraction:
    kind: Literal["table"]
    columns: list[str]
    rows: list[dict[str, str]]
    column_types: dict[str, str]


ExtractionResult = ProseExtraction | TableExtraction

_converter: Any | None = None
_converter_lock = threading.Lock()
WARMUP_PDF = Path(__file__).with_name("warmup.pdf")

SCANNED_PDF_ERROR = "This PDF has no extractable text. Scanned PDFs are not supported."

HEADING_LABELS = frozenset({"section_header"})
TABLE_LABELS = frozenset({"table"})
SUPPORTED_EXTENSIONS = frozenset(
    {".pdf", ".docx", ".md", ".txt", ".csv", ".tsv", ".json"}
)
TABLE_SAMPLE_ROWS = 100
JSON_BLOCK_CHARS = 8_000
_BLANK_LINES_RE = re.compile(r"\n\s*\n+")


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


def warm_converter() -> None:
    """Load layout + TableFormer weights by converting the bundled sample PDF."""
    get_converter().convert(str(WARMUP_PDF))


def _build_converter() -> Any:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    options.do_ocr = False
    options.do_table_structure = True
    options.generate_picture_images = True
    options.images_scale = 2.0
    return DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.DOCX],
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options),
        },
    )


def extract(
    path: str | Path,
    mime_type: str,
    *,
    image_min_dimension_px: int = 64,
) -> ExtractionResult:
    """Route a supported resource to its normalized prose or table extractor."""
    file_path = Path(path)
    extension = file_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {extension or mime_type}")
    if extension == ".pdf":
        blocks, page_count, images = extract_pdf(
            file_path,
            image_min_dimension_px=image_min_dimension_px,
        )
        return ProseExtraction("prose", blocks, page_count, images)
    if extension == ".docx":
        return ProseExtraction("prose", extract_docx(file_path), None)
    if extension == ".md":
        return ProseExtraction("prose", extract_markdown(file_path), None)
    if extension == ".txt":
        return ProseExtraction("prose", extract_text(file_path), None)
    if extension in {".csv", ".tsv"}:
        delimiter = "\t" if extension == ".tsv" else ","
        return extract_delimited(file_path, delimiter=delimiter)
    return extract_json(file_path)


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


def extract_pdf(
    path: str | Path,
    *,
    image_min_dimension_px: int = 64,
) -> tuple[list[Block], int, list[ExtractedImage]]:
    converter = get_converter()
    result = converter.convert(str(path))
    document = result.document
    blocks, images = blocks_and_images_from_document(
        document,
        image_min_dimension_px=max(1, image_min_dimension_px),
    )
    if not blocks:
        raise ValueError(SCANNED_PDF_ERROR)
    pages = getattr(document, "pages", None) or {}
    if pages:
        page_count = len(pages)
    else:
        page_count = max(
            (block["page"] or 0 for block in blocks),
            default=0,
        )
    return blocks, page_count, images


def extract_docx(path: str | Path) -> list[Block]:
    converter = get_converter()
    result = converter.convert(str(path))
    return blocks_from_document(result.document, include_locations=False)


def extract_markdown(path: str | Path) -> list[Block]:
    text = Path(path).read_text(encoding="utf-8-sig")
    tokens = MarkdownIt("commonmark").parse(text)
    blocks: list[Block] = []
    counters: dict[str, int] = {}
    previous_type = ""
    for token in tokens:
        if token.type == "inline":
            content = token.content.strip()
            if content:
                is_heading = previous_type == "heading_open"
                block_type = "section_header" if is_heading else "paragraph"
                counters[block_type] = counters.get(block_type, 0) + 1
                blocks.append(
                    _text_block(
                        content,
                        block_type,
                        f"{block_type}-{counters[block_type]}",
                        is_heading=is_heading,
                    )
                )
        previous_type = token.type
    return blocks


def extract_text(path: str | Path) -> list[Block]:
    text = Path(path).read_text(encoding="utf-8-sig")
    paragraphs = [
        paragraph.strip()
        for paragraph in _BLANK_LINES_RE.split(text)
        if paragraph.strip()
    ]
    return [
        _text_block(paragraph, "paragraph", f"paragraph-{index}")
        for index, paragraph in enumerate(paragraphs, start=1)
    ]


def extract_delimited(path: str | Path, *, delimiter: str) -> TableExtraction:
    text = Path(path).read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(text), delimiter=delimiter)
    columns = [str(name).strip() for name in (reader.fieldnames or []) if name]
    if not columns:
        raise ValueError("Tabular file has no header")
    rows: list[dict[str, str]] = []
    for raw_row in reader:
        rows.append(
            {column: str(raw_row.get(column) or "").strip() for column in columns}
        )
        if len(rows) >= TABLE_SAMPLE_ROWS:
            break
    return TableExtraction("table", columns, rows, infer_column_types(columns, rows))


def extract_json(path: str | Path) -> ExtractionResult:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    table = _json_table(value)
    if table is not None:
        return table
    pretty = json.dumps(value, ensure_ascii=False, indent=2)
    blocks = [
        _text_block(
            pretty[start : start + JSON_BLOCK_CHARS],
            "paragraph",
            f"json-{index}",
        )
        for index, start in enumerate(
            range(0, len(pretty), JSON_BLOCK_CHARS),
            start=1,
        )
    ]
    return ProseExtraction("prose", blocks, None)


def infer_column_types(
    columns: list[str],
    rows: list[dict[str, str]],
) -> dict[str, str]:
    return {
        column: _infer_values([row.get(column, "") for row in rows])
        for column in columns
    }


def _json_table(value: object) -> TableExtraction | None:
    if not isinstance(value, list) or not value:
        return None
    if not all(isinstance(row, dict) for row in value):
        return None
    object_rows = [row for row in value if isinstance(row, dict)]
    if not all(all(_is_scalar(cell) for cell in row.values()) for row in object_rows):
        return None
    columns = list(dict.fromkeys(str(key) for row in object_rows for key in row))
    if not columns:
        return None
    shared = set(object_rows[0])
    union = set(object_rows[0])
    for row in object_rows[1:]:
        shared &= set(row)
        union |= set(row)
    if union and len(shared) / len(union) < 0.6:
        return None
    rows = [
        {column: _scalar_text(row.get(column)) for column in columns}
        for row in object_rows[:TABLE_SAMPLE_ROWS]
    ]
    return TableExtraction("table", columns, rows, infer_column_types(columns, rows))


def _is_scalar(value: object) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _scalar_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _infer_values(values: list[str]) -> str:
    present = [value.strip() for value in values if value.strip()]
    if not present:
        return "string"
    if all(_is_integer(value) for value in present):
        return "integer"
    if all(_is_number(value) for value in present):
        return "number"
    if all(_is_date(value) for value in present):
        return "date"
    return "string"


def _is_integer(value: str) -> bool:
    try:
        int(value)
    except ValueError:
        return False
    return True


def _is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def _is_date(value: str) -> bool:
    normalized = value.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
        return True
    except ValueError:
        try:
            date.fromisoformat(value)
            return True
        except ValueError:
            return False


def _text_block(
    text: str,
    block_type: str,
    anchor: str,
    *,
    is_heading: bool = False,
) -> Block:
    return {
        "text": text,
        "block_type": block_type,
        "page": None,
        "anchor": anchor,
        "bbox": None,
        "is_heading": is_heading,
    }


def blocks_from_document(
    document: Any,
    *,
    include_locations: bool = True,
) -> list[Block]:
    blocks: list[Block] = []
    page_indexes: dict[int, int] = {}
    for item, _level in document.iterate_items():
        label = _item_label(item)
        text = _item_text(item, document)
        if not text:
            continue
        if include_locations:
            page, bbox = _item_location(item, document)
            page_key = page or 0
        else:
            page, bbox = None, None
            page_key = 0
        page_indexes[page_key] = page_indexes.get(page_key, 0) + 1
        prefix = f"p{page}" if page is not None else "block"
        blocks.append(
            {
                "text": text,
                "block_type": label,
                "page": page,
                "anchor": f"{prefix}-{page_indexes[page_key]}",
                "bbox": bbox,
                "is_heading": label in HEADING_LABELS,
            }
        )
    return blocks


def blocks_and_images_from_document(
    document: Any,
    *,
    image_min_dimension_px: int,
) -> tuple[list[Block], list[ExtractedImage]]:
    blocks: list[Block] = []
    images: list[ExtractedImage] = []
    page_indexes: dict[int, int] = {}
    for item, _level in document.iterate_items():
        if _is_picture_item(item):
            image = _picture_image(item, document)
            if image is None or min(image.size) < image_min_dimension_px:
                continue
            page, bbox = _item_location(item, document)
            page_indexes[page] = page_indexes.get(page, 0) + 1
            images.append(
                ExtractedImage(
                    image=image,
                    insert_at=len(blocks),
                    page=page,
                    anchor=f"p{page}-{page_indexes[page]}",
                    bbox=bbox,
                )
            )
            continue

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
    return blocks, images


def _is_picture_item(item: Any) -> bool:
    return isinstance(item, PictureItem) or _item_label(item) in {"picture", "chart"}


def _picture_image(item: Any, document: Any) -> Image.Image | None:
    get_image = getattr(item, "get_image", None)
    if not callable(get_image):
        return None
    try:
        image = get_image(document)
    except Exception:
        return None
    if not isinstance(image, Image.Image):
        return None
    return image.copy()


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
