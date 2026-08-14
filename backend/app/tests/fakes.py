from collections.abc import AsyncIterator, Sequence
from typing import Any

from app.core.llm.types import ChatMessage, StreamEvent


class FakeLLM:
    def __init__(
        self,
        chunks: Sequence[str] | None = None,
        title: str = "Test title",
        rounds: Sequence[Sequence[StreamEvent]] | None = None,
    ) -> None:
        import asyncio

        self.chunks = list(chunks or ["Hello", " world"])
        self.title = title
        self.rounds = [list(round_events) for round_events in rounds] if rounds else None
        self.round_index = 0
        self.calls: list[list[ChatMessage]] = []
        self.started = asyncio.Event()
        self.continue_event = asyncio.Event()
        self.continue_event.set()

    async def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        tools: Sequence[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        del model, tools
        self.calls.append(list(messages))
        if self.rounds is not None:
            events = self.rounds[min(self.round_index, len(self.rounds) - 1)]
            self.round_index += 1
            for event in events:
                yield event
            return
        yield StreamEvent(type="text-start", id="text_test")
        if self.chunks:
            yield StreamEvent(type="text-delta", id="text_test", delta=self.chunks[0])
        self.started.set()
        for chunk in self.chunks[1:]:
            await self.continue_event.wait()
            yield StreamEvent(type="text-delta", id="text_test", delta=chunk)
        yield StreamEvent(type="text-end", id="text_test")
        yield StreamEvent(type="finish-step")
        yield StreamEvent(type="finish")

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
    ) -> str:
        del messages, model
        return self.title
