from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest
from fastapi import FastAPI

from app.core.citations import Citations
from app.core.ids import new_id
from app.features.kb import query as query_module
from app.features.kb.models import Collection, KbFile
from app.features.kb.query import (
    QueryTimeoutError,
    QueryValidationError,
    _load_table,
    query_tabular_file,
    validate_read_only_sql,
)
from app.features.kb.tools import QueryTableTool
from app.tests.fakes import FakeStorage


def test_select_and_with_select_are_allowed() -> None:
    assert validate_read_only_sql("SELECT * FROM data") == "SELECT * FROM data"
    assert (
        validate_read_only_sql(
            "WITH filtered AS (SELECT * FROM data) SELECT * FROM filtered"
        )
        == "WITH filtered AS (SELECT * FROM data) SELECT * FROM filtered"
    )


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE data",
        "INSERT INTO data VALUES (1)",
        "COPY data TO '/tmp/out.csv'",
        "SELECT * FROM read_csv('/tmp/other.csv')",
        "SELECT * FROM read_csv_auto('/tmp/other.csv')",
        "SELECT * FROM data; SELECT * FROM data",
        "PRAGMA database_list",
        "UPDATE data SET name = 'x'",
    ],
)
def test_unsafe_sql_is_rejected(sql: str) -> None:
    with pytest.raises(QueryValidationError):
        validate_read_only_sql(sql)


def test_sql_length_is_bounded() -> None:
    with pytest.raises(QueryValidationError, match="character limit"):
        validate_read_only_sql(
            "SELECT * FROM data WHERE value IN ("
            + ",".join("1" for _ in range(6000))
            + ")"
        )


@pytest.mark.asyncio
async def test_limit_is_enforced_and_bad_column_is_a_duckdb_error(
    tmp_path: Path,
) -> None:
    path = tmp_path / "numbers.csv"
    path.write_text(
        "value\n" + "\n".join(str(index) for index in range(150)),
        encoding="utf-8",
    )
    result = await query_tabular_file(
        path,
        mime_type="text/csv",
        sql="SELECT * FROM data ORDER BY value",
    )
    assert len(result.rows) == 100
    with pytest.raises(duckdb.Error):
        await query_tabular_file(
            path,
            mime_type="text/csv",
            sql="SELECT missing_column FROM data",
        )


@pytest.mark.asyncio
async def test_query_timeout_interrupts_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "numbers.csv"
    path.write_text("value\n1\n", encoding="utf-8")

    def slow_query(
        _connection: duckdb.DuckDBPyConnection,
        _query: str,
    ) -> object:
        time.sleep(0.05)
        return object()

    monkeypatch.setattr(query_module, "_execute", slow_query)
    with pytest.raises(QueryTimeoutError):
        await query_tabular_file(
            path,
            mime_type="text/csv",
            sql="SELECT * FROM data",
            timeout_seconds=0.01,
        )


