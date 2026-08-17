from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.features.kb.ingestion.embed import GeminiEmbedder
from app.features.kb.models import EMBEDDING_DIMENSIONS


class _FakeModels:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def embed_content(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        contents = kwargs["contents"]
        assert isinstance(contents, list)
        return SimpleNamespace(
            embeddings=[
                SimpleNamespace(values=[0.2] * EMBEDDING_DIMENSIONS) for _ in contents
            ]
        )


class _FakeClient:
    def __init__(self) -> None:
        self.aio = SimpleNamespace(models=_FakeModels())


class _RateLimitError(Exception):
    status_code = 429


class _FlakyModels:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    async def embed_content(self, **kwargs: object) -> SimpleNamespace:
        self.calls += 1
        if self.calls <= self.failures:
            raise _RateLimitError("rate limited")
        contents = kwargs["contents"]
        assert isinstance(contents, list)
        return SimpleNamespace(
            embeddings=[
                SimpleNamespace(values=[0.2] * EMBEDDING_DIMENSIONS) for _ in contents
            ]
        )


@pytest.mark.asyncio
async def test_embed_uses_retrieval_document_and_1536_dimensions() -> None:
    client = _FakeClient()
    embedder = GeminiEmbedder(api_key="test", client=client)
    vectors = await embedder.embed(["chunk one", "chunk two"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 1536
    call = client.aio.models.calls[0]
    assert call["model"] == "gemini-embedding-001"
    config = call["config"]
    assert config.task_type == "RETRIEVAL_DOCUMENT"
    assert config.output_dimensionality == 1536


@pytest.mark.asyncio
async def test_embed_retries_rate_limit_then_returns_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep = AsyncMock()
    monkeypatch.setattr("app.core.retry.asyncio.sleep", sleep)
    models = _FlakyModels(failures=1)
    client = SimpleNamespace(aio=SimpleNamespace(models=models))

    vectors = await GeminiEmbedder(api_key="test", client=client).embed(["chunk"])

    assert len(vectors) == 1
    assert models.calls == 2
    sleep.assert_awaited_once_with(1.0)


@pytest.mark.asyncio
async def test_embed_raises_after_five_rate_limit_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep = AsyncMock()
    monkeypatch.setattr("app.core.retry.asyncio.sleep", sleep)
    models = _FlakyModels(failures=5)
    client = SimpleNamespace(aio=SimpleNamespace(models=models))

    with pytest.raises(_RateLimitError):
        await GeminiEmbedder(api_key="test", client=client).embed(["chunk"])

    assert models.calls == 5
    assert [call.args[0] for call in sleep.await_args_list] == [1.0, 2.0, 4.0, 8.0]
