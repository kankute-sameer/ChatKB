from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.core.config import Settings
from app.core.tracing import (
    LangfuseTracer,
    NullTracer,
    compact_trace_value,
    create_tracer,
)


def test_tracing_is_disabled_without_keys() -> None:
    settings = cast(
        Settings,
        SimpleNamespace(
            langfuse_public_key="",
            langfuse_secret_key="",
            langfuse_host="",
        ),
    )

    tracer = create_tracer(settings)

    assert isinstance(tracer, NullTracer)
    with tracer.trace(
        "conversation.turn",
        session_id="conv_1",
        user_id="alice",
    ) as trace:
        trace.update(output="still works")


def test_large_trace_payloads_are_truncated() -> None:
    compacted = compact_trace_value(
        {
            "output": "x" * 2_000,
            "rows": [{"value": "y" * 1_000} for _ in range(30)],
        }
    )

    assert isinstance(compacted, dict)
    assert len(str(compacted["output"])) == 500
    assert str(compacted["output"]).endswith("…")
    assert isinstance(compacted["rows"], list)
    assert len(compacted["rows"]) == 21


class _BrokenObservation:
    def update(self, **_kwargs: Any) -> None:
        raise RuntimeError("update failed")


class _BrokenManager:
    def __enter__(self) -> _BrokenObservation:
        return _BrokenObservation()

    def __exit__(self, *_args: Any) -> None:
        raise RuntimeError("close failed")


class _BrokenClient:
    def start_as_current_observation(self, **_kwargs: Any) -> _BrokenManager:
        return _BrokenManager()


class _BrokenAttributes:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_args: Any) -> None:
        raise RuntimeError("attribute close failed")


def test_tracing_layer_exceptions_do_not_escape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "langfuse.propagate_attributes",
        lambda **_kwargs: _BrokenAttributes(),
    )
    tracer = LangfuseTracer(_BrokenClient())
    completed = False

    with tracer.trace("conversation.turn") as trace:
        trace.update(output="response")
        completed = True

    assert completed


def test_application_exception_is_not_swallowed_when_tracing_close_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "langfuse.propagate_attributes",
        lambda **_kwargs: _BrokenAttributes(),
    )
    tracer = LangfuseTracer(_BrokenClient())

    with pytest.raises(ValueError, match="generation failed"):
        with tracer.trace("conversation.turn"):
            raise ValueError("generation failed")
