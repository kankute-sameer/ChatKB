from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.features.kb.ingestion.extract import Block

MAX_CHUNK_TOKENS = 2000
CHARS_PER_TOKEN = 4
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    text: str
    section_header: str | None
    page: int
    anchor: str
    bbox: list[float]
    block_type: str


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def chunk_blocks(
    blocks: Sequence[Block],
    *,
    max_tokens: int = MAX_CHUNK_TOKENS,
) -> list[Chunk]:
    """Each non-heading block becomes one chunk, with the current heading prepended."""
    chunks: list[Chunk] = []
    current_header: str | None = None
    index = 0
    for block in blocks:
        if block["is_heading"] or block["block_type"] == "section_header":
            header = block["text"].strip()
            if header:
                current_header = header
            continue
        body = block["text"].strip()
        if not body:
            continue
        parts = split_oversized(body, max_tokens)
        for part_i, part in enumerate(parts):
            text = f"{current_header}\n\n{part}" if current_header else part
            anchor = (
                block["anchor"]
                if len(parts) == 1
                else f"{block['anchor']}.{part_i + 1}"
            )
            chunks.append(
                Chunk(
                    chunk_index=index,
                    text=text,
                    section_header=current_header,
                    page=block["page"],
                    anchor=anchor,
                    bbox=list(block["bbox"]),
                    block_type=block["block_type"],
                )
            )
            index += 1
    return chunks


def split_oversized(text: str, max_tokens: int = MAX_CHUNK_TOKENS) -> list[str]:
    if estimate_tokens(text) <= max_tokens:
        return [text]
    sentences = [
        part.strip() for part in _SENTENCE_RE.split(text.strip()) if part.strip()
    ]
    if not sentences:
        return _split_chars(text, max_tokens)
    packed: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if current and estimate_tokens(candidate) > max_tokens:
            packed.append(current)
            current = sentence
        else:
            current = candidate
        if estimate_tokens(current) > max_tokens:
            packed.extend(_split_chars(current, max_tokens))
            current = ""
    if current:
        packed.append(current)
    return packed or [text]


def _split_chars(text: str, max_tokens: int) -> list[str]:
    max_chars = max(max_tokens * CHARS_PER_TOKEN, 1)
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
