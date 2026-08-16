from __future__ import annotations

import json
import logging
from typing import Any

from app.core.citations import Citations, WebSource
from app.core.exa import ExaClient
from app.core.tools.protocol import ToolResult

logger = logging.getLogger(__name__)

SNIPPET_LIMIT = 200
RESULT_CHAR_CAP = 4000


class WebSearchTool:
    name = "web_search"
    description = (
        "Search the web for current information. Use for recent events, "
        "current data, or anything you may not know."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "num_results": {"type": "integer", "default": 5},
        },
        "required": ["query"],
    }

    def __init__(self, exa: ExaClient) -> None:
        self._exa = exa

    async def run(self, args: dict[str, Any], citations: Citations) -> ToolResult:
        # Tool output is untrusted: web pages may try to manipulate the model.
        # Truncation bounds how much of that text reaches the context.
        query = str(args.get("query") or "").strip()
        if not query:
            return ToolResult(
                content=json.dumps({"error": "search failed: query is required"})
            )
        num_results = _num_results(args.get("num_results"))
        try:
            payload = await self._exa.search(query, num_results=num_results)
        except Exception as exc:
            logger.warning("Exa search failed: %s", exc)
            return ToolResult(content=json.dumps({"error": f"search failed: {exc}"}))

        results = payload.get("results")
        if not isinstance(results, list):
            results = []

        tool_results: list[dict[str, object]] = []
        source_parts: list[dict[str, Any]] = []
        known = citations.known_ids()
        for item in results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or item.get("id") or "").strip()
            if not url:
                continue
            title = str(item.get("title") or url)
            snippet = _snippet(item.get("highlights"))
            published = item.get("publishedDate")
            published_date = published if isinstance(published, str) else None
            source = WebSource(
                url=url,
                title=title,
                snippet=snippet,
                published_date=published_date,
            )
            cite_id = citations.add(source)
            tool_results.append(source.to_tool_result(cite_id))
            if cite_id not in known:
                source_parts.append(source.to_source_part(cite_id))
                known.add(cite_id)

        return ToolResult(
            content=_capped_json(tool_results),
            source_parts=source_parts,
            trace_data={
                "query": query,
                "result_count": len(tool_results),
                "titles": [str(item.get("title") or "") for item in tool_results],
            },
        )


def _num_results(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 5
    return max(1, min(value, 10))


def _snippet(highlights: object) -> str:
    chunks: list[str] = []
    if isinstance(highlights, list):
        for item in highlights:
            if isinstance(item, str) and item.strip():
                chunks.append(" ".join(item.split()))
    text = " ".join(chunks).strip()
    if len(text) <= SNIPPET_LIMIT:
        return text
    return text[: SNIPPET_LIMIT - 1].rstrip() + "…"


def _capped_json(results: list[dict[str, object]]) -> str:
    encoded = json.dumps(results)
    while len(encoded) > RESULT_CHAR_CAP and results:
        results.pop()
        encoded = json.dumps(results)
    if len(encoded) > RESULT_CHAR_CAP:
        return json.dumps([])
    return encoded
