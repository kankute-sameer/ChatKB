from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.citations import Citations
from app.core.tools.protocol import ToolResult
from app.features.agents.repository import AgentRepository


@dataclass
class AgentEditorContext:
    session_factory: async_sessionmaker[AsyncSession]
    target_agent_id: str
    owner_id: str


@dataclass
class _AgentSnapshot:
    name: str
    description: str
    instructions: str


class GetAgentSetupTool:
    name = "get_agent_setup"
    description = (
        "Load the target agent's current name, description, and instructions. "
        "Call this first, silently, before editing."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    def __init__(self, ctx: AgentEditorContext) -> None:
        self._ctx = ctx

    async def run(self, args: dict[str, Any], citations: Citations) -> ToolResult:
        del args, citations
        snapshot = await _load_target(self._ctx)
        if snapshot is None:
            return ToolResult(content=json.dumps({"error": "target agent not found"}))
        return ToolResult(
            content=json.dumps(
                {
                    "name": snapshot.name,
                    "description": snapshot.description,
                    "instructions": snapshot.instructions,
                }
            )
        )


class UpdateAgentInstructionsTool:
    name = "update_agent_instructions"
    description = "Overwrite the target agent's instructions with the given text."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "instructions": {"type": "string"},
        },
        "required": ["instructions"],
        "additionalProperties": False,
    }

    def __init__(self, ctx: AgentEditorContext) -> None:
        self._ctx = ctx

    async def run(self, args: dict[str, Any], citations: Citations) -> ToolResult:
        del citations
        instructions = args.get("instructions")
        if not isinstance(instructions, str):
            return ToolResult(
                content=json.dumps({"error": "instructions must be a string"})
            )
        async with self._ctx.session_factory() as session:
            repo = AgentRepository(session)
            row = await repo.get_owned(self._ctx.target_agent_id, self._ctx.owner_id)
            if row is None:
                return ToolResult(
                    content=json.dumps({"error": "target agent not found"})
                )
            row.instructions = instructions
            await repo.touch(row)
            await session.commit()
            payload = {"ok": True, "instructions": instructions}
        return ToolResult(content=json.dumps(payload))


class UpdateAgentMetadataTool:
    name = "update_agent_metadata"
    description = "Update the target agent's name and/or description."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "description": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def __init__(self, ctx: AgentEditorContext) -> None:
        self._ctx = ctx

    async def run(self, args: dict[str, Any], citations: Citations) -> ToolResult:
        del citations
        name = args.get("name")
        description = args.get("description")
        if name is not None and not isinstance(name, str):
            return ToolResult(content=json.dumps({"error": "name must be a string"}))
        if description is not None and not isinstance(description, str):
            return ToolResult(
                content=json.dumps({"error": "description must be a string"})
            )
        if name is None and description is None:
            return ToolResult(
                content=json.dumps({"error": "name or description is required"})
            )
        async with self._ctx.session_factory() as session:
            repo = AgentRepository(session)
            row = await repo.get_owned(self._ctx.target_agent_id, self._ctx.owner_id)
            if row is None:
                return ToolResult(
                    content=json.dumps({"error": "target agent not found"})
                )
            if isinstance(name, str) and name.strip():
                row.name = name.strip()
            if isinstance(description, str):
                row.description = description
            await repo.touch(row)
            await session.commit()
            payload = {"ok": True, "name": row.name, "description": row.description}
        return ToolResult(content=json.dumps(payload))


def agent_editor_tools(ctx: AgentEditorContext) -> list[Any]:
    return [
        GetAgentSetupTool(ctx),
        UpdateAgentInstructionsTool(ctx),
        UpdateAgentMetadataTool(ctx),
    ]


async def _load_target(ctx: AgentEditorContext) -> _AgentSnapshot | None:
    async with ctx.session_factory() as session:
        repo = AgentRepository(session)
        agent = await repo.get_owned(ctx.target_agent_id, ctx.owner_id)
        if agent is None:
            return None
        return _AgentSnapshot(
            name=agent.name,
            description=agent.description,
            instructions=agent.instructions,
        )
