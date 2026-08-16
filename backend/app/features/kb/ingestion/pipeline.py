from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.ids import new_id
from app.core.llm.types import LLM
from app.core.log import AppLogger, get_logger
from app.core.storage import Storage
from app.core.tracing import get_tracer
from app.features.kb.db import KbRepository
from app.features.kb.ingestion.assemble import (
    assemble_collection_index,
    assemble_content,
    generate_file_summary,
)
from app.features.kb.ingestion.chunk import chunk_blocks
from app.features.kb.ingestion.describe_image import (
    ImageDescriber,
    insert_image_descriptions,
)
from app.features.kb.ingestion.embed import Embedder
from app.features.kb.ingestion.extract import ProseExtraction, extract
from app.features.kb.ingestion.table import prepare_table
from app.features.kb.models import KbChunk, KbFile

logger = logging.getLogger(__name__)


async def run_ingestion(
    *,
    file_id: str,
    file_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    llm: LLM,
    embedder: Embedder,
    storage: Storage,
    owner_id: str,
    ingestion_model: str,
    log: AppLogger | None = None,
    image_describer: ImageDescriber | None = None,
    image_min_dimension_px: int = 64,
    max_concurrent_image_descriptions: int = 4,
) -> None:
    log = log.child("ingest") if log is not None else get_logger("chatkb.kb.ingest")
    tracer = get_tracer()
    async with session_factory() as session:
        repo = KbRepository(session)
        row = await repo.get_file(file_id)
        if row is None:
            log.warning("ingestion skipped; file %s not found", file_id)
            return
        row.status = "processing"
        row.error = None
        row.updated_at = datetime.now(UTC)
        await session.commit()
        metadata = {
            "file_id": row.id,
            "filename": row.filename,
            "format": Path(row.filename).suffix.lower().lstrip("."),
            "collection_id": row.collection_id,
        }
        with tracer.trace(
            "kb.ingestion",
            input={"file_id": row.id, "filename": row.filename},
            session_id=row.collection_id,
            user_id=owner_id,
            metadata=metadata,
        ) as trace:
            outcome: dict[str, object] = {"status": "processing"}
            try:
                page_count, chunk_count = await _ingest(
                    session,
                    repo,
                    row,
                    file_path,
                    llm,
                    embedder,
                    storage,
                    owner_id,
                    ingestion_model,
                    log,
                    image_describer,
                    image_min_dimension_px,
                    max_concurrent_image_descriptions,
                )
                outcome = {
                    "status": "ready",
                    "page_count": page_count,
                    "chunk_count": chunk_count,
                }
            except Exception as exc:
                outcome = {"status": "failed", "error": str(exc)}
                log.exception("ingestion failed for %s", file_id)
                await session.rollback()
                failed = await repo.get_file(file_id)
                if failed is not None:
                    failed.status = "failed"
                    failed.error = str(exc)
                    failed.updated_at = datetime.now(UTC)
                    await session.commit()
            finally:
                trace.update(output=outcome, metadata={**metadata, **outcome})
                file_path.unlink(missing_ok=True)
        tracer.schedule_flush()


