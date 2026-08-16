from __future__ import annotations

import json
from pathlib import Path

from app.core.llm.types import LLM
from app.features.kb.ingestion.chunk import Chunk
from app.features.kb.ingestion.extract import TableExtraction
from app.features.kb.ingestion.prompts import TABLE_SCHEMA_PROMPT

MAX_PREVIEW_ROWS = 20


async def prepare_table(
    extraction: TableExtraction,
    *,
    filename: str,
    llm: LLM,
    model: str,
) -> tuple[str, list[Chunk]]:
    """Build one discoverability schema and one bounded data preview."""
    draft = _schema_draft(extraction, filename)
    schema = (
        await llm.complete(
            [
                {
                    "role": "user",
                    "content": TABLE_SCHEMA_PROMPT.format(
                        schema=draft,
                        sample=markdown_preview(
                            extraction.columns,
                            extraction.rows[:5],
                        ),
                    ),
                }
            ],
            model=model,
        )
    ).strip()
    if not schema.startswith("type: table"):
        schema = draft

    preview_rows = extraction.rows[:MAX_PREVIEW_ROWS]
    preview = markdown_preview(extraction.columns, preview_rows)
    row_end = len(preview_rows)
    chunks = [
        Chunk(
            chunk_index=0,
            text=schema,
            section_header=None,
            page=None,
            anchor="table-schema",
            bbox=None,
            block_type="table_summary",
            metadata=None,
        ),
        Chunk(
            chunk_index=1,
            text=preview,
            section_header=None,
            page=None,
            anchor=f"rows-1-{row_end}",
            bbox=None,
            block_type="table",
            metadata={"row_start": 1, "row_end": row_end},
        ),
    ]
    return f"{schema}\n\n## Preview\n\n{preview}", chunks


def markdown_preview(
    columns: list[str],
    rows: list[dict[str, str]],
) -> str:
    header = "| " + " | ".join(_markdown_cell(column) for column in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| "
        + " | ".join(_markdown_cell(row.get(column, "")) for column in columns)
        + " |"
        for row in rows
    ]
    if not body:
        body = [
            "| " + " | ".join("" for _ in columns) + " |",
        ]
    return "\n".join([header, separator, *body])


def _schema_draft(extraction: TableExtraction, filename: str) -> str:
    title = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
    lines = [
        "type: table",
        f"title: {json.dumps(title or filename)}",
        f"summary: {json.dumps(f'Tabular data from {filename}.')}",
        f"resource: {json.dumps('./' + filename)}",
        "columns:",
    ]
    for column in extraction.columns:
        lines.extend(
            [
                f"  - name: {json.dumps(column)}",
                f"    type: {extraction.column_types[column]}",
                f"    description: {json.dumps(f'Values from the {column} column.')}",
            ]
        )
    return "\n".join(lines)


def _markdown_cell(value: str) -> str:
    return " ".join(value.replace("|", r"\|").split())
