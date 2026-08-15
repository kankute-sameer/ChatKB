from app.features.kb.ingestion.chunk import chunk_blocks, estimate_tokens
from app.features.kb.ingestion.extract import Block


def _block(
    text: str,
    *,
    block_type: str = "paragraph",
    page: int = 1,
    anchor: str = "p1-1",
    is_heading: bool = False,
) -> Block:
    return {
        "text": text,
        "block_type": block_type,
        "page": page,
        "anchor": anchor,
        "bbox": [0.1, 0.1, 0.9, 0.2],
        "is_heading": is_heading,
    }


def test_each_body_block_becomes_one_chunk_with_heading_prepended() -> None:
    blocks = [
        _block(
            "Introduction",
            block_type="section_header",
            anchor="p1-1",
            is_heading=True,
        ),
        _block("First paragraph.", anchor="p1-2"),
        _block("Second paragraph.", anchor="p1-3"),
        _block(
            "Details",
            block_type="section_header",
            page=2,
            anchor="p2-1",
            is_heading=True,
        ),
        _block("Later body.", page=2, anchor="p2-2"),
    ]
    chunks = chunk_blocks(blocks)
    assert [chunk.block_type for chunk in chunks] == [
        "paragraph",
        "paragraph",
        "paragraph",
    ]
    assert [chunk.anchor for chunk in chunks] == ["p1-2", "p1-3", "p2-2"]
    assert chunks[0].text == "Introduction\n\nFirst paragraph."
    assert chunks[1].text == "Introduction\n\nSecond paragraph."
    assert chunks[2].text == "Details\n\nLater body."
    assert chunks[0].section_header == "Introduction"
    assert chunks[2].section_header == "Details"
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]


def test_heading_blocks_are_not_body_chunks() -> None:
    blocks = [
        _block("Only heading", block_type="section_header", is_heading=True),
    ]
    assert chunk_blocks(blocks) == []


def test_normal_blocks_do_not_split() -> None:
    blocks = [_block("A short paragraph stays whole.")]
    chunks = chunk_blocks(blocks)
    assert len(chunks) == 1
    assert chunks[0].text == "A short paragraph stays whole."
    assert chunks[0].anchor == "p1-1"


def test_oversized_block_splits_at_sentence_boundaries() -> None:
    sentence = "This sentence is used to inflate a single block past the token guard. "
    text = sentence * 150
    assert estimate_tokens(text) > 2000
    chunks = chunk_blocks([_block(text, anchor="p1-3")])
    assert len(chunks) > 1
    assert all(chunk.page == 1 for chunk in chunks)
    assert all(chunk.section_header is None for chunk in chunks)
    assert chunks[0].anchor == "p1-3.1"
    assert chunks[1].anchor == "p1-3.2"
    rebuilt = " ".join(chunk.text for chunk in chunks)
    assert "inflate a single block" in rebuilt
