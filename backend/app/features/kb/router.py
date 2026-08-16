from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.deps import get_current_user, require_alice
from app.core.llm.types import LLM
from app.core.log import AppLogger, get_logger
from app.core.storage import Storage, get_storage
from app.features.agents.schemas import AgentResponse
from app.features.kb.ingestion.describe_image import ImageDescriber
from app.features.kb.ingestion.embed import Embedder
from app.features.kb.schemas import (
    CollectionAgentAttachRequest,
    CollectionCreateRequest,
    CollectionIndexResponse,
    CollectionResponse,
    KbFileResponse,
    KbFileSummary,
    KbFileViewResponse,
    ObservabilityQueryRequest,
    ObservabilityQueryResponse,
)
from app.features.kb.service import KbService

router = APIRouter(tags=["kb"])


def get_llm(request: Request) -> LLM:
    return request.app.state.llm  # type: ignore[no-any-return]


def get_embedder(request: Request) -> Embedder:
    return request.app.state.embedder  # type: ignore[no-any-return]


def get_image_describer(request: Request) -> ImageDescriber:
    return request.app.state.image_describer  # type: ignore[no-any-return]


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory  # type: ignore[no-any-return]


def get_log(request: Request) -> AppLogger:
    log = getattr(request.app.state, "log", None)
    if isinstance(log, AppLogger):
        return log
    return get_logger("chatkb")


def get_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
    llm: Annotated[LLM, Depends(get_llm)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    image_describer: Annotated[ImageDescriber, Depends(get_image_describer)],
    storage: Annotated[Storage, Depends(get_storage)],
    log: Annotated[AppLogger, Depends(get_log)],
) -> KbService:
    settings: Settings = get_settings()
    return KbService(
        session,
        session_factory,
        llm,
        embedder,
        image_describer,
        storage,
        settings,
        log,
    )


@router.post("/v1/collections", response_model=CollectionResponse)
async def create_collection(
    body: CollectionCreateRequest,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[KbService, Depends(get_service)],
) -> CollectionResponse:
    return await service.create_collection(owner_id, body)


@router.get("/v1/collections", response_model=list[CollectionResponse])
async def list_collections(
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[KbService, Depends(get_service)],
) -> list[CollectionResponse]:
    return await service.list_collections(owner_id)


@router.get("/v1/collections/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[KbService, Depends(get_service)],
) -> CollectionResponse:
    return await service.get_collection(owner_id, collection_id)


@router.get(
    "/v1/collections/{collection_id}/index",
    response_model=CollectionIndexResponse,
)
async def get_collection_index(
    collection_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[KbService, Depends(get_service)],
) -> CollectionIndexResponse:
    return await service.get_collection_index(owner_id, collection_id)


@router.get(
    "/v1/collections/{collection_id}/agents",
    response_model=list[AgentResponse],
)
async def list_collection_agents(
    collection_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[KbService, Depends(get_service)],
) -> list[AgentResponse]:
    return await service.list_agents(owner_id, collection_id)


@router.post(
    "/v1/collections/{collection_id}/agents",
    response_model=AgentResponse,
)
async def attach_collection_agent(
    collection_id: str,
    body: CollectionAgentAttachRequest,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[KbService, Depends(get_service)],
) -> AgentResponse:
    return await service.attach_agent(owner_id, collection_id, body.agent_id)


@router.delete(
    "/v1/collections/{collection_id}/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def detach_collection_agent(
    collection_id: str,
    agent_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[KbService, Depends(get_service)],
) -> Response:
    await service.detach_agent(owner_id, collection_id, agent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/v1/collections/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_collection(
    collection_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[KbService, Depends(get_service)],
) -> Response:
    await service.delete_collection(owner_id, collection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/v1/collections/{collection_id}/files",
    response_model=KbFileResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_file(
    collection_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[KbService, Depends(get_service)],
    file: Annotated[UploadFile, File()],
) -> KbFileResponse:
    return await service.upload_file(owner_id, collection_id, file)


@router.get(
    "/v1/collections/{collection_id}/files",
    response_model=list[KbFileSummary],
)
async def list_files(
    collection_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[KbService, Depends(get_service)],
) -> list[KbFileSummary]:
    return await service.list_files(owner_id, collection_id)


@router.get(
    "/v1/collections/{collection_id}/files/{file_id}",
    response_model=KbFileResponse,
)
async def get_file(
    collection_id: str,
    file_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[KbService, Depends(get_service)],
) -> KbFileResponse:
    return await service.get_file(owner_id, collection_id, file_id)


@router.delete(
    "/v1/collections/{collection_id}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_file(
    collection_id: str,
    file_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[KbService, Depends(get_service)],
) -> Response:
    await service.delete_file(owner_id, collection_id, file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/v1/files/{file_id}/content", response_model=None)
async def get_file_content(
    file_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[KbService, Depends(get_service)],
) -> RedirectResponse:
    url = await service.content_url(owner_id, file_id)
    # Redirecting is deliberate: S3 honors range requests, so pdf.js can lazily
    # fetch the cited page instead of downloading the PDF through this API.
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/v1/files/{file_id}/view", response_model=KbFileViewResponse)
async def view_file(
    file_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[KbService, Depends(get_service)],
) -> KbFileViewResponse:
    return await service.view_file(owner_id, file_id)


@router.post(
    "/v1/observability/collections/{collection_id}/query",
    response_model=ObservabilityQueryResponse,
)
async def query_collection_for_observability(
    collection_id: str,
    body: ObservabilityQueryRequest,
    owner_id: Annotated[str, Depends(require_alice)],
    service: Annotated[KbService, Depends(get_service)],
) -> ObservabilityQueryResponse:
    return await service.query_collection_for_observability(
        owner_id,
        collection_id,
        body.query,
        body.limit,
    )
