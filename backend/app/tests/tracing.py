from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from app.core.tracing import ObservationType


@dataclass
class RecordedObservation:
    name: str
    as_type: ObservationType
    input: Any = None
    metadata: Any = None
    model: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    parent: str | None = None
    updates: list[dict[str, Any]] = field(default_factory=list)

    def update(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)


class RecordingTracer:
    def __init__(self) -> None:
        self.observations: list[RecordedObservation] = []
        self.flushes = 0
        self._current: ContextVar[str | None] = ContextVar(
            "recording_trace_parent",
            default=None,
        )

    @contextmanager
    def trace(
        self,
        name: str,
        *,
        input: Any = None,
        session_id: str | None = None,
        user_id: str | None = None,
        metadata: Any = None,
    ) -> Iterator[RecordedObservation]:
        with self._record(
            name,
            as_type="span",
            input=input,
            metadata=metadata,
            session_id=session_id,
            user_id=user_id,
        ) as observation:
            yield observation

    def span(
        self,
        name: str,
        *,
        input: Any = None,
        metadata: Any = None,
        as_type: ObservationType = "span",
    ) -> Any:
        return self._record(
            name,
            as_type=as_type,
            input=input,
            metadata=metadata,
        )

    def generation(
        self,
        name: str,
        *,
        model: str | None,
        input: Any = None,
        metadata: Any = None,
    ) -> Any:
        return self._record(
            name,
            as_type="generation",
            input=input,
            metadata=metadata,
            model=model,
        )

    @contextmanager
    def _record(
        self,
        name: str,
        *,
        as_type: ObservationType,
        input: Any,
        metadata: Any,
        model: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> Iterator[RecordedObservation]:
        observation = RecordedObservation(
            name=name,
            as_type=as_type,
            input=input,
            metadata=metadata,
            model=model,
            session_id=session_id,
            user_id=user_id,
            parent=self._current.get(),
        )
        self.observations.append(observation)
        token = self._current.set(name)
        try:
            yield observation
        finally:
            self._current.reset(token)

    def schedule_flush(self) -> None:
        self.flushes += 1

    async def shutdown(self) -> None:
        return
