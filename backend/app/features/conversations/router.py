from typing import Annotated

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.llm.types import LLM
from app.features.conversations.buffer import StreamStore
from app.features.conversations.schemas import (
    ConversationCreateResponse,
    ConversationDetail,
    ConversationSummary,
    CreateResponseRequest,
    StopRequest,
    StopResponse,
)
from app.features.conversations.service import ConversationService
from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

router = APIRouter(tags=["conversations"])


def get_stream_store(request: Request) -> StreamStore:
    return request.app.state.stream_store  # type: ignore[no-any-return]


def get_llm(request: Request) -> LLM:
    return request.app.state.llm  # type: ignore[no-any-return]


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory  # type: ignore[no-any-return]


def get_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    store: Annotated[StreamStore, Depends(get_stream_store)],
    llm: Annotated[LLM, Depends(get_llm)],
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
) -> ConversationService:
    return ConversationService(session, store, llm, session_factory)


@router.post("/v1/conversations", response_model=ConversationCreateResponse)
async def create_conversation(
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[ConversationService, Depends(get_service)],
) -> ConversationCreateResponse:
    return await service.create_conversation(owner_id)


@router.get("/v1/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[ConversationService, Depends(get_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ConversationSummary]:
    return await service.list_conversations(owner_id, limit)


@router.get("/v1/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[ConversationService, Depends(get_service)],
) -> ConversationDetail:
    return await service.get_conversation(owner_id, conversation_id)


@router.get("/v1/conversations/{conversation_id}/stream")
async def resume_stream(
    conversation_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[ConversationService, Depends(get_service)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    active_response_id: str | None = Query(default=None, alias="activeResponseId"),
) -> object:
    after = 0
    if last_event_id:
        try:
            after = int(last_event_id)
        except ValueError:
            after = 0
    return await service.resume_stream(
        owner_id, conversation_id, after, active_response_id
    )


@router.post("/v1/conversations/{conversation_id}/stop", response_model=StopResponse)
async def stop_stream(
    conversation_id: str,
    body: StopRequest,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[ConversationService, Depends(get_service)],
) -> StopResponse:
    return await service.stop(owner_id, conversation_id, body)


@router.post("/v1/responses")
async def create_response(
    body: CreateResponseRequest,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[ConversationService, Depends(get_service)],
) -> object:
    return await service.start_response(owner_id, body)
