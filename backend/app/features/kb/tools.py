from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.citations import Citations, KbSource
from app.core.tools.protocol import ToolResult
from app.features.kb.ingestion.embed import Embedder
from app.features.kb.retrieve import hybrid_search

SNIPPET_LIMIT = 200
RESULT_CHAR_CAP = 4000


class KbSearchTool:
    name = "kb_search"
    description = (
        "Search the attached knowledge base documents for relevant information. "
        "Use when the answer may be in the user's uploaded documents."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        embedder: Embedder,
        session_factory: async_sessionmaker[AsyncSession],
        collection_ids: list[str] | None = None,
    ) -> None:
        self._embedder = embedder
        self._session_factory = session_factory
        self._collection_ids = list(collection_ids or [])

    def scoped(self, collection_ids: list[str]) -> KbSearchTool:
        return KbSearchTool(
            self._embedder,
            self._session_factory,
            collection_ids,
        )

    async def run(self, args: dict[str, Any], citations: Citations) -> ToolResult:
        if not self._collection_ids:
            return ToolResult(
                content=json.dumps(
                    {"note": "no knowledge base is attached to this agent"}
                )
            )

        query = str(args.get("query") or "").strip()
        if not query:
            return ToolResult(
                content=json.dumps({"error": "search failed: query is required"})
            )

        async with self._session_factory() as db:
            hits = await hybrid_search(
                query,
                self._collection_ids,
                db=db,
                embedder=self._embedder,
                k=5,
                session_factory=self._session_factory,
            )

        results: list[dict[str, object]] = []
        source_parts: list[dict[str, Any]] = []
        known = citations.known_ids()
        for hit in hits:
            source = KbSource(
                file_id=hit.file_id,
                filename=hit.filename,
                page=hit.page,
                anchor=hit.anchor,
                bbox=hit.bbox,
                collection_id=hit.collection_id,
                snippet=_snippet(hit.text),
            )
            cite_id = citations.add(source)
            results.append(source.to_tool_result(cite_id))
            if cite_id not in known:
                source_parts.append(source.to_source_part(cite_id))
                known.add(cite_id)

        return ToolResult(
            content=_capped_json(results),
            source_parts=source_parts,
        )


def _snippet(text: str) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= SNIPPET_LIMIT:
        return normalized
    return normalized[: SNIPPET_LIMIT - 1].rstrip() + "…"


def _capped_json(results: list[dict[str, object]]) -> str:
    encoded = json.dumps(results)
    while len(encoded) > RESULT_CHAR_CAP and results:
        results.pop()
        encoded = json.dumps(results)
    return encoded
