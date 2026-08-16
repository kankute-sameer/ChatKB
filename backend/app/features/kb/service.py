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
from app.features.kb.db import KbRepository
from app.features.kb.ingestion.assemble import assemble_collection_index
from app.features.kb.ingestion.describe_image import ImageDescriber
from app.features.kb.ingestion.embed import Embedder
from app.features.kb.ingestion.pipeline import run_ingestion
from app.features.kb.models import Collection, KbFile
from app.features.kb.retrieve import hybrid_search
from app.features.kb.schemas import (
    CollectionCreateRequest,
    CollectionIndexResponse,
    CollectionResponse,
    KbFileResponse,
    KbFileSummary,
    KbFileViewResponse,
    ObservabilityQueryHit,
    ObservabilityQueryResponse,
)

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
SUPPORTED_MIME_TYPES: dict[str, frozenset[str]] = {
    ".pdf": frozenset({"application/pdf"}),
    ".docx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        }
    ),
    ".md": frozenset({"text/markdown", "text/plain"}),
    ".txt": frozenset({"text/plain"}),
    ".csv": frozenset({"text/csv", "application/csv", "text/plain"}),
    ".tsv": frozenset({"text/tab-separated-values", "text/plain"}),
    ".json": frozenset({"application/json", "text/json", "text/plain"}),
}
CANONICAL_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".json": "application/json",
}


class KbService:
    def __init__(
        self,
        session: AsyncSession,
        session_factory: async_sessionmaker[AsyncSession],
        llm: LLM,
        embedder: Embedder,
        image_describer: ImageDescriber,
        storage: Storage,
        settings: Settings | None = None,
        log: AppLogger | None = None,
    ) -> None:
        self.session = session
        self.session_factory = session_factory
        self.llm = llm
        self.embedder = embedder
        self.image_describer = image_describer
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
            index_md=assemble_collection_index(
                body.name,
                body.description,
                [],
            ),
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

    async def get_collection_index(
        self,
        owner_id: str,
        collection_id: str,
    ) -> CollectionIndexResponse:
        collection = await self._owned_collection(collection_id, owner_id)
        return CollectionIndexResponse(
            collection_id=collection.id,
            content=collection.index_md
            or assemble_collection_index(
                collection.name,
                collection.description,
                [],
            ),
        )

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
        filename = upload.filename or "upload"
        extension = Path(filename).suffix.lower()
        mime_type = _validate_upload(
            filename,
            upload.content_type or "application/octet-stream",
            data,
        )

        fd, tmp_name = tempfile.mkstemp(suffix=extension)
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
                file_path=tmp_path,
                session_factory=self.session_factory,
                llm=self.llm,
                embedder=self.embedder,
                storage=self.storage,
                owner_id=owner_id,
                ingestion_model=self.settings.ingestion_model,
                log=self.log,
                image_describer=self.image_describer,
                image_min_dimension_px=self.settings.image_min_dimension_px,
                max_concurrent_image_descriptions=(
                    self.settings.max_concurrent_image_descriptions
                ),
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

    async def query_collection_for_observability(
        self,
        owner_id: str,
        collection_id: str,
        query: str,
        limit: int,
    ) -> ObservabilityQueryResponse:
        if owner_id != "alice":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Observability is only available to Alice",
            )
        await self._owned_collection(collection_id, owner_id)
        normalized_query = query.strip()
        if not normalized_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query cannot be empty",
            )
        hits = await hybrid_search(
            normalized_query,
            [collection_id],
            db=self.session,
            embedder=self.embedder,
            k=limit,
            session_factory=self.session_factory,
        )
        return ObservabilityQueryResponse(
            query=normalized_query,
            results=[
                ObservabilityQueryHit(
                    chunk_id=hit.chunk_id,
                    file_id=hit.file_id,
                    filename=hit.filename,
                    mime_type=hit.mime_type,
                    text=hit.text,
                    section_header=hit.section_header,
                    page=hit.page,
                    anchor=hit.anchor,
                    score=hit.score,
                )
                for hit in hits
            ],
        )

    async def delete_file(
        self, owner_id: str, collection_id: str, file_id: str
    ) -> None:
        await self._owned_collection(collection_id, owner_id)
        collection = await self.repo.get_collection_for_update(collection_id)
        if collection is None or collection.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found",
            )
        kb_file = await self.repo.get_file_in_collection(file_id, collection_id)
        if kb_file is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )
        if kb_file.s3_key:
            await self.storage.delete(kb_file.s3_key)
        await self.repo.delete_file(kb_file)
        ready_files = await self.repo.list_ready_files(collection_id)
        collection.index_md = assemble_collection_index(
            collection.name,
            collection.description,
            [(row.filename, row.summary_md) for row in ready_files],
        )
        collection.updated_at = datetime.now(UTC)
        await self.session.commit()

    async def content_url(self, owner_id: str, file_id: str) -> str:
        kb_file = await self._owned_file(owner_id, file_id)
        if not kb_file.s3_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File content is not available",
            )
        return await self.storage.presigned_get_url(kb_file.s3_key, expires_in=300)

    async def view_file(
        self,
        owner_id: str,
        file_id: str,
    ) -> KbFileViewResponse:
        kb_file = await self._owned_file(owner_id, file_id)
        if kb_file.mime_type == "application/pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF files use the document viewer",
            )
        suffix = Path(kb_file.filename).suffix.lower()
        if suffix == ".docx":
            content = kb_file.content_md or ""
        else:
            if not kb_file.s3_key:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File content is not available",
                )
            data = await self.storage.get(kb_file.s3_key)
            try:
                content = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                content = kb_file.content_md or ""
        return KbFileViewResponse(
            filename=kb_file.filename,
            mime_type=kb_file.mime_type,
            content=content,
            page_count=kb_file.page_count,
        )

    async def _owned_file(self, owner_id: str, file_id: str) -> KbFile:
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
        return kb_file

    async def _owned_collection(self, collection_id: str, owner_id: str) -> Collection:
        collection = await self.repo.get_owned_collection(collection_id, owner_id)
        if collection is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found",
            )
        return collection


def _validate_upload(filename: str, mime_type: str, data: bytes) -> str:
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file"
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File exceeds 50 MB limit",
        )
    extension = Path(filename).suffix.lower()
    allowed = SUPPORTED_MIME_TYPES.get(extension)
    if allowed is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Supported file types: PDF, DOCX, TXT, MD, CSV, TSV, and JSON"
            ),
        )
    if mime_type not in allowed and mime_type != "application/octet-stream":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File content type does not match {extension}",
        )
    if extension == ".pdf" and not data.startswith(PDF_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PDF file",
        )
    if extension == ".docx" and not data.startswith(b"PK"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid DOCX file",
        )
    if extension in {".md", ".txt", ".csv", ".tsv", ".json"}:
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text files must be UTF-8 encoded",
            ) from exc
    return (
        CANONICAL_MIME_TYPES[extension]
        if mime_type == "application/octet-stream"
        else mime_type
    )


def _log_ingest_task(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.exception("ingestion task crashed", exc_info=exc)
