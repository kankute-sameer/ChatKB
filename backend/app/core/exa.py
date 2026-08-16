import json
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.log import AppLogger, get_logger

EXA_SEARCH_URL = "https://api.exa.ai/search"


class ExaClient:
    """httpx client for Exa search. Create once at startup."""

    def __init__(
        self,
        api_key: str,
        http: httpx.AsyncClient | None = None,
        log: AppLogger | None = None,
    ) -> None:
        self._api_key = api_key
        self._http = http
        self._owns_http = http is None
        self.log = log.child("exa") if log is not None else get_logger("chatkb.exa")

    @classmethod
    def from_settings(
        cls,
        settings: Settings | None = None,
        log: AppLogger | None = None,
    ) -> "ExaClient":
        cfg = settings or get_settings()
        return cls(api_key=cfg.exa_api_key, log=log)

    async def aclose(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(20.0))
        return self._http

    async def search(
        self,
        query: str,
        num_results: int = 5,
    ) -> dict[str, Any]:
        client = await self._client()
        headers = {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        body = {
            "query": query,
            "type": "auto",
            "numResults": num_results,
            "contents":{"highlights":True}
        }
        self.log.curl("POST", EXA_SEARCH_URL, headers, body)
        response = await client.post(
            EXA_SEARCH_URL,
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        payload: object = response.json()
        self.log.debug(
            "EXA SEARCH RESPONSE: %s", json.dumps(payload, ensure_ascii=False, default=str)
        )
        if not isinstance(payload, dict):
            raise ValueError("unexpected Exa response")
        return payload
