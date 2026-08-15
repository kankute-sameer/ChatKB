from types import SimpleNamespace

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
