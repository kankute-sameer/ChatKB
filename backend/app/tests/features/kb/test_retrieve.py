from __future__ import annotations

from typing import Any

import pytest

from app.features.kb.ingestion.embed import QUERY_TASK_TYPE
from app.features.kb.retrieve import ChunkHit, hybrid_search, reciprocal_rank_fusion
from app.tests.fakes import FakeEmbedder


def _hit(chunk_id: str, collection_id: str = "col_one") -> ChunkHit:
    return ChunkHit(
        chunk_id=chunk_id,
        file_id=f"file_{chunk_id}",
        collection_id=collection_id,
        text=f"text {chunk_id}",
        section_header=None,
        page=1,
        anchor=f"anchor-{chunk_id}",
        bbox=[0.1, 0.2, 0.3, 0.4],
        filename="document.pdf",
        mime_type="application/pdf",
        score=0,
    )


def test_rrf_combines_rankings_and_rewards_overlap() -> None:
    fused = reciprocal_rank_fusion(
        [
            [_hit("a"), _hit("b")],
            [_hit("b"), _hit("c")],
        ],
        limit=3,
    )
    assert [hit.chunk_id for hit in fused] == ["b", "a", "c"]
    assert fused[0].score == pytest.approx(1 / 62 + 1 / 61)
    assert fused[1].score == pytest.approx(1 / 61)


class _Result:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> list[dict[str, object]]:
        return self._rows


class _Db:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, statement: Any, params: dict[str, object]) -> _Result:
        sql = str(statement)
        self.calls.append((sql, params))
        chunk_id = "vector" if "<=>" in sql else "lexical"
        return _Result(
            [
                {
                    "chunk_id": chunk_id,
                    "file_id": f"file_{chunk_id}",
                    "collection_id": "col_allowed",
                    "text": chunk_id,
                    "section_header": None,
                    "page": 2,
                    "anchor": chunk_id,
                    "bbox": [0, 0, 1, 1],
                    "filename": "resume.pdf",
                    "mime_type": "application/pdf",
                }
            ]
        )


@pytest.mark.asyncio
async def test_hybrid_search_is_scoped_and_uses_query_embedding() -> None:
    db = _Db()
    embedder = FakeEmbedder()
    hits = await hybrid_search(
        "Sameer",
        ["col_allowed"],
        db=db,  # type: ignore[arg-type]
        embedder=embedder,
    )

    assert {hit.collection_id for hit in hits} == {"col_allowed"}
    assert embedder.task_types == [QUERY_TASK_TYPE]
    assert len(db.calls) == 2
    assert all(call[1]["collection_ids"] == ["col_allowed"] for call in db.calls)
    vector_params = next(params for sql, params in db.calls if "<=>" in sql)
    assert isinstance(vector_params["qvec"], list)
    lexical_sql = next(sql for sql, _ in db.calls if "text_tsv" in sql)
    assert "websearch_to_tsquery('simple'" in lexical_sql


@pytest.mark.asyncio
async def test_empty_collection_ids_skips_embedding_and_database() -> None:
    db = _Db()
    embedder = FakeEmbedder()
    assert (
        await hybrid_search(
            "query",
            [],
            db=db,  # type: ignore[arg-type]
            embedder=embedder,
        )
        == []
    )
    assert db.calls == []
    assert embedder.texts == []
