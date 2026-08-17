from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.retry import is_rate_limit, is_transient, retry_async


class _StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"provider returned {status_code}")


@pytest.mark.asyncio
async def test_retry_async_succeeds_without_sleeping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep = AsyncMock()
    monkeypatch.setattr("app.core.retry.asyncio.sleep", sleep)

    assert await retry_async(_return_ok, retry_on=lambda _exc: True) == "ok"
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_async_retries_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep = AsyncMock()
    monkeypatch.setattr("app.core.retry.asyncio.sleep", sleep)
    calls = 0

    async def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _StatusError(429)
        return "ok"

    assert await retry_async(flaky, retry_on=is_rate_limit) == "ok"
    assert calls == 2
    sleep.assert_awaited_once_with(1.0)


@pytest.mark.asyncio
async def test_retry_async_exhausts_and_caps_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep = AsyncMock()
    monkeypatch.setattr("app.core.retry.asyncio.sleep", sleep)
    error = _StatusError(503)

    async def fail() -> None:
        raise error

    with pytest.raises(_StatusError) as caught:
        await retry_async(
            fail,
            max_attempts=6,
            base_delay=1.0,
            max_delay=4.0,
            retry_on=is_transient,
        )

    assert caught.value is error
    assert [call.args[0] for call in sleep.await_args_list] == [1.0, 2.0, 4.0, 4.0, 4.0]


@pytest.mark.asyncio
async def test_retry_async_does_not_retry_non_retryable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep = AsyncMock()
    monkeypatch.setattr("app.core.retry.asyncio.sleep", sleep)
    calls = 0

    async def fail() -> None:
        nonlocal calls
        calls += 1
        raise _StatusError(400)

    with pytest.raises(_StatusError):
        await retry_async(fail, retry_on=is_transient)

    assert calls == 1
    sleep.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "rate_limited", "transient"),
    [
        (_StatusError(429), True, True),
        (_StatusError(500), False, True),
        (_StatusError(503), False, True),
        (_StatusError(400), False, False),
        (_StatusError(401), False, False),
        (RuntimeError("RESOURCE_EXHAUSTED"), True, True),
        (httpx.ReadTimeout("timed out"), False, True),
        (httpx.ConnectError("connection failed"), False, True),
    ],
)
def test_retry_predicates(
    error: Exception,
    rate_limited: bool,
    transient: bool,
) -> None:
    assert is_rate_limit(error) is rate_limited
    assert is_transient(error) is transient


async def _return_ok() -> str:
    return "ok"
