from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.agents.models import Agent


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, agent: Agent) -> Agent:
        self.session.add(agent)
        await self.session.flush()
        return agent

    async def get(self, agent_id: str) -> Agent | None:
        return await self.session.get(Agent, agent_id)

    async def get_owned(self, agent_id: str, owner_id: str) -> Agent | None:
        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id, Agent.owner_id == owner_id)
        )
        return result.scalar_one_or_none()

    async def list_for_owner(self, owner_id: str) -> list[Agent]:
        result = await self.session.execute(
            select(Agent)
            .where(Agent.owner_id == owner_id, Agent.is_builder.is_(False))
            .order_by(Agent.updated_at.desc())
        )
        return list(result.scalars().all())

    async def list_owned_by_ids(
        self,
        owner_id: str,
        ids: list[str],
    ) -> list[Agent]:
        if not ids:
            return []
        result = await self.session.execute(
            select(Agent).where(
                Agent.owner_id == owner_id,
                Agent.is_builder.is_(False),
                Agent.id.in_(ids),
            )
        )
        by_id = {row.id: row for row in result.scalars().all()}
        return [by_id[agent_id] for agent_id in ids if agent_id in by_id]

    async def delete(self, agent: Agent) -> None:
        await self.session.delete(agent)
        await self.session.flush()

    async def touch(self, agent: Agent) -> None:
        agent.updated_at = datetime.now(UTC)
        await self.session.flush()
