from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.citations import Citations
from app.core.tools.protocol import ToolResult
from app.features.agents.db import AgentRepository
from app.features.kb.db import KbRepository


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
    knowledge_bases: list[dict[str, str]]


class GetAgentSetupTool:
    name = "get_agent_setup"
    description = (
        "Load the target agent's current name, description, instructions, and "
        "attached knowledge bases. Call this first, silently, before editing."
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
                    "knowledge_bases": snapshot.knowledge_bases,
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


class ListKnowledgeBasesTool:
    name = "list_knowledge_bases"
    description = (
        "List the user's knowledge bases (id, name, description) and whether "
        "each is already attached to the target agent. Use this to infer which "
        "bases are relevant before attaching any."
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
        async with self._ctx.session_factory() as session:
            agents = AgentRepository(session)
            agent = await agents.get_owned(
                self._ctx.target_agent_id, self._ctx.owner_id
            )
            if agent is None:
                return ToolResult(
                    content=json.dumps({"error": "target agent not found"})
                )
            kb = KbRepository(session)
            collections = await kb.list_collections(self._ctx.owner_id)
            attached = set(await kb.get_agent_collection_ids(agent.id))
            payload = {
                "knowledge_bases": [
                    {
                        "id": row.id,
                        "name": row.name,
                        "description": row.description,
                        "attached": row.id in attached,
                    }
                    for row in collections
                ]
            }
        return ToolResult(content=json.dumps(payload))


class AttachKnowledgeBasesTool:
    name = "attach_knowledge_bases"
    description = (
        "Attach one or more knowledge bases to the target agent by id. Only "
        "attach bases that are clearly relevant. Merges with existing "
        "attachments; does not remove others."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "collection_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
        },
        "required": ["collection_ids"],
        "additionalProperties": False,
    }

    def __init__(self, ctx: AgentEditorContext) -> None:
        self._ctx = ctx

    async def run(self, args: dict[str, Any], citations: Citations) -> ToolResult:
        del citations
        raw_ids = args.get("collection_ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            return ToolResult(
                content=json.dumps(
                    {"error": "collection_ids must be a non-empty array of strings"}
                )
            )
        collection_ids: list[str] = []
        for item in raw_ids:
            if not isinstance(item, str) or not item.strip():
                return ToolResult(
                    content=json.dumps(
                        {"error": "collection_ids must be a non-empty array of strings"}
                    )
                )
            collection_ids.append(item.strip())
        collection_ids = list(dict.fromkeys(collection_ids))

        async with self._ctx.session_factory() as session:
            agents = AgentRepository(session)
            agent = await agents.get_owned(
                self._ctx.target_agent_id, self._ctx.owner_id
            )
            if agent is None:
                return ToolResult(
                    content=json.dumps({"error": "target agent not found"})
                )
            kb = KbRepository(session)
            owned = await kb.owned_collection_ids(self._ctx.owner_id, collection_ids)
            owned_set = set(owned)
            missing = [cid for cid in collection_ids if cid not in owned_set]
            if missing:
                return ToolResult(
                    content=json.dumps(
                        {
                            "error": "one or more knowledge bases were not found",
                            "missing_ids": missing,
                        }
                    )
                )
            before = set(await kb.get_agent_collection_ids(agent.id))
            newly_attached: list[dict[str, str]] = []
            already_attached: list[dict[str, str]] = []
            for collection_id in collection_ids:
                row = await kb.get_collection(collection_id)
                if row is None:
                    continue
                summary = {"id": row.id, "name": row.name}
                if collection_id in before:
                    already_attached.append(summary)
                    continue
                await kb.attach_agent_collection(agent.id, collection_id)
                newly_attached.append(summary)
            await agents.touch(agent)
            await session.commit()
            attached_rows = await kb.list_collections_by_ids(
                await kb.get_agent_collection_ids(agent.id)
            )
            payload = {
                "ok": True,
                "newly_attached": newly_attached,
                "already_attached": already_attached,
                "knowledge_bases": [
                    {"id": row.id, "name": row.name, "description": row.description}
                    for row in attached_rows
                ],
            }
        return ToolResult(content=json.dumps(payload))


def agent_editor_tools(ctx: AgentEditorContext) -> list[Any]:
    return [
        GetAgentSetupTool(ctx),
        UpdateAgentInstructionsTool(ctx),
        UpdateAgentMetadataTool(ctx),
        ListKnowledgeBasesTool(ctx),
        AttachKnowledgeBasesTool(ctx),
    ]


async def _load_target(ctx: AgentEditorContext) -> _AgentSnapshot | None:
    async with ctx.session_factory() as session:
        repo = AgentRepository(session)
        agent = await repo.get_owned(ctx.target_agent_id, ctx.owner_id)
        if agent is None:
            return None
        kb = KbRepository(session)
        collection_ids = await kb.get_agent_collection_ids(agent.id)
        collections = await kb.list_collections_by_ids(collection_ids)
        return _AgentSnapshot(
            name=agent.name,
            description=agent.description,
            instructions=agent.instructions,
            knowledge_bases=[
                {
                    "id": row.id,
                    "name": row.name,
                    "description": row.description,
                }
                for row in collections
            ],
        )
