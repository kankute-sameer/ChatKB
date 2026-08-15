from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.ids import new_id
from app.core.llm.types import LLM
from app.core.log import AppLogger, get_logger
from app.core.storage import Storage
from app.features.kb.ingestion.embed import Embedder
from app.features.kb.ingestion.pipeline import run_ingestion
from app.features.kb.models import Collection, KbFile
from app.features.kb.repository import KbRepository
from app.features.kb.schemas import (
    CollectionCreateRequest,
    CollectionResponse,
    KbFileResponse,
    KbFileSummary,
)

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class KbService:
    def __init__(
        self,
        session: AsyncSession,
        session_factory: async_sessionmaker[AsyncSession],
        llm: LLM,
        embedder: Embedder,
        storage: Storage,
        settings: Settings | None = None,
        log: AppLogger | None = None,
    ) -> None:
        self.session = session
        self.session_factory = session_factory
        self.llm = llm
        self.embedder = embedder
        self.storage = storage
        self.settings = settings or get_settings()
        self.log = log if log is not None else get_logger("chatkb.kb")
        self.repo = KbRepository(session)

    async def create_collection(
        self, owner_id: str, body: CollectionCreateRequest
    ) -> CollectionResponse:
        now = datetime.now(UTC)
        collection = Collection(
            id=new_id("col"),
            owner_id=owner_id,
            name=body.name.strip(),
            description=body.description.strip(),
            visibility=body.visibility,
            created_at=now,
            updated_at=now,
        )
        await self.repo.create_collection(collection)
        await self.session.commit()
        await self.session.refresh(collection)
        return CollectionResponse.model_validate(collection)

    async def list_collections(self, owner_id: str) -> list[CollectionResponse]:
        rows = await self.repo.list_collections(owner_id)
        return [CollectionResponse.model_validate(row) for row in rows]

    async def get_collection(
        self, owner_id: str, collection_id: str
    ) -> CollectionResponse:
        collection = await self._owned_collection(collection_id, owner_id)
        return CollectionResponse.model_validate(collection)

    async def delete_collection(self, owner_id: str, collection_id: str) -> None:
        collection = await self._owned_collection(collection_id, owner_id)
        for kb_file in collection.files:
            if kb_file.s3_key:
                await self.storage.delete(kb_file.s3_key)
        await self.repo.delete_collection(collection)
        await self.session.commit()

    async def upload_file(
        self, owner_id: str, collection_id: str, upload: UploadFile
    ) -> KbFileResponse:
        await self._owned_collection(collection_id, owner_id)
        data = await upload.read()
        filename = upload.filename or "upload.pdf"
        mime_type = upload.content_type or "application/pdf"
        _validate_pdf(filename, mime_type, data)

        fd, tmp_name = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        tmp_path = Path(tmp_name)
        tmp_path.write_bytes(data)

        now = datetime.now(UTC)
        kb_file = KbFile(
            id=new_id("file"),
            collection_id=collection_id,
            filename=filename,
            size_bytes=len(data),
            mime_type=mime_type,
            status="processing",
            error=None,
            created_at=now,
            updated_at=now,
        )
        await self.repo.create_file(kb_file)
        await self.session.commit()
        await self.session.refresh(kb_file)

        task = asyncio.create_task(
            run_ingestion(
                file_id=kb_file.id,
                pdf_path=tmp_path,
                session_factory=self.session_factory,
                llm=self.llm,
                embedder=self.embedder,
                storage=self.storage,
                owner_id=owner_id,
                ingestion_model=self.settings.ingestion_model,
                log=self.log,
            ),
            name=f"ingest:{kb_file.id}",
        )
        task.add_done_callback(_log_ingest_task)

        return KbFileResponse.model_validate(kb_file)

    async def list_files(
        self, owner_id: str, collection_id: str
    ) -> list[KbFileSummary]:
        await self._owned_collection(collection_id, owner_id)
        rows = await self.repo.list_files(collection_id)
        return [KbFileSummary.model_validate(row) for row in rows]

    async def get_file(
        self, owner_id: str, collection_id: str, file_id: str
    ) -> KbFileResponse:
        await self._owned_collection(collection_id, owner_id)
        kb_file = await self.repo.get_file_in_collection(file_id, collection_id)
        if kb_file is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )
        return KbFileResponse.model_validate(kb_file)

    async def delete_file(
        self, owner_id: str, collection_id: str, file_id: str
    ) -> None:
        await self._owned_collection(collection_id, owner_id)
        kb_file = await self.repo.get_file_in_collection(file_id, collection_id)
        if kb_file is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )
        if kb_file.s3_key:
            await self.storage.delete(kb_file.s3_key)
        await self.repo.delete_file(kb_file)
        await self.session.commit()

    async def content_url(self, owner_id: str, file_id: str) -> str:
        kb_file = await self.repo.get_file(file_id)
        if kb_file is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )
        collection = await self.repo.get_collection(kb_file.collection_id)
        if collection is None or collection.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this file",
            )
        if not kb_file.s3_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File content is not available",
            )
        return await self.storage.presigned_get_url(kb_file.s3_key, expires_in=300)

    async def _owned_collection(self, collection_id: str, owner_id: str) -> Collection:
        collection = await self.repo.get_owned_collection(collection_id, owner_id)
        if collection is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found",
            )
        return collection


def _validate_pdf(filename: str, mime_type: str, data: bytes) -> None:
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file"
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File exceeds 50 MB limit",
        )
    looks_pdf = filename.lower().endswith(".pdf") or mime_type == "application/pdf"
    if not looks_pdf or not data.startswith(PDF_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported",
        )


def _log_ingest_task(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.exception("ingestion task crashed", exc_info=exc)
