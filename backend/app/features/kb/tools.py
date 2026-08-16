from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import duckdb
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.citations import Citations, KbSource
from app.core.storage import Storage
from app.core.tools.protocol import ToolResult
from app.features.kb.db import KbRepository
from app.features.kb.ingestion.embed import Embedder
from app.features.kb.query import (
    QueryTimeoutError,
    QueryValidationError,
    query_tabular_file,
)
from app.features.kb.retrieve import hybrid_search

SNIPPET_LIMIT = 200
RESULT_CHAR_CAP = 4000
TABULAR_EXTENSIONS = frozenset({".csv", ".tsv", ".json"})
TRUNCATION_NOTE = "Results were truncated to fit the tool response limit."


class KbSearchTool:
    name = "kb_search"
    description = (
        "Search the attached knowledge base documents for relevant information. "
        "Use when the answer may be in the user's uploaded documents."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        embedder: Embedder,
        session_factory: async_sessionmaker[AsyncSession],
        collection_ids: list[str] | None = None,
    ) -> None:
        self._embedder = embedder
        self._session_factory = session_factory
        self._collection_ids = list(collection_ids or [])

    def scoped(self, collection_ids: list[str]) -> KbSearchTool:
        return KbSearchTool(
            self._embedder,
            self._session_factory,
            collection_ids,
        )

    async def run(self, args: dict[str, Any], citations: Citations) -> ToolResult:
        if not self._collection_ids:
            return ToolResult(
                content=json.dumps(
                    {"note": "no knowledge base is attached to this agent"}
                )
            )

        query = str(args.get("query") or "").strip()
        if not query:
            return ToolResult(
                content=json.dumps({"error": "search failed: query is required"})
            )

        async with self._session_factory() as db:
            hits = await hybrid_search(
                query,
                self._collection_ids,
                db=db,
                embedder=self._embedder,
                k=5,
                session_factory=self._session_factory,
            )

        results: list[dict[str, object]] = []
        traced_hits: list[dict[str, object]] = []
        source_parts: list[dict[str, Any]] = []
        known = citations.known_ids()
        for hit in hits:
            is_table_schema = hit.text.lstrip().startswith("type: table")
            source = KbSource(
                file_id=hit.file_id,
                filename=hit.filename,
                media_type=hit.mime_type,
                page=hit.page,
                anchor=hit.anchor,
                bbox=hit.bbox,
                collection_id=hit.collection_id,
                snippet=_snippet(hit.text),
            )
            cite_id = citations.add(source)
            tool_row = source.to_tool_result(cite_id)
            if is_table_schema:
                tool_row["schema"] = hit.text[:3000]
            results.append(tool_row)
            traced_hits.append(
                {
                    "chunk_id": hit.chunk_id,
                    "file_id": hit.file_id,
                    "filename": hit.filename,
                    "score": hit.score,
                    "page": hit.page,
                    "snippet": _snippet(hit.text),
                }
            )
            if cite_id not in known:
                source_parts.append(source.to_source_part(cite_id))
                known.add(cite_id)

        return ToolResult(
            content=_capped_json(results),
            source_parts=source_parts,
            trace_data={
                "query": query,
                "result_count": len(traced_hits),
                "hits": traced_hits,
            },
        )


