from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal, Protocol

from app.core.config import Settings
from app.core.log import AppLogger, get_logger

TRACE_TEXT_LIMIT = 500
TRACE_LIST_LIMIT = 20
TRACE_DICT_LIMIT = 30
ObservationType = Literal[
    "span",
    "generation",
    "tool",
    "retriever",
    "agent",
    "chain",
]
ScoreDataType = Literal["BOOLEAN", "TEXT"]


class Observation(Protocol):
    def update(self, **kwargs: Any) -> None: ...


class Tracer(Protocol):
    def trace(
        self,
        name: str,
        *,
        input: Any = None,
        session_id: str | None = None,
        user_id: str | None = None,
        metadata: Any = None,
        trace_id_seed: str | None = None,
    ) -> Any: ...

    def span(
        self,
        name: str,
        *,
        input: Any = None,
        metadata: Any = None,
        as_type: ObservationType = "span",
    ) -> Any: ...

    def generation(
        self,
        name: str,
        *,
        model: str | None,
        input: Any = None,
        metadata: Any = None,
    ) -> Any: ...

    def schedule_flush(self) -> None: ...

    def score_trace(
        self,
        trace_id_seed: str,
        *,
        name: str,
        value: bool | str,
        data_type: ScoreDataType = "BOOLEAN",
        score_id_seed: str | None = None,
        comment: str | None = None,
        metadata: Any = None,
    ) -> None: ...

    async def shutdown(self) -> None: ...


class NullObservation:
    def update(self, **kwargs: Any) -> None:
        del kwargs


class NullTracer:
    @contextmanager
    def trace(
        self,
        name: str,
        *,
        input: Any = None,
        session_id: str | None = None,
        user_id: str | None = None,
        metadata: Any = None,
        trace_id_seed: str | None = None,
    ) -> Iterator[Observation]:
        del name, input, session_id, user_id, metadata, trace_id_seed
        yield NullObservation()

    @contextmanager
    def span(
        self,
        name: str,
        *,
        input: Any = None,
        metadata: Any = None,
        as_type: ObservationType = "span",
    ) -> Iterator[Observation]:
        del name, input, metadata, as_type
        yield NullObservation()

    def generation(
        self,
        name: str,
        *,
        model: str | None,
        input: Any = None,
        metadata: Any = None,
    ) -> Any:
        return self.span(name, input=input, metadata=metadata)

    def schedule_flush(self) -> None:
        return

    def score_trace(
        self,
        trace_id_seed: str,
        *,
        name: str,
        value: bool | str,
        data_type: ScoreDataType = "BOOLEAN",
        score_id_seed: str | None = None,
        comment: str | None = None,
        metadata: Any = None,
    ) -> None:
        del trace_id_seed, name, value, data_type, score_id_seed, comment, metadata

    async def shutdown(self) -> None:
        return


class SafeObservation:
    def __init__(self, observation: Any, log: AppLogger) -> None:
        self._observation = observation
        self._log = log

    def update(self, **kwargs: Any) -> None:
        try:
            self._observation.update(
                **{key: compact_trace_value(value) for key, value in kwargs.items()}
            )
        except Exception as exc:
            self._log.warning("Langfuse observation update failed: %s", exc)


