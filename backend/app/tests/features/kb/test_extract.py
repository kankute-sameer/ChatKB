from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from app.core.log import get_logger
from app.features.kb.ingestion.extract import (
    WARMUP_PDF,
    blocks_and_images_from_document,
    blocks_from_document,
    normalize_bbox,
    warm_converter,
)
from app.main import _warm_docling


def test_normalize_bbox_bottomleft_pdf_points_to_unit_topleft() -> None:
    # US Letter, a box at x=10%–50% and (bottom-left) y=50%–60%.
    page_width, page_height = 612.0, 792.0
    left, right = 61.2, 306.0
    bottom, top = 396.0, 475.2
    result = normalize_bbox(
        left, top, right, bottom, page_width, page_height, origin="BOTTOMLEFT"
    )
    assert result == [0.1, 0.4, 0.5, 0.5]


def test_normalize_bbox_already_topleft() -> None:
    result = normalize_bbox(61.2, 316.8, 306.0, 396.0, 612.0, 792.0, origin="TOPLEFT")
    assert result == [0.1, 0.4, 0.5, 0.5]


def test_blocks_from_mocked_document_have_normalized_shape() -> None:
    bbox = SimpleNamespace(
        l=61.2,
        t=475.2,
        r=306.0,
        b=396.0,
        coord_origin=SimpleNamespace(name="BOTTOMLEFT"),
    )
    heading = SimpleNamespace(
        text="Overview",
        label=SimpleNamespace(value="section_header"),
        prov=[SimpleNamespace(page_no=1, bbox=bbox)],
    )
    paragraph = SimpleNamespace(
        text="Body copy.",
        label=SimpleNamespace(value="paragraph"),
        prov=[SimpleNamespace(page_no=1, bbox=bbox)],
    )
    table = SimpleNamespace(
        text="",
        label=SimpleNamespace(value="table"),
        prov=[SimpleNamespace(page_no=1, bbox=bbox)],
        export_to_markdown=lambda **_kwargs: "| A | B |\n| --- | --- |\n| 1 | 2 |",
    )
    document = SimpleNamespace(
        pages={1: SimpleNamespace(size=SimpleNamespace(width=612.0, height=792.0))},
        iterate_items=lambda: [(heading, 0), (paragraph, 0), (table, 0)],
    )

    blocks = blocks_from_document(document)
    assert [block["block_type"] for block in blocks] == [
        "section_header",
        "paragraph",
        "table",
    ]
    assert [block["anchor"] for block in blocks] == ["p1-1", "p1-2", "p1-3"]
    assert blocks[0]["is_heading"] is True
    assert blocks[1]["is_heading"] is False
    assert blocks[1]["text"] == "Body copy."
    assert blocks[2]["text"].startswith("| A | B |")
    for block in blocks:
        assert block["page"] == 1
        assert block["bbox"] == [0.1, 0.4, 0.5, 0.5]
        assert set(block) == {
            "text",
            "block_type",
            "page",
            "anchor",
            "bbox",
            "is_heading",
        }


def test_picture_filter_preserves_reading_order_and_location() -> None:
    bbox = SimpleNamespace(
        l=61.2,
        t=475.2,
        r=306.0,
        b=396.0,
        coord_origin=SimpleNamespace(name="BOTTOMLEFT"),
    )
    before = SimpleNamespace(
        text="Before image.",
        label=SimpleNamespace(value="paragraph"),
        prov=[SimpleNamespace(page_no=1, bbox=bbox)],
    )
    small_calls: list[object] = []

    def small_image(document: object) -> Image.Image:
        small_calls.append(document)
        return Image.new("RGB", (32, 32))

    small = SimpleNamespace(
        label=SimpleNamespace(value="picture"),
        prov=[SimpleNamespace(page_no=1, bbox=bbox)],
        get_image=small_image,
    )
    large_calls: list[object] = []

    def large_image(document: object) -> Image.Image:
        large_calls.append(document)
        return Image.new("RGB", (200, 100))

    large = SimpleNamespace(
        label=SimpleNamespace(value="picture"),
        prov=[SimpleNamespace(page_no=1, bbox=bbox)],
        get_image=large_image,
    )
    after = SimpleNamespace(
        text="After image.",
        label=SimpleNamespace(value="paragraph"),
        prov=[SimpleNamespace(page_no=1, bbox=bbox)],
    )
    document = SimpleNamespace(
        pages={1: SimpleNamespace(size=SimpleNamespace(width=612.0, height=792.0))},
        iterate_items=lambda: [(before, 0), (small, 0), (large, 0), (after, 0)],
    )

    blocks, images = blocks_and_images_from_document(
        document,
        image_min_dimension_px=64,
    )

    assert [block["text"] for block in blocks] == ["Before image.", "After image."]
    assert len(images) == 1
    assert images[0].insert_at == 1
    assert images[0].page == 1
    assert images[0].bbox == [0.1, 0.4, 0.5, 0.5]
    assert images[0].anchor == "p1-2"
    assert len(small_calls) == 1
    assert len(large_calls) == 1


def test_warmup_pdf_is_bundled() -> None:
    assert WARMUP_PDF.is_file()
    assert WARMUP_PDF.read_bytes().startswith(b"%PDF")


def test_warm_converter_converts_bundled_sample(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class _Converter:
        def convert(self, path: str) -> None:
            calls.append(path)

    monkeypatch.setattr(
        "app.features.kb.ingestion.extract.get_converter",
        lambda: _Converter(),
    )
    warm_converter()
    assert calls == [str(WARMUP_PDF)]


@pytest.mark.asyncio
async def test_startup_warms_converter_when_artifacts_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifacts = tmp_path / "docling"
    artifacts.mkdir()
    monkeypatch.setenv("DOCLING_ARTIFACTS_PATH", str(artifacts))
    warmup = AsyncMock()
    monkeypatch.setattr("app.main.asyncio.to_thread", warmup)
    await _warm_docling(get_logger("chatkb.test"))
    warmup.assert_awaited_once()
    assert warmup.await_args is not None
    assert warmup.await_args.args[0] is warm_converter


@pytest.mark.asyncio
async def test_startup_skips_warmup_without_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DOCLING_ARTIFACTS_PATH", raising=False)
    warmup = AsyncMock()
    monkeypatch.setattr("app.main.asyncio.to_thread", warmup)
    await _warm_docling(get_logger("chatkb.test"))
    warmup.assert_not_awaited()
