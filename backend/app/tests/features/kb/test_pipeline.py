from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from PIL import Image
from sqlalchemy import select

from app.core.ids import new_id
from app.core.tracing import NullTracer, set_tracer
from app.features.kb.ingestion.extract import Block, ExtractedImage, ProseExtraction
from app.features.kb.ingestion.pipeline import run_ingestion
from app.features.kb.models import Collection, KbChunk, KbFile
from app.tests.fakes import FakeEmbedder, FakeLLM, FakeStorage
from app.tests.tracing import RecordingTracer


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

    def boom(
        _path: Path,
        _mime_type: str,
        **_kwargs: object,
    ) -> ProseExtraction:
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
    tracer = RecordingTracer()

    def fake_extract(
        _path: Path,
        _mime_type: str,
        **_kwargs: object,
    ) -> ProseExtraction:
        return ProseExtraction(
            "prose",
            [
                _block("Intro", block_type="section_header", is_heading=True),
                _block("Hello world.", anchor="p1-2"),
            ],
            1,
            [
                ExtractedImage(
                    image=Image.new("RGB", (200, 100)),
                    insert_at=1,
                    page=1,
                    anchor="p1-image",
                    bbox=[0.2, 0.3, 0.8, 0.7],
                )
            ],
        )

    monkeypatch.setattr("app.features.kb.ingestion.pipeline.extract", fake_extract)

    set_tracer(tracer)
    try:
        await run_ingestion(
            file_id=file_id,
            file_path=pdf_path,
            session_factory=app.state.session_factory,
            llm=fake_llm,
            embedder=embedder,
            storage=storage,
            owner_id="alice",
            ingestion_model="test-model",
            image_describer=fake_llm,
        )
    finally:
        set_tracer(NullTracer())

    async with app.state.session_factory() as session:
        row = await session.get(KbFile, file_id)
        assert row is not None
        assert row.status == "ready"
        assert row.s3_key == f"alice/{file_id}.pdf"
        assert row.error is None
        assert row.page_count == 1
        assert row.content_md is not None
        assert "## Intro" in row.content_md
        assert "*[Image: A test image.]*" in row.content_md
        assert row.summary_md == fake_llm.title
        collection = await session.get(Collection, collection_id)
        assert collection is not None
        assert collection.index_md is not None
        assert "### spec.pdf" in collection.index_md
        assert fake_llm.title in collection.index_md
        result = await session.execute(
            select(KbChunk)
            .where(KbChunk.file_id == file_id)
            .order_by(KbChunk.chunk_index)
        )
        chunks = list(result.scalars().all())
        assert len(chunks) == 2
        assert chunks[0].collection_id == collection_id
        assert chunks[0].text == "Intro\n\nA test image."
        assert chunks[0].block_type == "image"
        assert chunks[0].bbox == [0.2, 0.3, 0.8, 0.7]
        assert chunks[1].text == "Intro\n\nHello world."
        assert chunks[0].section_header == "Intro"
        assert chunks[0].anchor == "p1-image"
        assert chunks[1].anchor == "p1-2"
        assert len(chunks[0].embedding) == 1536
    assert embedder.texts == [
        "Intro\n\nA test image.",
        "Intro\n\nHello world.",
    ]
    assert storage.puts == [
        (f"alice/{file_id}.pdf", b"%PDF-1.4", "application/pdf")
    ]
    ingestion = [
        item for item in tracer.observations if item.name == "kb.ingestion"
    ]
    assert len(ingestion) == 1
    assert ingestion[0].session_id == collection_id
    assert ingestion[0].user_id == "alice"
    assert {
        "store",
        "extract",
        "describe_images",
        "chunk",
        "index_md",
        "embed",
    }.issubset({item.name for item in tracer.observations})
