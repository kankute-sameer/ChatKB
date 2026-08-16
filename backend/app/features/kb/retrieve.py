from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.tracing import get_tracer
from app.features.kb.ingestion.embed import QUERY_TASK_TYPE, Embedder

SEARCH_LIMIT = 30
RRF_K = 60


@dataclass(frozen=True)
class ChunkHit:
    chunk_id: str
    file_id: str
    collection_id: str
    text: str
    section_header: str | None
    page: int | None
    anchor: str
    bbox: list[float] | None
    filename: str
    mime_type: str
    score: float


async def hybrid_search(
    query: str,
    collection_ids: list[str],
    *,
    db: AsyncSession,
    embedder: Embedder,
    k: int = 10,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> list[ChunkHit]:
    """Search selected collections and fuse semantic and lexical rankings."""
    if not collection_ids or k <= 0:
        return []

    tracer = get_tracer()
    with tracer.span(
        "retrieval",
        input={"query": query, "collection_ids": collection_ids, "limit": k},
        as_type="retriever",
    ) as retrieval:
        vectors = await embedder.embed([query], task_type=QUERY_TASK_TYPE)
        query_vector = vectors[0]

        async def vector_search() -> list[ChunkHit]:
            with tracer.span(
                "retrieval.vector",
                as_type="retriever",
            ) as vector_span:
                hits = await _vector_search(db, collection_ids, query_vector)
                vector_span.update(output=_trace_hits(hits))
                return hits

        async def lexical_search() -> list[ChunkHit]:
            with tracer.span(
                "retrieval.lexical",
                as_type="retriever",
            ) as lexical_span:
                if session_factory is None:
                    hits = await _lexical_search(db, collection_ids, query)
                else:
                    async with session_factory() as session:
                        hits = await _lexical_search(session, collection_ids, query)
                lexical_span.update(output=_trace_hits(hits))
                return hits

        # Independent sessions let PostgreSQL execute both halves concurrently.
        vector_hits, lexical_hits = await asyncio.gather(
            vector_search(),
            lexical_search(),
        )
        fused = reciprocal_rank_fusion([vector_hits, lexical_hits], limit=k)
        retrieval.update(
            output={
                "vector": _trace_hits(vector_hits),
                "lexical": _trace_hits(lexical_hits),
                "fused": _trace_hits(fused),
            }
        )
        return fused


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[ChunkHit]],
    *,
    limit: int,
) -> list[ChunkHit]:
    scores: dict[str, float] = {}
    hits: dict[str, ChunkHit] = {}
    for ranked in ranked_lists:
        seen: set[str] = set()
        for rank, hit in enumerate(ranked, start=1):
            if hit.chunk_id in seen:
                continue
            seen.add(hit.chunk_id)
            hits.setdefault(hit.chunk_id, hit)
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1 / (
                RRF_K + rank
            )

    # Equal weighting for now. Vector weighting may improve cross-lingual queries later.
    ordered = sorted(
        hits.values(),
        key=lambda hit: (-scores[hit.chunk_id], hit.chunk_id),
    )
    return [
        replace(hit, score=scores[hit.chunk_id])
        for hit in ordered[: max(0, limit)]
    ]


async def _vector_search(
    db: AsyncSession,
    collection_ids: list[str],
    query_vector: list[float],
) -> list[ChunkHit]:
    statement = text(
        """
        SELECT c.id AS chunk_id, c.file_id, c.collection_id, c.text,
               c.section_header, c.page, c.anchor, c.bbox, f.filename,
               f.mime_type,
               1 - (c.embedding <=> CAST(:qvec AS vector)) AS score
        FROM kb_chunks AS c
        JOIN kb_files AS f ON f.id = c.file_id
        WHERE c.collection_id IN :collection_ids
        ORDER BY c.embedding <=> CAST(:qvec AS vector)
        LIMIT :search_limit
        """
    ).bindparams(bindparam("collection_ids", expanding=True))
    rows = await db.execute(
        statement,
        {
            "collection_ids": collection_ids,
            "qvec": query_vector,
            "search_limit": SEARCH_LIMIT,
        },
    )
    return [_row_to_hit(row) for row in rows.mappings()]


async def _lexical_search(
    db: AsyncSession,
    collection_ids: list[str],
    query: str,
) -> list[ChunkHit]:
    statement = text(
        """
        SELECT c.id AS chunk_id, c.file_id, c.collection_id, c.text,
               c.section_header, c.page, c.anchor, c.bbox, f.filename,
               f.mime_type,
               ts_rank(
                   c.text_tsv,
                   websearch_to_tsquery('simple', :query)
               ) AS score
        FROM kb_chunks AS c
        JOIN kb_files AS f ON f.id = c.file_id
        WHERE c.collection_id IN :collection_ids
          AND c.text_tsv @@ websearch_to_tsquery('simple', :query)
        ORDER BY ts_rank(
            c.text_tsv,
            websearch_to_tsquery('simple', :query)
        ) DESC
        LIMIT :search_limit
        """
    ).bindparams(bindparam("collection_ids", expanding=True))
    rows = await db.execute(
        statement,
        {
            "collection_ids": collection_ids,
            "query": query,
            "search_limit": SEARCH_LIMIT,
        },
    )
    return [_row_to_hit(row) for row in rows.mappings()]


def _row_to_hit(row: Any) -> ChunkHit:
    bbox = row["bbox"]
    return ChunkHit(
        chunk_id=str(row["chunk_id"]),
        file_id=str(row["file_id"]),
        collection_id=str(row["collection_id"]),
        text=str(row["text"]),
        section_header=(
            str(row["section_header"]) if row["section_header"] is not None else None
        ),
        page=int(row["page"]) if row["page"] is not None else None,
        anchor=str(row["anchor"]),
        bbox=[float(value) for value in bbox] if bbox is not None else None,
        filename=str(row["filename"]),
        mime_type=str(row["mime_type"]),
        score=float(row.get("score") or 0.0),
    )


def _trace_hits(hits: Sequence[ChunkHit]) -> list[dict[str, object]]:
    return [
        {
            "chunk_id": hit.chunk_id,
            "file_id": hit.file_id,
            "filename": hit.filename,
            "section_header": hit.section_header,
            "page": hit.page,
            "score": round(hit.score, 6),
            "text": _trace_snippet(hit.text),
        }
        for hit in hits[:10]
    ]


def _trace_snippet(text: str, limit: int = 500) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"
