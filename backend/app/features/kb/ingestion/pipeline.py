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
from app.features.kb.ingestion.assemble import assemble_content, generate_index
from app.features.kb.ingestion.chunk import chunk_blocks
from app.features.kb.ingestion.embed import Embedder
from app.features.kb.ingestion.extract import extract_pdf
from app.features.kb.models import KbChunk, KbFile
from app.features.kb.repository import KbRepository

logger = logging.getLogger(__name__)


async def run_ingestion(
    *,
    file_id: str,
    pdf_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    llm: LLM,
    embedder: Embedder,
    storage: Storage,
    owner_id: str,
    ingestion_model: str,
    log: AppLogger | None = None,
) -> None:
    log = log.child("ingest") if log is not None else get_logger("chatkb.kb.ingest")
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
        try:
            await _ingest(
                session,
                repo,
                row,
                pdf_path,
                llm,
                embedder,
                storage,
                owner_id,
                ingestion_model,
                log,
            )
        except Exception as exc:
            log.exception("ingestion failed for %s", file_id)
            await session.rollback()
            failed = await repo.get_file(file_id)
            if failed is not None:
                failed.status = "failed"
                failed.error = str(exc)
                failed.updated_at = datetime.now(UTC)
                await session.commit()
        finally:
            pdf_path.unlink(missing_ok=True)


async def _ingest(
    session: AsyncSession,
    repo: KbRepository,
    row: KbFile,
    pdf_path: Path,
    llm: LLM,
    embedder: Embedder,
    storage: Storage,
    owner_id: str,
    ingestion_model: str,
    log: AppLogger,
) -> None:
    s3_key = f"{owner_id}/{row.id}.pdf"
    log.info("uploading %s to object storage", row.filename)
    pdf_bytes = await asyncio.to_thread(pdf_path.read_bytes)
    await storage.put(s3_key, pdf_bytes, "application/pdf")
    row.s3_key = s3_key
    row.updated_at = datetime.now(UTC)
    await session.commit()

    log.info("extracting %s", row.filename)
    blocks, page_count = await asyncio.to_thread(extract_pdf, pdf_path)
    content_md = assemble_content(blocks)
    index_md = await generate_index(content_md, llm, ingestion_model)
    chunks = chunk_blocks(blocks)
    embeddings = await embedder.embed([chunk.text for chunk in chunks])
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
            embedding=embedding,
            created_at=now,
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]
    await repo.replace_chunks(row.id, rows)
    row.content_md = content_md
    row.index_md = index_md
    row.page_count = page_count
    row.status = "ready"
    row.error = None
    row.updated_at = now
    await session.commit()
    log.info("ready %s (%s chunks)", row.id, len(rows))
