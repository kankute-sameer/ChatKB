import asyncio

import pytest
from PIL import Image

from app.features.kb.ingestion.assemble import assemble_content
from app.features.kb.ingestion.chunk import chunk_blocks
from app.features.kb.ingestion.describe_image import insert_image_descriptions
from app.features.kb.ingestion.extract import Block, ExtractedImage


def _block(text: str, anchor: str) -> Block:
    return {
        "text": text,
        "block_type": "paragraph",
        "page": 1,
        "anchor": anchor,
        "bbox": [0.1, 0.1, 0.9, 0.2],
        "is_heading": False,
    }


class _Describer:
    def __init__(self, description: str) -> None:
        self.description = description
        self.calls = 0

    async def describe_image(self, _image: Image.Image) -> str:
        self.calls += 1
        return self.description


@pytest.mark.asyncio
async def test_image_description_keeps_reading_order_and_becomes_chunk() -> None:
    blocks = [_block("Before image.", "p1-1"), _block("After image.", "p1-3")]
    candidate = ExtractedImage(
        image=Image.new("RGB", (200, 100)),
        insert_at=1,
        page=1,
        anchor="p1-2",
        bbox=[0.2, 0.3, 0.8, 0.7],
    )
    describer = _Describer("A lighthouse with green bands.")

    resolved = await insert_image_descriptions(
        blocks,
        [candidate],
        describer,
        max_concurrency=4,
    )

    assert [block["block_type"] for block in resolved] == [
        "paragraph",
        "image",
        "paragraph",
    ]
    assert describer.calls == 1
    assert assemble_content(resolved) == (
        "Before image.\n\n"
        "*[Image: A lighthouse with green bands.]*\n\n"
        "After image."
    )
    chunks = chunk_blocks(resolved)
    assert chunks[1].block_type == "image"
    assert chunks[1].text == "A lighthouse with green bands."
    assert chunks[1].page == 1
    assert chunks[1].bbox == [0.2, 0.3, 0.8, 0.7]


class _FailingDescriber:
    async def describe_image(self, _image: Image.Image) -> str:
        raise RuntimeError("vision failed")


@pytest.mark.asyncio
async def test_image_description_failure_skips_image_and_keeps_text() -> None:
    blocks = [_block("Before.", "p1-1"), _block("After.", "p1-3")]
    resolved = await insert_image_descriptions(
        blocks,
        [
            ExtractedImage(
                image=Image.new("RGB", (200, 100)),
                insert_at=1,
                page=1,
                anchor="p1-2",
                bbox=[0.2, 0.3, 0.8, 0.7],
            )
        ],
        _FailingDescriber(),
        max_concurrency=4,
    )
    assert resolved == blocks
    assert assemble_content(resolved) == "Before.\n\nAfter."


class _ConcurrentDescriber:
    def __init__(self) -> None:
        self.active = 0
        self.peak = 0

    async def describe_image(self, _image: Image.Image) -> str:
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return "Image"


@pytest.mark.asyncio
async def test_image_description_concurrency_is_bounded() -> None:
    describer = _ConcurrentDescriber()
    images = [
        ExtractedImage(
            image=Image.new("RGB", (100, 100)),
            insert_at=0,
            page=1,
            anchor=f"p1-{index}",
            bbox=[0.1, 0.1, 0.2, 0.2],
        )
        for index in range(1, 6)
    ]
    await insert_image_descriptions(
        [],
        images,
        describer,
        max_concurrency=2,
    )
    assert describer.peak == 2