# Each running-agent conversation receives a collection-scoped copy.
class QueryTableTool:
    name = "query_table"
    description = (
        "Run a read-only SQL query over a tabular knowledge-base file "
        "(CSV/TSV/JSON). Use this to filter, count, sort, or aggregate rows — "
        "e.g. find employees matching criteria, compute averages, rank by a "
        "column. The table is named `data`. You will be given the exact column "
        "names and types. Prefer this over kb_search when the question needs "
        "specific rows or computation from a table."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "The tabular file to query",
            },
            "sql": {
                "type": "string",
                "description": (
                    "A read-only SELECT query. The table is named `data`."
                ),
            },
        },
        "required": ["file_id", "sql"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage: Storage,
        collection_ids: list[str] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._collection_ids = list(collection_ids or [])

    def scoped(self, collection_ids: list[str]) -> QueryTableTool:
        return QueryTableTool(
            self._session_factory,
            self._storage,
            collection_ids,
        )

    async def run(
        self,
        args: dict[str, Any],
        citations: Citations,
    ) -> ToolResult:
        file_id = str(args.get("file_id") or "").strip()
        sql = str(args.get("sql") or "").strip()
        if not file_id or not sql:
            return _query_error("file_id and sql are required")
        if not self._collection_ids:
            return _query_error(
                "The file is not attached to the running agent."
            )

        async with self._session_factory() as session:
            row = await KbRepository(session).get_file(file_id)
            if row is None or row.collection_id not in self._collection_ids:
                return _query_error(
                    "The file is not attached to the running agent."
                )
            suffix = Path(row.filename).suffix.lower()
            if suffix not in TABULAR_EXTENSIONS:
                return _query_error(
                    "query_table only supports CSV, TSV, and tabular JSON files."
                )
            if suffix == ".json" and not (
                row.content_md or ""
            ).lstrip().startswith("type: table"):
                return _query_error(
                    "This JSON file is not a flat tabular array."
                )
            if row.status != "ready" or not row.s3_key:
                return _query_error("The tabular file is not ready to query.")
            filename = row.filename
            mime_type = row.mime_type
            collection_id = row.collection_id
            s3_key = row.s3_key

        try:
            data = await self._storage.get(s3_key)
        except Exception as exc:
            return _query_error(f"Could not fetch the table resource: {exc}")

        path: Path | None = None
        try:
            path = await asyncio.to_thread(
                _write_temp_file,
                data,
                Path(filename).suffix,
            )
            result = await query_tabular_file(
                path,
                mime_type=mime_type,
                sql=sql,
            )
        except (QueryValidationError, QueryTimeoutError, duckdb.Error) as exc:
            return _query_error(str(exc))
        finally:
            if path is not None:
                path.unlink(missing_ok=True)

        return _query_result(
            file_id=file_id,
            filename=filename,
            mime_type=mime_type,
            collection_id=collection_id,
            sql=sql,
            columns=result.columns,
            rows=result.rows,
            citations=citations,
        )


def _snippet(text: str, *, limit: int = SNIPPET_LIMIT) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _capped_json(results: list[dict[str, object]]) -> str:
    encoded = json.dumps(results)
    while len(encoded) > RESULT_CHAR_CAP and results:
        results.pop()
        encoded = json.dumps(results)
    return encoded


def _query_error(message: str) -> ToolResult:
    return ToolResult(content=json.dumps({"error": message}))


def _write_temp_file(data: bytes, suffix: str) -> Path:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(data)
        return Path(handle.name)


def _query_result(
    *,
    file_id: str,
    filename: str,
    mime_type: str,
    collection_id: str,
    sql: str,
    columns: list[str],
    rows: list[dict[str, object]],
    citations: Citations,
) -> ToolResult:
    payload_columns = list(columns)
    payload_rows: list[dict[str, object]] = []
    source_parts: list[dict[str, Any]] = []
    known = citations.known_ids()
    truncated = False
    query_key = hashlib.sha256(sql.encode()).hexdigest()[:8]
    for index, row in enumerate(rows, start=1):
        anchor = _row_anchor(row, index, query_key)
        source = KbSource(
            file_id=file_id,
            filename=filename,
            media_type=mime_type,
            page=None,
            anchor=anchor,
            bbox=None,
            collection_id=collection_id,
            snippet=_row_snippet(row),
        )
        cite_id = citations.add(source)
        candidate = {**row, "cite_id": cite_id}
        payload_rows.append(candidate)
        candidate_payload = {
            "columns": payload_columns,
            "rows": payload_rows,
            "truncated": True,
            "note": TRUNCATION_NOTE,
        }
        if (
            len(json.dumps(candidate_payload, default=str))
            > RESULT_CHAR_CAP
        ):
            payload_rows.pop()
            truncated = True
            break
        if cite_id not in known:
            source_parts.append(source.to_source_part(cite_id))
            known.add(cite_id)

    if len(payload_rows) < len(rows):
        truncated = True
    payload: dict[str, Any] = {
        "columns": payload_columns,
        "rows": payload_rows,
        "truncated": truncated,
    }
    if truncated:
        payload["note"] = TRUNCATION_NOTE
    while (
        len(json.dumps(payload, default=str)) > RESULT_CHAR_CAP
        and payload_columns
    ):
        payload_columns.pop()
        payload["truncated"] = True
        payload["note"] = TRUNCATION_NOTE
    return ToolResult(
        content=json.dumps(payload, default=str),
        source_parts=source_parts,
        trace_data={
            "sql": sql,
            "row_count": len(payload_rows),
            "columns": payload_columns,
            "sample_rows": payload_rows[:3],
            "truncated": truncated,
        },
    )


def _row_anchor(
    row: dict[str, object],
    index: int,
    query_key: str,
) -> str:
    key = next(
        (
            column
            for column in row
            if column.lower() == "id" or column.lower().endswith("_id")
        ),
        None,
    )
    if key is not None:
        value = row.get(key)
        if value is not None and value != "":
            return f"row:{key}:{value}"
    return f"query:{query_key}:row:{index}"


def _row_snippet(row: dict[str, object]) -> str:
    snippet = ", ".join(f"{key}={value}" for key, value in row.items())
    return _snippet(snippet)
