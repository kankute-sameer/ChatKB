from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

from app.core.citations import Citations, KbSource
from app.features.kb.retrieve import ChunkHit
from app.features.kb.tools import KbSearchTool
from app.tests.fakes import FakeEmbedder


def test_kb_source_shapes() -> None:
    source = KbSource(
        file_id="file_1",
        filename="resume.pdf",
        page=3,
        anchor="page-3-block-2",
        bbox=[0.1, 0.2, 0.8, 0.3],
        collection_id="col_1",
        snippet="Relevant experience",
    )
    part = source.to_source_part("abc12345")
    assert part["type"] == "source-document"
    assert part["page"] == 3
    assert part["bbox"] == [0.1, 0.2, 0.8, 0.3]
    assert source.to_tool_result("abc12345") == {
        "cite_id": "abc12345",
        "filename": "resume.pdf",
        "page": 3,
        "snippet": "Relevant experience",
    }


@asynccontextmanager
async def _session() -> AsyncIterator[Any]:
    yield object()


class _SessionFactory:
    def __call__(self) -> Any:
        return _session()


@pytest.mark.asyncio
async def test_kb_search_self_guards_without_collections() -> None:
    tool = KbSearchTool(
        FakeEmbedder(),
        _SessionFactory(),  # type: ignore[arg-type]
    )
    result = await tool.run({"query": "skills"}, Citations())
    assert json.loads(result.content) == {
        "note": "no knowledge base is attached to this agent"
    }
    assert result.source_parts == []


@pytest.mark.asyncio
async def test_kb_search_mints_document_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    async def fake_search(
        query: str,
        collection_ids: list[str],
        **kwargs: object,
    ) -> list[ChunkHit]:
        seen["query"] = query
        seen["collection_ids"] = collection_ids
        return [
            ChunkHit(
                chunk_id="chunk_1",
                file_id="file_1",
                collection_id="col_1",
                text="A " * 150,
                section_header="Experience",
                page=4,
                anchor="block-7",
                bbox=[0.1, 0.2, 0.9, 0.4],
                filename="resume.pdf",
                score=0.02,
            )
        ]

    monkeypatch.setattr("app.features.kb.tools.hybrid_search", fake_search)
    tool = KbSearchTool(
        FakeEmbedder(),
        _SessionFactory(),  # type: ignore[arg-type]
        ["col_1"],
    )
    citations = Citations()
    result = await tool.run({"query": "experience"}, citations)
    payload = json.loads(result.content)

    assert seen == {"query": "experience", "collection_ids": ["col_1"]}
    assert payload[0]["filename"] == "resume.pdf"
    assert payload[0]["cite_id"] in citations.known_ids()
    assert result.source_parts[0]["type"] == "source-document"
    assert result.source_parts[0]["collectionId"] == "col_1"
