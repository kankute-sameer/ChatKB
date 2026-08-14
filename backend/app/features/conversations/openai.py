from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from app.core.llm.types import ChatMessage
from app.features.conversations.models import Message

SOURCE_TYPES = {"source-url", "source-document"}
SKIP_TYPES = SOURCE_TYPES | {"reasoning"}


def messages_to_responses_input(
    messages: Sequence[Message],
    *,
    system: str | None = None,
) -> list[ChatMessage]:
    """Convert stored UI messages to Responses API input items.

    Source parts are stripped here and never sent to the model.
    """
    converted: list[ChatMessage] = []
    if system:
        converted.append({"role": "system", "content": system})
    for message in messages:
        if message.role == "user":
            converted.append(
                {"role": "user", "content": _text_content(message.parts)}
            )
        elif message.role == "assistant":
            converted.extend(_assistant_to_responses(message.parts))
        elif message.role == "system":
            converted.append(
                {"role": "system", "content": _text_content(message.parts)}
            )
    return converted


def _assistant_to_responses(parts: Sequence[dict[str, Any]]) -> list[ChatMessage]:
    converted: list[ChatMessage] = []
    text_chunks: list[str] = []

    def flush_text() -> None:
        text = "".join(text_chunks)
        text_chunks.clear()
        if text:
            converted.append({"role": "assistant", "content": text})

    for part in parts:
        part_type = str(part.get("type") or "")
        if part_type in SKIP_TYPES:
            continue
        if _is_tool_part(part_type):
            flush_text()
            call, result = _tool_items(part)
            if call is not None:
                converted.append(call)
            if result is not None:
                converted.append(result)
            continue
        if part_type == "text":
            text_chunks.append(str(part.get("text") or ""))
            continue

    flush_text()
    return converted


def _is_tool_part(part_type: str) -> bool:
    return part_type.startswith("tool-") or part_type in {
        "tool-call",
        "tool-result",
        "dynamic-tool",
    }


def _tool_items(
    part: dict[str, Any],
) -> tuple[ChatMessage | None, ChatMessage | None]:
    tool_id = str(part.get("toolCallId") or part.get("id") or "")
    name = str(part.get("toolName") or part.get("name") or "tool")
    arguments = part.get("input")
    if arguments is None:
        arguments = part.get("args") or {}
    output = part.get("output")
    if output is None:
        output = part.get("result")
    call: ChatMessage | None = None
    result: ChatMessage | None = None
    if tool_id and part.get("type") != "tool-result":
        call = {
            "type": "function_call",
            "call_id": tool_id,
            "name": name,
            "arguments": _arguments_json(arguments),
        }
    if tool_id and output is not None:
        result = {
            "type": "function_call_output",
            "call_id": tool_id,
            "output": output if isinstance(output, str) else json.dumps(output),
        }
    return call, result


def _arguments_json(arguments: object) -> str:
    if isinstance(arguments, str):
        return arguments
    try:
        return json.dumps(arguments)
    except TypeError:
        return "{}"


def _text_content(parts: Sequence[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for part in parts:
        if part.get("type") == "text":
            chunks.append(str(part.get("text") or ""))
    return "".join(chunks)
