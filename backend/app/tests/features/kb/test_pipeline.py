from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from sqlalchemy import select

from app.core.ids import new_id
from app.features.kb.ingestion.extract import Block, ProseExtraction
from app.features.kb.ingestion.pipeline import run_ingestion
from app.features.kb.models import Collection, KbChunk, KbFile
from app.tests.fakes import FakeEmbedder, FakeLLM, FakeStorage


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
        "bbox": [0.1, 0.2, 0.9, 0.3],
        "is_heading": is_heading,
    }


async def _seed_processing_file(app: FastAPI) -> tuple[str, str]:
    collection_id = new_id("col")
    file_id = new_id("file")
    now = datetime.now(UTC)
    async with app.state.session_factory() as session:
        session.add(
            Collection(
                id=collection_id,
                owner_id="alice",
                name="Docs",
                description="",
                visibility="personal",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            KbFile(
                id=file_id,
                collection_id=collection_id,
                filename="spec.pdf",
                size_bytes=12,
                mime_type="application/pdf",
                status="processing",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    return collection_id, file_id


@pytest.mark.asyncio
async def test_pipeline_extract_failure_marks_file_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, app: FastAPI
) -> None:
    _, file_id = await _seed_processing_file(app)
    pdf_path = tmp_path / "spec.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    def boom(_path: Path, _mime_type: str) -> ProseExtraction:
        raise RuntimeError("docling exploded")

    monkeypatch.setattr("app.features.kb.ingestion.pipeline.extract", boom)
    storage = FakeStorage()

    await run_ingestion(
        file_id=file_id,
        file_path=pdf_path,
        session_factory=app.state.session_factory,
        llm=app.state.llm,
        embedder=FakeEmbedder(),
        storage=storage,
        owner_id="alice",
        ingestion_model="test-model",
    )

    async with app.state.session_factory() as session:
        row = await session.get(KbFile, file_id)
        assert row is not None
        assert row.status == "failed"
        assert row.error is not None
        assert "docling exploded" in row.error
    assert not pdf_path.exists()
    assert storage.puts[0][0] == f"alice/{file_id}.pdf"


@pytest.mark.asyncio
async def test_pipeline_persists_chunks_and_marks_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, app: FastAPI, fake_llm: FakeLLM
) -> None:
    collection_id, file_id = await _seed_processing_file(app)
    pdf_path = tmp_path / "spec.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    embedder = FakeEmbedder()
    storage = FakeStorage()

    def fake_extract(_path: Path, _mime_type: str) -> ProseExtraction:
        return ProseExtraction(
            "prose",
            [
                _block("Intro", block_type="section_header", is_heading=True),
                _block("Hello world.", anchor="p1-2"),
            ],
            1,
        )

    monkeypatch.setattr("app.features.kb.ingestion.pipeline.extract", fake_extract)

    await run_ingestion(
        file_id=file_id,
        file_path=pdf_path,
        session_factory=app.state.session_factory,
        llm=fake_llm,
        embedder=embedder,
        storage=storage,
        owner_id="alice",
        ingestion_model="test-model",
    )

    async with app.state.session_factory() as session:
        row = await session.get(KbFile, file_id)
        assert row is not None
        assert row.status == "ready"
        assert row.s3_key == f"alice/{file_id}.pdf"
        assert row.error is None
        assert row.page_count == 1
        assert row.content_md is not None
        assert "## Intro" in row.content_md
        assert row.index_md == fake_llm.title
        result = await session.execute(
            select(KbChunk)
            .where(KbChunk.file_id == file_id)
            .order_by(KbChunk.chunk_index)
        )
        chunks = list(result.scalars().all())
        assert len(chunks) == 1
        assert chunks[0].collection_id == collection_id
        assert chunks[0].text == "Intro\n\nHello world."
        assert chunks[0].section_header == "Intro"
        assert chunks[0].anchor == "p1-2"
        assert len(chunks[0].embedding) == 1536
    assert embedder.texts == ["Intro\n\nHello world."]
    assert storage.puts == [
        (f"alice/{file_id}.pdf", b"%PDF-1.4", "application/pdf")
    ]