class LangfuseTracer:
    def __init__(self, client: Any, log: AppLogger | None = None) -> None:
        self._client = client
        self._log = (
            log.child("langfuse") if log is not None else get_logger("chatkb.langfuse")
        )
        self._flush_tasks: set[asyncio.Task[None]] = set()

    @contextmanager
    def trace(
        self,
        name: str,
        *,
        input: Any = None,
        session_id: str | None = None,
        user_id: str | None = None,
        metadata: Any = None,
        trace_id_seed: str | None = None,
    ) -> Iterator[Observation]:
        # Attach user/session before opening the root observation so Langfuse
        # tags the whole trace, not only later child spans.
        merged_metadata = _with_user_fields(metadata, user_id)
        attributes = None
        try:
            from langfuse import propagate_attributes

            attributes = propagate_attributes(
                session_id=session_id,
                user_id=user_id,
                trace_name=name,
                metadata=compact_trace_value(merged_metadata),
            )
            attributes.__enter__()
        except Exception as exc:
            attributes = None
            self._log.warning("Langfuse trace attributes failed: %s", exc)

        error: tuple[Any, Any, Any] = (None, None, None)
        try:
            with self._observation(
                name,
                input=input,
                metadata=merged_metadata,
                as_type="span",
                trace_id_seed=trace_id_seed,
            ) as observation:
                yield observation
        except BaseException:
            error = sys.exc_info()
            raise
        finally:
            if attributes is not None:
                try:
                    attributes.__exit__(*error)
                except Exception as exc:
                    self._log.warning(
                        "Langfuse trace attribute close failed: %s", exc
                    )

    def span(
        self,
        name: str,
        *,
        input: Any = None,
        metadata: Any = None,
        as_type: ObservationType = "span",
    ) -> Any:
        return self._observation(
            name,
            input=input,
            metadata=metadata,
            as_type=as_type,
        )

    def generation(
        self,
        name: str,
        *,
        model: str | None,
        input: Any = None,
        metadata: Any = None,
    ) -> Any:
        return self._observation(
            name,
            input=input,
            metadata=metadata,
            as_type="generation",
            model=model,
        )

    @contextmanager
    def _observation(
        self,
        name: str,
        *,
        input: Any,
        metadata: Any,
        as_type: ObservationType,
        model: str | None = None,
        trace_id_seed: str | None = None,
    ) -> Iterator[Observation]:
        manager = None
        try:
            trace_context = None
            if trace_id_seed:
                trace_context = {
                    "trace_id": self._client.create_trace_id(seed=trace_id_seed)
                }
            manager = self._client.start_as_current_observation(
                name=name,
                as_type=as_type,
                input=compact_trace_value(input),
                metadata=compact_trace_value(metadata),
                model=model,
                trace_context=trace_context,
            )
            raw = manager.__enter__()
            observation: Observation = SafeObservation(raw, self._log)
        except Exception as exc:
            self._log.warning("Langfuse observation start failed: %s", exc)
            yield NullObservation()
            return

        error: tuple[Any, Any, Any] = (None, None, None)
        try:
            yield observation
        except BaseException:
            error = sys.exc_info()
            raise
        finally:
            if manager is not None:
                try:
                    manager.__exit__(*error)
                except Exception as exc:
                    self._log.warning("Langfuse observation close failed: %s", exc)

    def score_trace(
        self,
        trace_id_seed: str,
        *,
        name: str,
        value: bool | str,
        data_type: ScoreDataType = "BOOLEAN",
        score_id_seed: str | None = None,
        comment: str | None = None,
        metadata: Any = None,
    ) -> None:
        try:
            trace_id = self._client.create_trace_id(seed=trace_id_seed)
            score_id = (
                self._client.create_trace_id(seed=score_id_seed)
                if score_id_seed
                else None
            )
            self._client.create_score(
                trace_id=trace_id,
                score_id=score_id,
                name=name,
                value=value,
                data_type=data_type,
                comment=comment,
                metadata=compact_trace_value(metadata),
            )
        except Exception as exc:
            self._log.warning("Langfuse trace score failed: %s", exc)

    def schedule_flush(self) -> None:
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(
                asyncio.to_thread(self._safe_flush),
                name="langfuse:flush",
            )
            self._flush_tasks.add(task)
            task.add_done_callback(self._flush_tasks.discard)
        except Exception as exc:
            self._log.warning("Langfuse flush scheduling failed: %s", exc)

    def _safe_flush(self) -> None:
        try:
            self._client.flush()
        except Exception as exc:
            self._log.warning("Langfuse flush failed: %s", exc)

    async def shutdown(self) -> None:
        try:
            await asyncio.to_thread(self._client.shutdown)
        except Exception as exc:
            self._log.warning("Langfuse shutdown failed: %s", exc)


_tracer: Tracer = NullTracer()


def create_tracer(settings: Settings, log: AppLogger | None = None) -> Tracer:
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return NullTracer()
    try:
        from langfuse import Langfuse

        kwargs: dict[str, Any] = {
            "public_key": settings.langfuse_public_key,
            "secret_key": settings.langfuse_secret_key,
        }
        if settings.langfuse_host:
            kwargs["host"] = settings.langfuse_host
        return LangfuseTracer(Langfuse(**kwargs), log=log)
    except Exception as exc:
        target = (
            log.child("langfuse")
            if log is not None
            else get_logger("chatkb.langfuse")
        )
        target.warning("Langfuse disabled after initialization failure: %s", exc)
        return NullTracer()


def get_tracer() -> Tracer:
    return _tracer


def set_tracer(tracer: Tracer) -> None:
    global _tracer
    _tracer = tracer


def _with_user_fields(metadata: Any, user_id: str | None) -> dict[str, Any]:
    merged: dict[str, Any] = dict(metadata) if isinstance(metadata, dict) else {}
    if user_id:
        # Auth subject is both the stable id and display name in this app.
        merged.setdefault("user_id", user_id)
        merged.setdefault("user_name", user_id)
    return merged


def compact_trace_value(value: Any, *, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        normalized = " ".join(value.split())
        if len(normalized) <= TRACE_TEXT_LIMIT:
            return normalized
        return normalized[: TRACE_TEXT_LIMIT - 1].rstrip() + "…"
    if depth >= 4:
        return compact_trace_value(str(value), depth=depth + 1)
    if isinstance(value, dict):
        items = list(value.items())[:TRACE_DICT_LIMIT]
        compacted = {
            str(key): compact_trace_value(item, depth=depth + 1)
            for key, item in items
        }
        if len(value) > TRACE_DICT_LIMIT:
            compacted["_truncated"] = True
        return compacted
    if isinstance(value, (list, tuple, set)):
        values = list(value)
        compacted_list = [
            compact_trace_value(item, depth=depth + 1)
            for item in values[:TRACE_LIST_LIMIT]
        ]
        if len(values) > TRACE_LIST_LIMIT:
            compacted_list.append("…")
        return compacted_list
    return compact_trace_value(str(value), depth=depth + 1)
