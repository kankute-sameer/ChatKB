from types import SimpleNamespace

from app.features.kb.ingestion.extract import blocks_from_document, normalize_bbox


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
