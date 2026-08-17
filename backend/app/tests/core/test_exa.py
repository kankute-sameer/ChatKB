import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.citations import Citations
from app.core.exa import ExaClient
from app.features.conversations.tools.web_search import WebSearchTool


@pytest.mark.asyncio
async def test_exa_retries_transient_failure(
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
        return httpx.Response(200, json={"results": []})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = ExaClient(api_key="test", http=http)

    assert await client.search("query") == {"results": []}
    assert calls == 2
    sleep.assert_awaited_once_with(1.0)
    await http.aclose()


@pytest.mark.asyncio
async def test_web_search_degrades_gracefully_after_exa_retry_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep = AsyncMock()
    monkeypatch.setattr("app.core.retry.asyncio.sleep", sleep)
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, text="temporarily unavailable")

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tool = WebSearchTool(ExaClient(api_key="test", http=http))

    result = await tool.run({"query": "query"}, Citations())

    assert calls == 5
    assert "search failed" in json.loads(result.content)["error"]
    assert [call.args[0] for call in sleep.await_args_list] == [1.0, 2.0, 4.0, 8.0]
    await http.aclose()
