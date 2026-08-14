from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol, TypedDict


class ChatMessage(TypedDict, total=False):
    """A Responses API input item (message, function_call, or function_call_output)."""

    role: str
    content: str | None
    type: str
    call_id: str
    name: str
    arguments: str
    output: str


class StreamEvent(TypedDict, total=False):
    type: str
    messageId: str
    id: str
    delta: str
    errorText: str
    toolCallId: str
    toolName: str
    providerExecuted: bool
    inputTextDelta: str
    input: dict[str, Any]
    output: Any
    sourceId: str
    url: str
    title: str
    snippet: str
    publishedDate: str | None


class LLM(Protocol):
    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        tools: Sequence[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]: ...

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
    ) -> str: ...
