from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_id
from app.features.agents.appearance import random_appearance
from app.features.agents.models import Agent
from app.features.agents.repository import AgentRepository
from app.features.agents.schemas import (
    AgentCreateRequest,
    AgentInstructionsResponse,
    AgentResponse,
    AgentUpdateRequest,
)


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AgentRepository(session)

    async def create(self, owner_id: str, body: AgentCreateRequest) -> AgentResponse:
        now = datetime.now(UTC)
        agent = Agent(
            id=new_id("agt"),
            owner_id=owner_id,
            name=body.name.strip(),
            description=body.description.strip(),
            instructions="",
            appearance=random_appearance(),
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

    async def _owned(self, agent_id: str, owner_id: str) -> Agent:
        agent = await self.repo.get_owned(agent_id, owner_id)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found",
            )
        return agent
