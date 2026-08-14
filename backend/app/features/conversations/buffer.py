from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

EventPayload = dict[str, Any]
BufferedEvent = tuple[int, EventPayload]


class EventIdCounter:
    """Process-wide monotonic event ids (not per-response)."""

    def __init__(self) -> None:
        self._n = 0

    def next_id(self) -> int:
        self._n += 1
        return self._n


@runtime_checkable
class EventLog(Protocol):
    finished: bool

    def append(self, event: EventPayload) -> int: ...

    def read_from(self, after_id: int) -> AsyncIterator[BufferedEvent]: ...

    def finish(self) -> None: ...


@runtime_checkable
class StreamStore(Protocol):
    """Swap-out point for a Redis Streams implementation."""

    def create(self, response_id: str) -> EventLog: ...

    def get(self, response_id: str) -> EventLog | None: ...

    def register_task(self, response_id: str, task: asyncio.Task[None]) -> None: ...

    def get_task(self, response_id: str) -> asyncio.Task[None] | None: ...

    def mark_finished(self, response_id: str) -> None: ...

    def evict(self, response_id: str) -> None: ...

    async def cleanup_loop(self) -> None: ...


class ResponseBuffer:
    """Holds events for one in-flight response. Multiple independent readers."""

    def __init__(self, counter: EventIdCounter) -> None:
        self.events: list[BufferedEvent] = []
        self.finished = False
        self._counter = counter
        self._wakeup = asyncio.Event()

    def append(self, event: EventPayload) -> int:
        event_id = self._counter.next_id()
        self.events.append((event_id, event))
        self._notify()
        return event_id

    def finish(self) -> None:
        self.finished = True
        self._notify()

    def _notify(self) -> None:
        previous = self._wakeup
        self._wakeup = asyncio.Event()
        previous.set()

    async def read_from(self, after_id: int) -> AsyncIterator[BufferedEvent]:
        index = 0
        last_emitted = after_id
        while True:
            while index < len(self.events):
                event_id, payload = self.events[index]
                index += 1
                if event_id > last_emitted:
                    last_emitted = event_id
                    yield event_id, payload
            if self.finished:
                return
            wakeup = self._wakeup
            if index < len(self.events) or self.finished:
                continue
            await wakeup.wait()


@dataclass
class _Entry:
    buffer: ResponseBuffer
    task: asyncio.Task[None] | None = None
    finished_at: float | None = None


@dataclass
class InMemoryStreamStore:
    ttl_seconds: float = 300
    counter: EventIdCounter = field(default_factory=EventIdCounter)
    _entries: dict[str, _Entry] = field(default_factory=dict)

    def create(self, response_id: str) -> ResponseBuffer:
        buffer = ResponseBuffer(self.counter)
        self._entries[response_id] = _Entry(buffer=buffer)
        return buffer

    def get(self, response_id: str) -> ResponseBuffer | None:
        entry = self._entries.get(response_id)
        if entry is None:
            return None
        return entry.buffer

    def register_task(self, response_id: str, task: asyncio.Task[None]) -> None:
        entry = self._entries.get(response_id)
        if entry is None:
            raise KeyError(response_id)
        entry.task = task

    def get_task(self, response_id: str) -> asyncio.Task[None] | None:
        entry = self._entries.get(response_id)
        if entry is None:
            return None
        return entry.task

    def mark_finished(self, response_id: str) -> None:
        entry = self._entries.get(response_id)
        if entry is None:
            return
        entry.finished_at = time.monotonic()

    def evict(self, response_id: str) -> None:
        self._entries.pop(response_id, None)

    async def cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(30)
            now = time.monotonic()
            expired = [
                key
                for key, entry in self._entries.items()
                if entry.finished_at is not None
                and now - entry.finished_at >= self.ttl_seconds
            ]
            for key in expired:
                self._entries.pop(key, None)
