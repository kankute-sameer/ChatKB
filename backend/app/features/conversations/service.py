from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import Any

from app.core.citations import Citations
from app.core.ids import new_id
from app.core.llm.types import LLM, ChatMessage, StreamEvent
from app.core.log import AppLogger, get_logger
from app.core.tools import ToolRegistry
from app.core.tools.protocol import ToolResult
from app.features.conversations.buffer import EventLog, StreamStore
from app.features.conversations.models import Conversation, Message
from app.features.conversations.openai import messages_to_responses_input
from app.features.conversations.prompts import AGENT_INSTRUCTIONS, TITLE_PROMPT
from app.features.conversations.repository import ConversationRepository
from app.features.conversations.schemas import (
    ConversationCreateResponse,
    ConversationDetail,
    ConversationSummary,
    CreateResponseRequest,
    StopRequest,
    StopResponse,
    UIMessage,
)
from fastapi import HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 8
TERMINAL_EVENT_TYPES = {"finish", "finish-step"}

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
    "x-vercel-ai-ui-message-stream": "v1",
}


class PartsAccumulator:
    def __init__(self) -> None:
        self.parts: list[dict[str, Any]] = []
        self._text_index: dict[str, int] = {}
        self._reasoning_index: dict[str, int] = {}

    def apply(self, event: StreamEvent | dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "text-start":
            self._start_part(self._text_index, event, "text")
        elif event_type == "text-delta":
            self._delta_part(self._text_index, event, "text")
        elif event_type == "text-end":
            self._end_part(self._text_index, event)
        elif event_type == "reasoning-start":
            self._start_part(self._reasoning_index, event, "reasoning")
        elif event_type == "reasoning-delta":
            self._delta_part(self._reasoning_index, event, "reasoning")
        elif event_type == "reasoning-end":
            self._end_part(self._reasoning_index, event)
        elif event_type == "tool-input-start":
            tool_name = str(event.get("toolName") or "tool")
            self.parts.append(
                {
                    "type": f"tool-{tool_name}",
                    "toolCallId": event.get("toolCallId"),
                    "toolName": tool_name,
                    "state": "input-streaming",
                    "input": {},
                }
            )
        elif event_type == "tool-input-available":
            tool_id = event.get("toolCallId")
            for part in self.parts:
                if part.get("toolCallId") == tool_id:
                    part["input"] = event.get("input") or {}
                    part["state"] = "input-available"
        elif event_type == "tool-output-available":
            tool_id = event.get("toolCallId")
            for part in self.parts:
                if part.get("toolCallId") == tool_id:
                    part["output"] = event.get("output")
                    part["state"] = "output-available"
        elif isinstance(event_type, str) and event_type.startswith("source-"):
            self.parts.append(dict(event))

    def _start_part(
        self,
        index_map: dict[str, int],
        event: StreamEvent | dict[str, Any],
        part_type: str,
    ) -> None:
        part_id = str(event.get("id", ""))
        index_map[part_id] = len(self.parts)
        self.parts.append({"type": part_type, "text": "", "state": "streaming"})

    def _delta_part(
        self,
        index_map: dict[str, int],
        event: StreamEvent | dict[str, Any],
        part_type: str,
    ) -> None:
        part_id = str(event.get("id", ""))
        index = index_map.get(part_id)
        if index is None:
            index = len(self.parts)
            index_map[part_id] = index
            self.parts.append({"type": part_type, "text": "", "state": "streaming"})
        delta = event.get("delta") or ""
        self.parts[index]["text"] = str(self.parts[index].get("text") or "") + delta

    def _end_part(
        self, index_map: dict[str, int], event: StreamEvent | dict[str, Any]
    ) -> None:
        part_id = str(event.get("id", ""))
        index = index_map.get(part_id)
        if index is not None:
            self.parts[index]["state"] = "done"

    def finalize(self) -> list[dict[str, Any]]:
        finalized: list[dict[str, Any]] = []
        for part in self.parts:
            item = dict(part)
            if item.get("type") in ("text", "reasoning"):
                item["state"] = "done"
            finalized.append(item)
        return finalized


def text_from_parts(parts: Sequence[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for part in parts:
        if part.get("type") == "text":
            chunks.append(str(part.get("text") or ""))
    return "".join(chunks)


def validate_text_parts(
    parts: Sequence[dict[str, Any]], citations: Citations
) -> None:
    for part in parts:
        if part.get("type") == "text":
            part["text"] = citations.validate(str(part.get("text") or ""))


def format_sse(event_id: int, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, separators=(",", ":"))
    return f"id: {event_id}\ndata: {data}\n\n"


def replay_events_from_message(message: Message) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        {"type": "start", "messageId": message.id},
        {"type": "start-step"},
    ]
    for part in message.parts:
        part_type = part.get("type")
        text = str(part.get("text") or "")
        if part_type == "reasoning":
            part_id = new_id("rsn")
            events.extend(
                [
                    {"type": "reasoning-start", "id": part_id},
                    {"type": "reasoning-delta", "id": part_id, "delta": text},
                    {"type": "reasoning-end", "id": part_id},
                ]
            )
        elif part_type == "text":
            part_id = new_id("text")
            events.extend(
                [
                    {"type": "text-start", "id": part_id},
                    {"type": "text-delta", "id": part_id, "delta": text},
                    {"type": "text-end", "id": part_id},
                ]
            )
        elif part_type == "source-url":
            events.append(
                {
                    "type": "source-url",
                    "sourceId": part.get("sourceId"),
                    "url": part.get("url"),
                    "title": part.get("title"),
                    "snippet": part.get("snippet"),
                    "publishedDate": part.get("publishedDate"),
                }
            )
        elif isinstance(part_type, str) and (
            part_type.startswith("tool-") or part_type == "dynamic-tool"
        ):
            tool_id = str(part.get("toolCallId") or new_id("call"))
            tool_name = str(
                part.get("toolName")
                or (part_type[5:] if part_type.startswith("tool-") else "tool")
            )
            events.append(
                {
                    "type": "tool-input-start",
                    "toolCallId": tool_id,
                    "toolName": tool_name,
                    "providerExecuted": True,
                }
            )
            events.append(
                {
                    "type": "tool-input-available",
                    "toolCallId": tool_id,
                    "toolName": tool_name,
                    "input": part.get("input") or {},
                    "providerExecuted": True,
                }
            )
            if "output" in part:
                events.append(
                    {
                        "type": "tool-output-available",
                        "toolCallId": tool_id,
                        "output": part.get("output"),
                        "providerExecuted": True,
                    }
                )
    events.extend(
        [
            {"type": "finish-step"},
            {"type": "finish"},
        ]
    )
    return events


async def sse_from_buffer(
    buffer: EventLog, after_id: int
) -> AsyncIterator[str]:
    async for event_id, payload in buffer.read_from(after_id):
        yield format_sse(event_id, payload)
    yield "data: [DONE]\n\n"


async def sse_from_events(events: Sequence[dict[str, Any]]) -> AsyncIterator[str]:
    for index, payload in enumerate(events, start=1):
        yield format_sse(index, payload)
    yield "data: [DONE]\n\n"


class ConversationService:
    def __init__(
        self,
        session: AsyncSession,
        store: StreamStore,
        llm: LLM,
        session_factory: async_sessionmaker[AsyncSession],
        tools: ToolRegistry,
        log: AppLogger | None = None,
    ) -> None:
        self.session = session
        self.store = store
        self.llm = llm
        self.session_factory = session_factory
        self.tools = tools
        self.log = log.child("gen") if log is not None else get_logger("chatkb.gen")
        self.repo = ConversationRepository(session)

    async def create_conversation(self, owner_id: str) -> ConversationCreateResponse:
        now = datetime.now(UTC)
        conversation = Conversation(
            id=new_id("conv"),
            owner_id=owner_id,
            title=None,
            active_response_id=None,
            last_event_id=None,
            created_at=now,
            updated_at=now,
            last_active_at=now,
        )
        await self.repo.create(conversation)
        await self.session.commit()
        await self.session.refresh(conversation)
        return ConversationCreateResponse.model_validate(conversation)

    async def list_conversations(
        self, owner_id: str, limit: int
    ) -> list[ConversationSummary]:
        rows = await self.repo.list_for_owner(owner_id, limit)
        return [ConversationSummary.model_validate(row) for row in rows]

    async def get_conversation(
        self, owner_id: str, conversation_id: str
    ) -> ConversationDetail:
        conversation = await self._owned(conversation_id, owner_id)
        return ConversationDetail(
            id=conversation.id,
            title=conversation.title,
            messages=[
                UIMessage(
                    id=item.id,
                    role="assistant" if item.role == "assistant" else "user",
                    parts=item.parts,
                )
                for item in conversation.messages
                if item.role in ("user", "assistant")
            ],
            active_response_id=conversation.active_response_id,
            last_event_id=conversation.last_event_id,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            last_active_at=conversation.last_active_at,
        )

    async def start_response(
        self, owner_id: str, body: CreateResponseRequest
    ) -> StreamingResponse:
        conversation = await self._owned(body.id, owner_id)
        await self.repo.add_message(conversation.id, body.message)
        response_id = new_id("resp")
        assistant_message_id = new_id("msg")
        conversation.active_response_id = response_id
        conversation.last_active_at = datetime.now(UTC)
        conversation.updated_at = datetime.now(UTC)
        await self.session.commit()

        buffer = self.store.create(response_id)
        task = asyncio.create_task(
            run_generation(
                conversation_id=conversation.id,
                response_id=response_id,
                assistant_message_id=assistant_message_id,
                store=self.store,
                llm=self.llm,
                session_factory=self.session_factory,
                tools=self.tools,
                log=self.log,
            ),
            name=f"generate:{response_id}",
        )
        self.store.register_task(response_id, task)

        if conversation.title is None:
            user_text = text_from_parts(body.message.parts)
            asyncio.create_task(
                run_title_generation(
                    conversation_id=conversation.id,
                    user_text=user_text,
                    llm=self.llm,
                    session_factory=self.session_factory,
                ),
                name=f"title:{conversation.id}",
            )

        return StreamingResponse(
            sse_from_buffer(buffer, after_id=0),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    async def resume_stream(
        self,
        owner_id: str,
        conversation_id: str,
        last_event_id: int,
        active_response_id: str | None,
    ) -> Response:
        conversation = await self._owned(conversation_id, owner_id)
        response_id = active_response_id or conversation.active_response_id
        if conversation.active_response_id is None and active_response_id is None:
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        if response_id is not None:
            buffer = self.store.get(response_id)
            if buffer is not None:
                return StreamingResponse(
                    sse_from_buffer(buffer, after_id=last_event_id),
                    media_type="text/event-stream",
                    headers=SSE_HEADERS,
                )

        assistant = await self.repo.latest_assistant_message(conversation.id)
        if assistant is None:
            if conversation.active_response_id is None:
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        return StreamingResponse(
            sse_from_events(replay_events_from_message(assistant)),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    async def stop(
        self, owner_id: str, conversation_id: str, body: StopRequest
    ) -> StopResponse:
        conversation = await self._owned(conversation_id, owner_id)
        active_id = conversation.active_response_id
        if active_id is None:
            return StopResponse()
        if body.active_stream_id is not None and body.active_stream_id != active_id:
            return StopResponse()

        if body.assistant_message is not None:
            await self.repo.upsert_message(conversation.id, body.assistant_message)
            await self.session.commit()

        task = self.store.get_task(active_id)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        latest = await self.repo.get_owned(conversation_id, owner_id)
        if latest is not None and latest.active_response_id == active_id:
            await self.repo.set_active_response(
                conversation_id, None, last_event_id=None
            )
        buffer = self.store.get(active_id)
        if buffer is not None and not buffer.finished:
            buffer.finish()
            self.store.mark_finished(active_id)
        return StopResponse()

    async def _owned(self, conversation_id: str, owner_id: str) -> Conversation:
        conversation = await self.repo.get_owned(conversation_id, owner_id)
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        return conversation


async def run_generation(
    conversation_id: str,
    response_id: str,
    assistant_message_id: str,
    store: StreamStore,
    llm: LLM,
    session_factory: async_sessionmaker[AsyncSession],
    tools: ToolRegistry,
    log: AppLogger,
) -> None:
    buffer = store.get(response_id)
    if buffer is None:
        return
    accumulator = PartsAccumulator()
    citations = Citations()
    try:
        async with session_factory() as session:
            repo = ConversationRepository(session)
            conversation = await repo.get(conversation_id)
            if conversation is None:
                buffer.append({"type": "error", "errorText": "Conversation not found"})
                buffer.finish()
                store.mark_finished(response_id)
                return
            input_items = messages_to_responses_input(
                conversation.messages,
                system=AGENT_INSTRUCTIONS,
            )

            async def emit(event: dict[str, Any]) -> None:
                log.debug("Transformed chunk %s", event)
                event_id = buffer.append(event)
                await repo.update_last_event_id(conversation_id, event_id)

            await emit({"type": "start", "messageId": assistant_message_id})
            await _run_agent_loop(
                input_items=input_items,
                llm=llm,
                tools=tools,
                citations=citations,
                accumulator=accumulator,
                emit=emit,
            )
            validate_text_parts(accumulator.parts, citations)
            parts = accumulator.finalize()
            if parts:
                await repo.upsert_message(
                    conversation_id,
                    UIMessage(
                        id=assistant_message_id,
                        role="assistant",
                        parts=parts,
                    ),
                )
            await repo.set_active_response(
                conversation_id, None, last_event_id=None
            )
    except asyncio.CancelledError:
        async with session_factory() as session:
            repo = ConversationRepository(session)
            validate_text_parts(accumulator.parts, citations)
            parts = accumulator.finalize()
            if parts:
                await repo.upsert_message(
                    conversation_id,
                    UIMessage(
                        id=assistant_message_id,
                        role="assistant",
                        parts=parts,
                    ),
                )
                await session.commit()
        raise
    except Exception:
        logger.exception("Generation failed for %s", response_id)
        try:
            event_id = buffer.append(
                {"type": "error", "errorText": "The model failed to complete."}
            )
            async with session_factory() as session:
                repo = ConversationRepository(session)
                await repo.update_last_event_id(conversation_id, event_id)
                validate_text_parts(accumulator.parts, citations)
                parts = accumulator.finalize()
                if parts:
                    await repo.upsert_message(
                        conversation_id,
                        UIMessage(
                            id=assistant_message_id,
                            role="assistant",
                            parts=parts,
                        ),
                    )
                await repo.set_active_response(
                    conversation_id, None, last_event_id=None
                )
        except Exception:
            logger.exception("Failed to persist error state for %s", response_id)
    finally:
        if not buffer.finished:
            buffer.finish()
        store.mark_finished(response_id)


async def _run_agent_loop(
    input_items: list[ChatMessage],
    llm: LLM,
    tools: ToolRegistry,
    citations: Citations,
    accumulator: PartsAccumulator,
    emit: Any,
) -> None:
    tool_schemas = tools.openai_tools() or None
    for _round in range(MAX_TOOL_ROUNDS):
        await emit({"type": "start-step"})
        pending: list[StreamEvent] = []
        async for event in llm.stream(input_items, tools=tool_schemas):
            event_type = event.get("type")
            if event_type in TERMINAL_EVENT_TYPES:
                continue
            accumulator.apply(event)
            await emit(dict(event))
            if event_type == "tool-input-available":
                pending.append(event)
        if not pending:
            await emit({"type": "finish-step"})
            await emit({"type": "finish"})
            return
        for call in pending:
            arguments = call.get("input") or {}
            input_items.append(
                {
                    "type": "function_call",
                    "call_id": str(call.get("toolCallId") or ""),
                    "name": str(call.get("toolName") or "tool"),
                    "arguments": json.dumps(arguments),
                }
            )
        for call in pending:
            result = await _execute_tool(call, tools, citations)
            output_event: StreamEvent = {
                "type": "tool-output-available",
                "toolCallId": str(call.get("toolCallId") or ""),
                "output": result.content,
                "providerExecuted": True,
            }
            accumulator.apply(output_event)
            await emit(dict(output_event))
            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": str(call.get("toolCallId") or ""),
                    "output": result.content,
                }
            )
            for part in result.source_parts:
                accumulator.apply(part)
                await emit(dict(part))
        await emit({"type": "finish-step"})
    await emit({"type": "finish"})


async def _execute_tool(
    call: StreamEvent,
    tools: ToolRegistry,
    citations: Citations,
) -> ToolResult:
    name = str(call.get("toolName") or "")
    args = call.get("input") or {}
    if not isinstance(args, dict):
        args = {}
    tool = tools.get(name)
    if tool is None:
        return ToolResult(content=json.dumps({"error": f"unknown tool: {name}"}))
    try:
        return await tool.run(args, citations)
    except Exception as exc:
        logger.warning("Tool %s failed: %s", name, exc)
        return ToolResult(content=json.dumps({"error": f"search failed: {exc}"}))


async def run_title_generation(
    conversation_id: str,
    user_text: str,
    llm: LLM,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        title = await llm.complete(
            [
                ChatMessage(
                    role="user",
                    content=TITLE_PROMPT.format(message=user_text),
                )
            ]
        )
        title = " ".join(title.split())[:80]
        if not title:
            return
        async with session_factory() as session:
            repo = ConversationRepository(session)
            await repo.set_title(conversation_id, title)
    except Exception:
        logger.exception("Title generation failed for %s", conversation_id)
