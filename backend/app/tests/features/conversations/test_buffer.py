import asyncio

import pytest
from app.features.conversations.buffer import InMemoryStreamStore, ResponseBuffer


@pytest.mark.asyncio
async def test_two_readers_at_different_positions_receive_all_events() -> None:
    store = InMemoryStreamStore()
    buffer = store.create("resp_1")

    first: list[str] = []
    second: list[str] = []

    async def collect(after: int, into: list[str]) -> None:
        async for _event_id, payload in buffer.read_from(after):
            into.append(str(payload["type"]))

    reader_a = asyncio.create_task(collect(0, first))
    await asyncio.sleep(0)
    first_id = buffer.append({"type": "one"})
    reader_b = asyncio.create_task(collect(first_id, second))
    await asyncio.sleep(0)
    buffer.append({"type": "two"})
    buffer.append({"type": "three"})
    buffer.finish()
    await asyncio.wait_for(reader_a, timeout=1)
    await asyncio.wait_for(reader_b, timeout=1)
    assert first == ["one", "two", "three"]
    assert second == ["two", "three"]


@pytest.mark.asyncio
async def test_late_reader_gets_backlog_then_live_events() -> None:
    store = InMemoryStreamStore()
    buffer = store.create("resp_2")
    buffer.append({"type": "backlog"})
    collected: list[str] = []

    async def collect() -> None:
        async for _event_id, payload in buffer.read_from(0):
            collected.append(str(payload["type"]))

    reader = asyncio.create_task(collect())
    await asyncio.sleep(0)
    buffer.append({"type": "live"})
    buffer.finish()
    await asyncio.wait_for(reader, timeout=1)
    assert collected == ["backlog", "live"]


@pytest.mark.asyncio
async def test_read_from_terminates_when_finish_is_called() -> None:
    buffer = ResponseBuffer(InMemoryStreamStore().counter)
    buffer.append({"type": "start"})
    buffer.finish()
    events = [payload async for _event_id, payload in buffer.read_from(0)]
    assert [event["type"] for event in events] == ["start"]
