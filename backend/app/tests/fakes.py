from collections.abc import AsyncIterator, Sequence
from typing import Any

from PIL import Image

from app.core.llm.types import ChatMessage, StreamEvent
from app.features.kb.ingestion.embed import DOCUMENT_TASK_TYPE
from app.features.kb.models import EMBEDDING_DIMENSIONS


class FakeLLM:
    def __init__(
        self,
        chunks: Sequence[str] | None = None,
        title: str = "Test title",
        rounds: Sequence[Sequence[StreamEvent]] | None = None,
        image_description: str = "A test image.",
    ) -> None:
        import asyncio

        self.chunks = list(chunks or ["Hello", " world"])
        self.title = title
        self.rounds = (
            [list(round_events) for round_events in rounds] if rounds else None
        )
        self.round_index = 0
        self.image_description = image_description
        self.images: list[Image.Image] = []
        self.calls: list[list[ChatMessage]] = []
        self.tools_seen: list[Sequence[dict[str, Any]] | None] = []
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
        del model
        self.calls.append(list(messages))
        self.tools_seen.append(list(tools) if tools is not None else None)
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

    async def describe_image(self, image: Image.Image) -> str:
        self.images.append(image)
        return self.image_description


class FakeEmbedder:
    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        self.dimensions = dimensions
        self.texts: list[str] = []
        self.task_types: list[str] = []

    async def embed(
        self,
        texts: Sequence[str],
        *,
        task_type: str = DOCUMENT_TASK_TYPE,
    ) -> list[list[float]]:
        self.texts.extend(texts)
        self.task_types.append(task_type)
        return [[0.01] * self.dimensions for _ in texts]


class FakeStorage:
    def __init__(self) -> None:
        self.puts: list[tuple[str, bytes, str]] = []
        self.objects: dict[str, bytes] = {}
        self.deletes: list[str] = []
        self.presigned: list[tuple[str, int]] = []

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.puts.append((key, data, content_type))
        self.objects[key] = data

    async def get(self, key: str) -> bytes:
        return self.objects[key]

    async def presigned_get_url(self, key: str, expires_in: int = 300) -> str:
        self.presigned.append((key, expires_in))
        return f"https://example-bucket.s3.amazonaws.com/{key}?signature=test"

    async def delete(self, key: str) -> None:
        self.deletes.append(key)
        self.objects.pop(key, None)
