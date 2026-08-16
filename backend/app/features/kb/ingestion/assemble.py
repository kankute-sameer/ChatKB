from __future__ import annotations

from collections.abc import Sequence

from app.core.llm.types import LLM
from app.features.kb.ingestion.extract import Block
from app.features.kb.ingestion.prompts import FILE_SUMMARY_PROMPT

MAX_INDEX_INPUT_CHARS = 80_000


def assemble_content(blocks: Sequence[Block]) -> str:
    parts: list[str] = []
    for block in blocks:
        text = block["text"].strip()
        if not text:
            continue
        if block["is_heading"] or block["block_type"] == "section_header":
            parts.append(f"## {text}")
        elif block["block_type"] == "image":
            parts.append(f"*[Image: {text}]*")
        else:
            parts.append(text)
    return "\n\n".join(parts)


async def generate_file_summary(content_md: str, llm: LLM, model: str) -> str:
    content = content_md.strip() or "(empty document)"
    if len(content) > MAX_INDEX_INPUT_CHARS:
        content = content[:MAX_INDEX_INPUT_CHARS]
    summary = await llm.complete(
        [{"role": "user", "content": FILE_SUMMARY_PROMPT.format(content=content)}],
        model=model,
    )
    return summary.strip()


def assemble_collection_index(
    collection_name: str,
    collection_description: str,
    files: Sequence[tuple[str, str | None]],
) -> str:
    parts = [f"# {collection_name.strip() or 'Knowledge base'}"]
    if collection_description.strip():
        parts.append(collection_description.strip())
    parts.append("## Files")
    for filename, summary in sorted(files, key=lambda item: item[0].casefold()):
        parts.append(f"### {filename}\n\n{summary or 'No summary available.'}")
    return "\n\n".join(parts)
