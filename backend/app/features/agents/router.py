from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.features.agents.schemas import (
    AgentCreateRequest,
    AgentInstructionsResponse,
    AgentResponse,
    AgentUpdateRequest,
)
from app.features.agents.service import AgentService

router = APIRouter(tags=["agents"])


def get_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentService:
    return AgentService(session)


@router.post("/v2/agents", response_model=AgentResponse)
async def create_agent(
    body: AgentCreateRequest,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[AgentService, Depends(get_service)],
) -> AgentResponse:
    return await service.create(owner_id, body)


@router.get("/v2/agents", response_model=list[AgentResponse])
async def list_agents(
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[AgentService, Depends(get_service)],
) -> list[AgentResponse]:
    return await service.list_for_owner(owner_id)


@router.get("/v2/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[AgentService, Depends(get_service)],
) -> AgentResponse:
    return await service.get(owner_id, agent_id)


@router.get(
    "/v2/agents/{agent_id}/instructions",
    response_model=AgentInstructionsResponse,
)
async def get_agent_instructions(
    agent_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[AgentService, Depends(get_service)],
) -> AgentInstructionsResponse:
    return await service.get_instructions(owner_id, agent_id)


@router.patch("/v2/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    body: AgentUpdateRequest,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[AgentService, Depends(get_service)],
) -> AgentResponse:
    return await service.update(owner_id, agent_id, body)


@router.delete("/v2/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    owner_id: Annotated[str, Depends(get_current_user)],
    service: Annotated[AgentService, Depends(get_service)],
) -> Response:
    await service.delete(owner_id, agent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
