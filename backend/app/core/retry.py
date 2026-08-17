from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx

logger = logging.getLogger("chatkb.retry")

_TRANSIENT_STATUS_CODES = {500, 502, 503, 504}


async def retry_async[T](
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 16.0,
    retry_on: Callable[[Exception], bool],
) -> T:
    """Call fn(), retrying with exponential backoff when retry_on(exc) is True."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if base_delay < 0 or max_delay < 0:
        raise ValueError("retry delays must be non-negative")

    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except Exception as exc:
            if attempt == max_attempts or not retry_on(exc):
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            logger.warning(
                "Provider call failed; retrying attempt %s/%s in %.1fs: %s",
                attempt + 1,
                max_attempts,
                delay,
                exc,
            )
            await asyncio.sleep(delay)

    raise RuntimeError("retry loop exited unexpectedly")


def is_rate_limit(exc: Exception) -> bool:
    """Return whether an exception represents a provider rate limit."""
    if _status_code(exc) == 429:
        return True
    message = str(exc).lower()
    return any(
        marker in message for marker in ("429", "resource_exhausted", "rate limit")
    )


def is_transient(exc: Exception) -> bool:
    """Return whether an exception is safe to retry as a transient failure."""
    if is_rate_limit(exc) or _status_code(exc) in _TRANSIENT_STATUS_CODES:
        return True
    return isinstance(
        exc,
        (
            httpx.NetworkError,
            httpx.TimeoutException,
            ConnectionError,
            TimeoutError,
        ),
    )


def _status_code(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    candidates = (
        getattr(exc, "status_code", None),
        getattr(exc, "code", None),
        getattr(response, "status_code", None),
    )
    for candidate in candidates:
        if isinstance(candidate, bool):
            continue
        if isinstance(candidate, int):
            return candidate
        value = getattr(candidate, "value", None)
        if isinstance(value, int):
            return value
        if isinstance(candidate, str) and candidate.isdigit():
            return int(candidate)
    return None