async def _ingest(
    session: AsyncSession,
    repo: KbRepository,
    row: KbFile,
    file_path: Path,
    llm: LLM,
    embedder: Embedder,
    storage: Storage,
    owner_id: str,
    ingestion_model: str,
    log: AppLogger,
    image_describer: ImageDescriber | None = None,
    image_min_dimension_px: int = 64,
    max_concurrent_image_descriptions: int = 4,
) -> tuple[int | None, int]:
    tracer = get_tracer()
    suffix = Path(row.filename).suffix.lower()
    s3_key = f"{owner_id}/{row.id}{suffix}"
    log.info("uploading %s to object storage", row.filename)
    with tracer.span(
        "store",
        input={"file_id": row.id, "filename": row.filename},
    ) as store_span:
        file_bytes = await asyncio.to_thread(file_path.read_bytes)
        await storage.put(s3_key, file_bytes, row.mime_type)
        store_span.update(output={"s3_key": s3_key, "bytes": len(file_bytes)})
    row.s3_key = s3_key
    row.updated_at = datetime.now(UTC)
    await session.commit()

    log.info("extracting %s", row.filename)
    with tracer.span(
        "extract",
        input={"filename": row.filename, "mime_type": row.mime_type},
    ) as extract_span:
        extraction = await asyncio.to_thread(
            extract,
            file_path,
            row.mime_type,
            image_min_dimension_px=image_min_dimension_px,
        )
        extract_span.update(
            output={
                "kind": extraction.kind,
                "page_count": (
                    extraction.page_count
                    if isinstance(extraction, ProseExtraction)
                    else None
                ),
                "image_count": (
                    len(extraction.images)
                    if isinstance(extraction, ProseExtraction)
                    else 0
                ),
            }
        )
    if isinstance(extraction, ProseExtraction):
        blocks = extraction.blocks
        with tracer.span(
            "describe_images",
            input={"candidate_count": len(extraction.images)},
        ) as image_span:
            if extraction.images and image_describer is not None:
                blocks = await insert_image_descriptions(
                    blocks,
                    extraction.images,
                    image_describer,
                    max_concurrency=max_concurrent_image_descriptions,
                )
            image_span.update(
                output={
                    "candidate_count": len(extraction.images),
                    "described_count": sum(
                        block["block_type"] == "image" for block in blocks
                    ),
                }
            )
        content_md = assemble_content(blocks)
        with tracer.span("chunk", input={"block_count": len(blocks)}) as chunk_span:
            chunks = chunk_blocks(blocks)
            chunk_span.update(output={"chunk_count": len(chunks)})
        page_count = extraction.page_count
    else:
        with tracer.span(
            "describe_images",
            input={"candidate_count": 0},
        ) as image_span:
            image_span.update(output={"candidate_count": 0, "described_count": 0})
        with tracer.span("chunk", input={"kind": "table"}) as chunk_span:
            content_md, chunks = await prepare_table(
                extraction,
                filename=row.filename,
                llm=llm,
                model=ingestion_model,
            )
            chunk_span.update(output={"chunk_count": len(chunks)})
        page_count = None
    with tracer.span(
        "index_md",
        input={"filename": row.filename, "chunk_count": len(chunks)},
    ) as index_span:
        file_summary = await generate_file_summary(content_md, llm, ingestion_model)
        index_span.update(output={"summary": file_summary})
    with tracer.span("embed", input={"chunk_count": len(chunks)}) as embed_span:
        embeddings = await embedder.embed([chunk.text for chunk in chunks])
        embed_span.update(output={"embedding_count": len(embeddings)})
    now = datetime.now(UTC)
    rows = [
        KbChunk(
            id=new_id("chunk"),
            file_id=row.id,
            collection_id=row.collection_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            section_header=chunk.section_header,
            page=chunk.page,
            anchor=chunk.anchor,
            bbox=chunk.bbox,
            block_type=chunk.block_type,
            chunk_metadata=chunk.metadata,
            embedding=embedding,
            created_at=now,
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]
    collection = await repo.get_collection_for_update(row.collection_id)
    if collection is None:
        raise RuntimeError("Collection not found while finalizing ingestion")
    await repo.replace_chunks(row.id, rows)
    row.content_md = content_md
    row.summary_md = file_summary
    row.page_count = page_count
    row.status = "ready"
    row.error = None
    row.updated_at = now
    ready_files = await repo.list_ready_files(row.collection_id)
    collection.index_md = assemble_collection_index(
        collection.name,
        collection.description,
        [(kb_file.filename, kb_file.summary_md) for kb_file in ready_files],
    )
    collection.updated_at = now
    await session.commit()
    log.info("ready %s (%s chunks)", row.id, len(rows))
    return page_count, len(rows)
