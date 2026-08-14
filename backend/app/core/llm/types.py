from collections.abc import AsyncIterator, Sequence
from typing import Any, Literal, Protocol, TypedDict

ChatRole = Literal["system", "user", "assistant"]


class ChatMessage(TypedDict):
    role: ChatRole
    content: str


class StreamEvent(TypedDict, total=False):
    type: str
    messageId: str
    id: str
    delta: str
    errorText: str
    toolCallId: str
    toolName: str
    inputTextDelta: str
    input: dict[str, Any]


class LLM(Protocol):
    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
    ) -> AsyncIterator[StreamEvent]: ...

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
    ) -> str: ...