def test_duckdb_external_file_access_is_disabled(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed.csv"
    other = tmp_path / "other.csv"
    allowed.write_text("value\n1\n", encoding="utf-8")
    other.write_text("secret\nhidden\n", encoding="utf-8")
    connection = _load_table(allowed, "text/csv")
    try:
        with pytest.raises(duckdb.PermissionException):
            connection.execute(
                "SELECT * FROM read_csv_auto(?)",
                [str(other)],
            )
        with pytest.raises(duckdb.Error):
            connection.execute("SET enable_external_access=true")
        with pytest.raises(duckdb.Error):
            connection.execute("LOAD httpfs")
    finally:
        connection.close()


async def _seed_table(
    app: FastAPI,
    *,
    filename: str,
    mime_type: str,
    content: bytes,
) -> tuple[str, str]:
    collection_id = new_id("col")
    file_id = new_id("file")
    key = f"alice/{file_id}{Path(filename).suffix}"
    now = datetime.now(UTC)
    async with app.state.session_factory() as session:
        session.add(
            Collection(
                id=collection_id,
                owner_id="alice",
                name="Tables",
                description="",
                visibility="personal",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            KbFile(
                id=file_id,
                collection_id=collection_id,
                filename=filename,
                s3_key=key,
                size_bytes=len(content),
                mime_type=mime_type,
                status="ready",
                content_md=(
                    "type: table\nresource: ./employees.json"
                    if filename.endswith(".json")
                    else None
                ),
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    storage = app.state.storage
    assert isinstance(storage, FakeStorage)
    storage.objects[key] = content
    return collection_id, file_id


@pytest.mark.asyncio
async def test_file_must_belong_to_attached_collection(app: FastAPI) -> None:
    collection_id, file_id = await _seed_table(
        app,
        filename="employees.csv",
        mime_type="text/csv",
        content=b"employee_id,name\nEMP1,Ada\n",
    )
    tool = QueryTableTool(
        app.state.session_factory,
        app.state.storage,
        ["col_not_attached"],
    )
    result = await tool.run(
        {"file_id": file_id, "sql": "SELECT * FROM data"},
        Citations(),
    )
    assert collection_id != "col_not_attached"
    assert "not attached" in json.loads(result.content)["error"]


@pytest.mark.asyncio
async def test_csv_filter_and_aggregate_returns_cited_rows(app: FastAPI) -> None:
    collection_id, file_id = await _seed_table(
        app,
        filename="employees.csv",
        mime_type="text/csv",
        content=(
            b"employee_id,name,role,city,salary\n"
            b"EMP1,Ada,ML Engineer,Bangalore,100\n"
            b"EMP2,Grace,ML Engineer,Pune,120\n"
            b"EMP3,Lin,Designer,Bangalore,80\n"
        ),
    )
    tool = QueryTableTool(
        app.state.session_factory,
        app.state.storage,
        [collection_id],
    )
    citations = Citations()
    filtered = await tool.run(
        {
            "file_id": file_id,
            "sql": (
                "SELECT employee_id, name FROM data "
                "WHERE role = 'ML Engineer' AND city = 'Bangalore'"
            ),
        },
        citations,
    )
    payload = json.loads(filtered.content)
    assert payload["rows"][0]["name"] == "Ada"
    cite_id = payload["rows"][0]["cite_id"]
    assert cite_id in citations.known_ids()
    assert filtered.source_parts[0]["page"] is None
    assert filtered.source_parts[0]["bbox"] is None

    aggregate = await tool.run(
        {
            "file_id": file_id,
            "sql": "SELECT role, AVG(salary) AS average_salary FROM data GROUP BY role",
        },
        citations,
    )
    aggregate_rows = json.loads(aggregate.content)["rows"]
    by_role = {row["role"]: row["average_salary"] for row in aggregate_rows}
    assert by_role["ML Engineer"] == 110.0


@pytest.mark.asyncio
async def test_json_array_is_queryable_and_bad_sql_is_returned(app: FastAPI) -> None:
    collection_id, file_id = await _seed_table(
        app,
        filename="employees.json",
        mime_type="application/json",
        content=json.dumps(
            [
                {"employee_id": "EMP1", "department": "AI"},
                {"employee_id": "EMP2", "department": "Platform"},
            ]
        ).encode(),
    )
    tool = QueryTableTool(
        app.state.session_factory,
        app.state.storage,
        [collection_id],
    )
    result = await tool.run(
        {
            "file_id": file_id,
            "sql": "SELECT employee_id FROM data WHERE department = 'AI'",
        },
        Citations(),
    )
    assert json.loads(result.content)["rows"][0]["employee_id"] == "EMP1"

    bad = await tool.run(
        {"file_id": file_id, "sql": "SELECT missing FROM data"},
        Citations(),
    )
    assert "error" in json.loads(bad.content)


@pytest.mark.asyncio
async def test_oversized_tool_result_is_truncated(app: FastAPI) -> None:
    rows = ["employee_id,notes"] + [
        f"EMP{index},{'x' * 300}" for index in range(40)
    ]
    collection_id, file_id = await _seed_table(
        app,
        filename="large.csv",
        mime_type="text/csv",
        content="\n".join(rows).encode(),
    )
    tool = QueryTableTool(
        app.state.session_factory,
        app.state.storage,
        [collection_id],
    )
    result = await tool.run(
        {"file_id": file_id, "sql": "SELECT * FROM data"},
        Citations(),
    )
    payload = json.loads(result.content)
    assert payload["truncated"] is True
    assert len(result.content) <= 4000
