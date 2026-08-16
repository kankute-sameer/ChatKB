from __future__ import annotations

import asyncio
import re
import threading
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

MAX_QUERY_ROWS = 100
MAX_SQL_CHARS = 10_000
QUERY_TIMEOUT_SECONDS = 5.0
MAX_CONCURRENT_QUERIES = 4
_QUERY_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_QUERIES)
_BLOCKED_TOKEN_RE = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|COPY|INSTALL|LOAD|"
    r"PRAGMA|SET|CALL|EXPORT|IMPORT|READ_CSV(?:_AUTO)?|"
    r"READ_JSON(?:_AUTO)?|READ_PARQUET|READ_TEXT|GLOB)\b",
    re.IGNORECASE,
)
_CTE_RE = re.compile(
    r"(?:\bWITH\b|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(",
    re.IGNORECASE,
)
_TABLE_REF_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+[\"`]?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)


class QueryValidationError(ValueError):
    pass


class QueryTimeoutError(RuntimeError):
    pass


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[dict[str, object]]


def validate_read_only_sql(sql: str) -> str:
    query = sql.strip()
    if not query:
        raise QueryValidationError(
            "SQL is required. Write a plain SELECT ... FROM data query."
        )
    if len(query) > MAX_SQL_CHARS:
        raise QueryValidationError(
            f"SQL exceeds the {MAX_SQL_CHARS}-character limit."
        )
    try:
        statements = duckdb.extract_statements(query)
    except duckdb.Error as exc:
        raise QueryValidationError(f"Invalid SQL: {exc}") from exc
    if len(statements) != 1:
        raise QueryValidationError(
            "Only one SQL statement is allowed. "
            "Write a plain SELECT ... FROM data query."
        )
    if statements[0].type != duckdb.StatementType.SELECT:
        raise QueryValidationError(
            "Only read-only SELECT or WITH ... SELECT queries are allowed."
        )
    blocked = _BLOCKED_TOKEN_RE.search(query)
    if blocked is not None:
        raise QueryValidationError(
            f"`{blocked.group(0)}` is not allowed. "
            "Query only the table named data."
        )

    cte_names = {name.lower() for name in _CTE_RE.findall(query)}
    references = [name.lower() for name in _TABLE_REF_RE.findall(query)]
    if "data" not in references:
        raise QueryValidationError(
            "The query must read from the table named data."
        )
    invalid_references = [
        name for name in references if name != "data" and name not in cte_names
    ]
    if invalid_references:
        raise QueryValidationError(
            f"Only the table named data may be queried; "
            f"`{invalid_references[0]}` is not allowed."
        )
    return str(statements[0].query).strip().rstrip(";")


async def query_tabular_file(
    path: Path,
    *,
    mime_type: str,
    sql: str,
    timeout_seconds: float = QUERY_TIMEOUT_SECONDS,
) -> QueryResult:
    query = validate_read_only_sql(sql)
    await _QUERY_SEMAPHORE.acquire()
    try:
        connection = await asyncio.to_thread(
            _load_table,
            path,
            mime_type,
            timeout_seconds,
        )
        task = asyncio.create_task(
            asyncio.to_thread(_execute, connection, query)
        )
        try:
            return await asyncio.wait_for(
                asyncio.shield(task),
                timeout_seconds,
            )
        except TimeoutError as exc:
            await asyncio.to_thread(connection.interrupt)
            try:
                await task
            except duckdb.Error:
                pass
            raise QueryTimeoutError(
                f"Query exceeded the {timeout_seconds:g}-second timeout"
            ) from exc
        finally:
            await asyncio.to_thread(connection.close)
    finally:
        _QUERY_SEMAPHORE.release()


def _load_table(
    path: Path,
    mime_type: str,
    timeout_seconds: float = QUERY_TIMEOUT_SECONDS,
) -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    interrupted = threading.Event()

    def interrupt() -> None:
        interrupted.set()
        connection.interrupt()

    timer = threading.Timer(timeout_seconds, interrupt)
    timer.daemon = True
    timer.start()
    try:
        connection.execute("SET memory_limit='256MB'")
        connection.execute("SET threads=1")
        connection.execute("SET max_temp_directory_size='0B'")
        connection.execute("SET max_expression_depth=200")
        connection.execute("SET autoinstall_known_extensions=false")
        connection.execute("SET autoload_known_extensions=false")
        suffix = path.suffix.lower()
        if suffix == ".json" or mime_type in {"application/json", "text/json"}:
            connection.execute(
                "CREATE TABLE data AS "
                "SELECT * FROM read_json_auto(?, format='array')",
                [str(path)],
            )
        elif suffix == ".tsv" or mime_type == "text/tab-separated-values":
            connection.execute(
                "CREATE TABLE data AS "
                "SELECT * FROM read_csv_auto(?, delim='\\t', header=true)",
                [str(path)],
            )
        else:
            connection.execute(
                "CREATE TABLE data AS SELECT * FROM read_csv_auto(?)",
                [str(path)],
            )
        connection.execute("SET enable_external_access=false")
        connection.execute("SET lock_configuration=true")
        return connection
    except Exception as exc:
        connection.close()
        if interrupted.is_set():
            raise QueryTimeoutError(
                f"Table load exceeded the {timeout_seconds:g}-second timeout"
            ) from exc
        raise
    finally:
        timer.cancel()


def _execute(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> QueryResult:
    bounded = (
        "SELECT * FROM ("
        f"{query}"
        f") AS query_result LIMIT {MAX_QUERY_ROWS}"
    )
    cursor = connection.execute(bounded)
    columns = [str(item[0]) for item in (cursor.description or [])]
    rows = [
        {
            column: _json_value(value)
            for column, value in zip(columns, row, strict=True)
        }
        for row in cursor.fetchmany(MAX_QUERY_ROWS)
    ]
    return QueryResult(columns=columns, rows=rows)


def _json_value(value: Any) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (list, dict)):
        return value
    return str(value)
