from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, Protocol

from app.core.config import Settings, get_settings
from app.features.kb.models import EMBEDDING_DIMENSIONS

EMBEDDING_MODEL = "gemini-embedding-001"
DOCUMENT_TASK_TYPE = "RETRIEVAL_DOCUMENT"
QUERY_TASK_TYPE = "RETRIEVAL_QUERY"
BATCH_SIZE = 100
MAX_RETRIES = 5


class Embedder(Protocol):
    async def embed(
        self,
        texts: Sequence[str],
        *,
        task_type: str = DOCUMENT_TASK_TYPE,
    ) -> list[list[float]]: ...


class GeminiEmbedder:
    def __init__(
        self,
        api_key: str = "",
        model: str = EMBEDDING_MODEL,
        dimensions: int = EMBEDDING_DIMENSIONS,
        client: Any | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> GeminiEmbedder:
        cfg = settings or get_settings()
        client: Any | None = None
        if cfg.gemini_api_key:
            from google import genai

            client = genai.Client(api_key=cfg.gemini_api_key)
        return cls(
            api_key=cfg.gemini_api_key,
            model=cfg.embedding_model,
            dimensions=cfg.embedding_dimensions,
            client=client,
        )

    def _ensure_client(self) -> Any:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("GEMINI_API_KEY is not configured")
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def embed(
        self,
        texts: Sequence[str],
        *,
        task_type: str = DOCUMENT_TASK_TYPE,
    ) -> list[list[float]]:
        if not texts:
            return []
        client = self._ensure_client()
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = list(texts[start : start + BATCH_SIZE])
            vectors.extend(await self._embed_batch(client, batch, task_type))
        return vectors

    async def _embed_batch(
        self,
        client: Any,
        texts: list[str],
        task_type: str,
    ) -> list[list[float]]:
        from google.genai import types

        config = types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=self._dimensions,
        )
        delay = 1.0
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                result = await client.aio.models.embed_content(
                    model=self._model,
                    contents=texts,
                    config=config,
                )
                embeddings = getattr(result, "embeddings", None) or []
                vectors: list[list[float]] = []
                for item in embeddings:
                    values = getattr(item, "values", None) or []
                    vectors.append([float(x) for x in values])
                if len(vectors) != len(texts):
                    raise RuntimeError(
                        "Gemini returned "
                        f"{len(vectors)} embeddings for {len(texts)} texts"
                    )
                return vectors
            except Exception as exc:
                last_error = exc
                if attempt < MAX_RETRIES - 1 and _is_rate_limit(exc):
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 16)
                    continue
                raise
        raise RuntimeError("Gemini embedding failed") from last_error


def _is_rate_limit(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status == 429:
        return True
    text = str(exc).lower()
    return "429" in text or "resource_exhausted" in text or "rate limit" in text
