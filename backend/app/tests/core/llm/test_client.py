import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from PIL import Image

from app.core.llm.client import LLMClient, _ResponsesMapper


class _FailingAfterFirstEvent(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield (
            b'data: {"type":"response.output_text.delta",'
            b'"item_id":"msg_1","delta":"Hello"}\n\n'
        )
        raise httpx.ReadError("stream disconnected")

    async def aclose(self) -> None:
        return None


def test_stream_body_includes_reasoning() -> None:
    client = LLMClient(
        api_key="k",
        base_url="https://example.test/v1",
        model="gpt-5.6-luna",
        title_model="gpt-5.6-luna",
        reasoning_effort="medium",
        reasoning_summary="auto",
    )
    body = client._body([], model="gpt-5.6-luna", stream=True, with_reasoning=True)
    assert body["reasoning"] == {"effort": "medium", "summary": "auto"}


def test_complete_body_omits_reasoning() -> None:
    client = LLMClient(
        api_key="k",
        base_url="https://example.test/v1",
        model="gpt-5.6-luna",
        title_model="gpt-5.6-luna",
    )
    body = client._body([], model="gpt-5.6-luna", stream=False)
    assert "reasoning" not in body


def test_reasoning_off_omits_field() -> None:
    client = LLMClient(
        api_key="k",
        base_url="https://example.test/v1",
        model="gpt-5.6-luna",
        title_model="gpt-5.6-luna",
        reasoning_effort="off",
    )
    body = client._body([], model="gpt-5.6-luna", stream=True, with_reasoning=True)
    assert "reasoning" not in body


@pytest.mark.asyncio
async def test_describe_image_uses_openai_responses_multimodal_input() -> None:
    requests: list[Any] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "A lighthouse with green bands.",
                            }
                        ],
                    }
                ]
            },
        )

    http = httpx.AsyncClient(
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    client = LLMClient(
        api_key="k",
        base_url="https://example.test/v1",
        model="gpt-5.6-luna",
        title_model="gpt-5.6-luna",
        vision_model="gpt-5.6-luna",
        http=http,
    )

    description = await client.describe_image(Image.new("RGB", (100, 80), "green"))
    await http.aclose()

    assert description == "A lighthouse with green bands."
    assert requests[0]["model"] == "gpt-5.6-luna"
    content = requests[0]["input"][0]["content"]
    assert content[0]["type"] == "input_text"
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_describe_image_failure_returns_empty_string() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="provider failed")

    http = httpx.AsyncClient(
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    client = LLMClient(
        api_key="k",
        base_url="https://example.test/v1",
        model="gpt-5.6-luna",
        title_model="gpt-5.6-luna",
        http=http,
    )
    assert await client.describe_image(Image.new("RGB", (100, 80))) == ""
    await http.aclose()


@pytest.mark.asyncio
async def test_complete_retries_rate_limit_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep = AsyncMock()
    monkeypatch.setattr("app.core.retry.asyncio.sleep", sleep)
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, text="rate limited")
        return httpx.Response(200, json={"output_text": "Recovered"})

    http = httpx.AsyncClient(
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    client = LLMClient(
        api_key="k",
        base_url="https://example.test/v1",
        model="gpt-5.6-luna",
        title_model="gpt-5.6-luna",
        http=http,
    )

    assert await client.complete([]) == "Recovered"
    assert calls == 2
    sleep.assert_awaited_once_with(1.0)
    await http.aclose()


@pytest.mark.asyncio
async def test_stream_retries_failure_before_first_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep = AsyncMock()
    monkeypatch.setattr("app.core.retry.asyncio.sleep", sleep)
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, text="temporarily unavailable")
        return httpx.Response(
            200,
            content=(
                b'data: {"type":"response.output_text.delta",'
                b'"item_id":"msg_1","delta":"Hello"}\n\n'
                b'data: {"type":"response.output_text.done","item_id":"msg_1"}\n\n'
            ),
        )

    http = httpx.AsyncClient(
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    client = LLMClient(
        api_key="k",
        base_url="https://example.test/v1",
        model="gpt-5.6-luna",
        title_model="gpt-5.6-luna",
        http=http,
    )

    events = [event async for event in client.stream([])]

    assert calls == 2
    assert [
        event.get("delta") for event in events if event["type"] == "text-delta"
    ] == ["Hello"]
    sleep.assert_awaited_once_with(1.0)
    await http.aclose()


@pytest.mark.asyncio
async def test_stream_does_not_retry_after_first_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep = AsyncMock()
    monkeypatch.setattr("app.core.retry.asyncio.sleep", sleep)
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, stream=_FailingAfterFirstEvent())

    http = httpx.AsyncClient(
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    client = LLMClient(
        api_key="k",
        base_url="https://example.test/v1",
        model="gpt-5.6-luna",
        title_model="gpt-5.6-luna",
        http=http,
    )

    events = [event async for event in client.stream([])]

    assert calls == 1
    assert [
        event.get("delta") for event in events if event["type"] == "text-delta"
    ] == ["Hello"]
    assert [event["type"] for event in events].count("error") == 1
    sleep.assert_not_awaited()
    await http.aclose()


def test_mapper_streams_reasoning_then_text() -> None:
    mapper = _ResponsesMapper()
    events = [
        *mapper.handle(
            {
                "type": "response.reasoning_summary_text.delta",
                "item_id": "rs_1",
                "summary_index": 0,
                "delta": "Consider ",
            }
        ),
        *mapper.handle(
            {
                "type": "response.reasoning_summary_text.delta",
                "item_id": "rs_1",
                "summary_index": 0,
                "delta": "the question.",
            }
        ),
        *mapper.handle(
            {
                "type": "response.reasoning_summary_text.done",
                "item_id": "rs_1",
                "summary_index": 0,
                "text": "Consider the question.",
            }
        ),
        *mapper.handle(
            {
                "type": "response.output_text.delta",
                "item_id": "msg_1",
                "delta": "Hello",
            }
        ),
        *mapper.handle({"type": "response.output_text.done", "item_id": "msg_1"}),
    ]
    types = [event["type"] for event in events]
    assert types == [
        "reasoning-start",
        "reasoning-delta",
        "reasoning-delta",
        "reasoning-end",
        "text-start",
        "text-delta",
        "text-end",
    ]
    reasoning = "".join(
        str(event.get("delta") or "")
        for event in events
        if event["type"] == "reasoning-delta"
    )
    assert reasoning == "Consider the question."


def test_mapper_keeps_function_name_when_done_event_omits_it() -> None:
    mapper = _ResponsesMapper()
    events = [
        *mapper.handle(
            {
                "type": "response.output_item.added",
                "item": {
                    "id": "fc_1",
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "web_search",
                    "arguments": "",
                },
            }
        ),
        *mapper.handle(
            {
                "type": "response.function_call_arguments.done",
                "item_id": "fc_1",
                "call_id": "call_1",
                "arguments": '{"query":"latest news"}',
            }
        ),
    ]
    available = [event for event in events if event["type"] == "tool-input-available"]
    assert len(available) == 1
    assert available[0]["toolName"] == "web_search"
    assert available[0]["toolCallId"] == "call_1"
    assert available[0]["input"] == {"query": "latest news"}


def test_mapper_emits_usage_and_finish_metadata() -> None:
    events = _ResponsesMapper().handle(
        {
            "type": "response.completed",
            "response": {
                "model": "gpt-5.6-luna",
                "status": "completed",
                "usage": {
                    "input_tokens": 120,
                    "output_tokens": 30,
                    "total_tokens": 150,
                },
            },
        }
    )

    assert events == [
        {
            "type": "response-metadata",
            "model": "gpt-5.6-luna",
            "finishReason": "completed",
            "usage": {
                "input_tokens": 120,
                "output_tokens": 30,
                "total_tokens": 150,
            },
        }
    ]
