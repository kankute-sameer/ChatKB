from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_id
from app.features.agents.appearance import random_appearance
from app.features.agents.db import AgentRepository
from app.features.agents.models import Agent
from app.features.agents.schemas import (
    AgentCollectionsUpdate,
    AgentCreateRequest,
    AgentInstructionsResponse,
    AgentResponse,
    AgentUpdateRequest,
)
from app.features.kb.db import KbRepository
from app.features.kb.schemas import CollectionResponse


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AgentRepository(session)
        self.kb_repo = KbRepository(session)

    async def create(self, owner_id: str, body: AgentCreateRequest) -> AgentResponse:
        now = datetime.now(UTC)
        agent = Agent(
            id=new_id("agt"),
            owner_id=owner_id,
            name=body.name.strip(),
            description=body.description.strip(),
            instructions="",
            appearance=random_appearance(),
            connectors=["web_search"],
            visibility="personal",
            is_builder=False,
            created_at=now,
            updated_at=now,
        )
        await self.repo.create(agent)
        await self.session.commit()
        await self.session.refresh(agent)
        return AgentResponse.model_validate(agent)

    async def list_for_owner(self, owner_id: str) -> list[AgentResponse]:
        rows = await self.repo.list_for_owner(owner_id)
        return [AgentResponse.model_validate(row) for row in rows]

    async def get(self, owner_id: str, agent_id: str) -> AgentResponse:
        agent = await self._owned(agent_id, owner_id)
        return AgentResponse.model_validate(agent)

    async def get_instructions(
        self, owner_id: str, agent_id: str
    ) -> AgentInstructionsResponse:
        agent = await self._owned(agent_id, owner_id)
        return AgentInstructionsResponse(instructions=agent.instructions)

    async def update(
        self, owner_id: str, agent_id: str, body: AgentUpdateRequest
    ) -> AgentResponse:
        agent = await self._owned(agent_id, owner_id)
        if body.name is not None:
            agent.name = body.name.strip()
        if body.description is not None:
            agent.description = body.description
        if body.instructions is not None:
            agent.instructions = body.instructions
        if body.connectors is not None:
            agent.connectors = list(dict.fromkeys(body.connectors))
        await self.repo.touch(agent)
        await self.session.commit()
        await self.session.refresh(agent)
        return AgentResponse.model_validate(agent)

    async def delete(self, owner_id: str, agent_id: str) -> None:
        agent = await self._owned(agent_id, owner_id)
        if agent.is_builder:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete the builder agent",
            )
        await self.repo.delete(agent)
        await self.session.commit()

    async def list_collections(
        self, owner_id: str, agent_id: str
    ) -> list[CollectionResponse]:
        await self._owned(agent_id, owner_id)
        ids = await self.kb_repo.get_agent_collection_ids(agent_id)
        rows = await self.kb_repo.list_collections_by_ids(ids)
        return [CollectionResponse.model_validate(row) for row in rows]

    async def set_collections(
        self, owner_id: str, agent_id: str, body: AgentCollectionsUpdate
    ) -> list[CollectionResponse]:
        await self._owned(agent_id, owner_id)
        requested = list(dict.fromkeys(body.collection_ids))
        owned = await self.kb_repo.owned_collection_ids(owner_id, requested)
        if len(owned) != len(requested):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more collections were not found",
            )
        await self.kb_repo.set_agent_collections(agent_id, requested)
        await self.session.commit()
        rows = await self.kb_repo.list_collections_by_ids(requested)
        return [CollectionResponse.model_validate(row) for row in rows]

    async def _owned(self, agent_id: str, owner_id: str) -> Agent:
        agent = await self.repo.get_owned(agent_id, owner_id)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found",
            )
        return agent
