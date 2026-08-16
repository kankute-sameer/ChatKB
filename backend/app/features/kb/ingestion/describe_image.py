from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Protocol

from PIL import Image

from app.features.kb.ingestion.extract import Block, ExtractedImage


class ImageDescriber(Protocol):
    async def describe_image(self, image: Image.Image) -> str: ...


async def insert_image_descriptions(
    blocks: Sequence[Block],
    images: Sequence[ExtractedImage],
    describer: ImageDescriber,
    *,
    max_concurrency: int,
) -> list[Block]:
    if not images:
        return list(blocks)
    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def describe(candidate: ExtractedImage) -> str:
        try:
            async with semaphore:
                return (await describer.describe_image(candidate.image)).strip()
        except Exception:
            return ""

    descriptions = await asyncio.gather(*(describe(image) for image in images))
    by_position: dict[int, list[Block]] = {}
    for image, description in zip(images, descriptions, strict=True):
        if not description:
            continue
        by_position.setdefault(image.insert_at, []).append(
            {
                "text": description,
                "block_type": "image",
                "page": image.page,
                "anchor": image.anchor,
                "bbox": list(image.bbox),
                "is_heading": False,
            }
        )

    resolved: list[Block] = []
    for index, block in enumerate(blocks):
        resolved.extend(by_position.get(index, []))
        resolved.append(block)
    resolved.extend(by_position.get(len(blocks), []))
    return resolved
