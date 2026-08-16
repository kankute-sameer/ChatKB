from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from sqlalchemy import select

from app.core.ids import new_id
from app.core.log import get_logger
from app.features.kb.db import KbRepository
from app.features.kb.ingestion.extract import (
    Block,
    ProseExtraction,
    TableExtraction,
    blocks_from_document,
    extract,
    extract_docx,
    extract_json,
    extract_markdown,
    extract_text,
)
from app.features.kb.ingestion.pipeline import _ingest
from app.features.kb.ingestion.table import prepare_table
from app.features.kb.models import Collection, KbChunk, KbFile
from app.tests.fakes import FakeEmbedder, FakeLLM, FakeStorage


class _Doc:
    pages: dict[int, object] = {}

    def iterate_items(self) -> list[tuple[object, int]]:
        return [
            (
                SimpleNamespace(
                    label=SimpleNamespace(value="section_header"),
                    text="Overview",
                    prov=[],
                ),
                0,
            ),
            (
                SimpleNamespace(
                    label=SimpleNamespace(value="paragraph"),
                    text="A DOCX paragraph.",
                    prov=[],
                ),
                1,
            ),
        ]


def test_docx_via_docling_produces_page_less_blocks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    converter = SimpleNamespace(
        convert=lambda _path: SimpleNamespace(document=_Doc())
    )
    monkeypatch.setattr(
        "app.features.kb.ingestion.extract.get_converter",
        lambda: converter,
    )
    blocks = extract_docx(tmp_path / "document.docx")
    assert [block["block_type"] for block in blocks] == [
        "section_header",
        "paragraph",
    ]
    assert all(block["page"] is None for block in blocks)
    assert all(block["bbox"] is None for block in blocks)


def test_router_dispatches_pdf_and_docx(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_block: Block = {
        "text": "PDF",
        "block_type": "paragraph",
        "page": 1,
        "anchor": "p1-1",
        "bbox": [0.0, 0.0, 1.0, 1.0],
        "is_heading": False,
    }
    docx_block: Block = {
        "text": "DOCX",
        "block_type": "paragraph",
        "page": None,
        "anchor": "block-1",
        "bbox": None,
        "is_heading": False,
    }
    monkeypatch.setattr(
        "app.features.kb.ingestion.extract.extract_pdf",
        lambda _path, **_kwargs: ([pdf_block], 1, []),
    )
    monkeypatch.setattr(
        "app.features.kb.ingestion.extract.extract_docx",
        lambda _path: [docx_block],
    )
    pdf = extract(tmp_path / "file.pdf", "application/pdf")
    docx = extract(
        tmp_path / "file.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert isinstance(pdf, ProseExtraction)
    assert pdf.blocks == [pdf_block]
    assert isinstance(docx, ProseExtraction)
    assert docx.blocks == [docx_block]


def test_blocks_from_document_keeps_pdf_locations() -> None:
    document = _Doc()
    blocks = blocks_from_document(document, include_locations=True)
    assert all(block["page"] == 1 for block in blocks)
    assert all(block["bbox"] == [0.0, 0.0, 0.0, 0.0] for block in blocks)


def test_markdown_headings_and_body_blocks(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    path.write_text(
        "# Setup\n\nInstall the app.\n\n- First step\n- Second step\n",
        encoding="utf-8",
    )
    blocks = extract_markdown(path)
    assert blocks[0]["block_type"] == "section_header"
    assert blocks[0]["is_heading"] is True
    assert [block["text"] for block in blocks[1:]] == [
        "Install the app.",
        "First step",
        "Second step",
    ]
    assert all(block["page"] is None for block in blocks)


def test_text_splits_on_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("First paragraph.\n\nSecond\nparagraph.\n", encoding="utf-8")
    blocks = extract_text(path)
    assert [block["text"] for block in blocks] == [
        "First paragraph.",
        "Second\nparagraph.",
    ]


def test_csv_routes_to_schema_and_bounded_preview(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    rows = ["name,age,joined"] + [
        f"Person {index},{20 + index},2026-08-{index + 1:02d}"
        for index in range(30)
    ]
    path.write_text("\n".join(rows), encoding="utf-8")
    result = extract(path, "text/csv")
    assert isinstance(result, TableExtraction)
    assert result.column_types == {
        "name": "string",
        "age": "integer",
        "joined": "date",
    }


@pytest.mark.asyncio
async def test_table_has_exactly_schema_and_preview_chunks(
    tmp_path: Path,
) -> None:
    path = tmp_path / "people.tsv"
    path.write_text("name\tscore\nAda\t9.5\nGrace\t10\n", encoding="utf-8")
    result = extract(path, "text/tab-separated-values")
    assert isinstance(result, TableExtraction)
    content, chunks = await prepare_table(
        result,
        filename=path.name,
        llm=FakeLLM(title="not yaml"),
        model="test-model",
    )
    assert len(chunks) == 2
    assert [chunk.block_type for chunk in chunks] == [
        "table_summary",
        "table",
    ]
    assert chunks[1].metadata == {"row_start": 1, "row_end": 2}
    assert "resource: \"./people.tsv\"" in content
    assert "| name | score |" in content


def test_json_array_of_objects_is_tabular(tmp_path: Path) -> None:
    path = tmp_path / "people.json"
    path.write_text(
        json.dumps([{"name": "Ada", "age": 36}, {"name": "Grace", "age": 40}]),
        encoding="utf-8",
    )
    result = extract_json(path)
    assert isinstance(result, TableExtraction)
    assert result.columns == ["name", "age"]
    assert result.column_types["age"] == "integer"


def test_nested_json_falls_back_to_page_less_prose(tmp_path: Path) -> None:
    path = tmp_path / "nested.json"
    path.write_text(
        json.dumps({"team": {"members": [{"name": "Ada"}]}}),
        encoding="utf-8",
    )
    result = extract_json(path)
    assert isinstance(result, ProseExtraction)
    assert result.blocks
    assert result.blocks[0]["page"] is None
    assert result.blocks[0]["bbox"] is None


@pytest.mark.asyncio
async def test_csv_pipeline_stores_resource_and_only_two_chunks(
    app: FastAPI,
    fake_llm: FakeLLM,
    tmp_path: Path,
) -> None:
    path = tmp_path / "employees.csv"
    path.write_text(
        "name,department,salary\nAda,Engineering,100\nGrace,Research,120\n",
        encoding="utf-8",
    )
    collection = Collection(
        id=new_id("col"),
        owner_id="alice",
        name="Employees",
        description="",
        visibility="personal",
    )
    kb_file = KbFile(
        id=new_id("file"),
        collection_id=collection.id,
        filename=path.name,
        size_bytes=path.stat().st_size,
        mime_type="text/csv",
        status="processing",
    )
    storage = FakeStorage()
    embedder = FakeEmbedder()
    async with app.state.session_factory() as session:
        session.add_all([collection, kb_file])
        await session.commit()
        await session.refresh(kb_file)
        repo = KbRepository(session)
        await _ingest(
            session,
            repo,
            kb_file,
            path,
            fake_llm,
            embedder,
            storage,
            "alice",
            "test-model",
            get_logger("test.kb"),
        )
        chunks = list(
            (
                await session.execute(
                    select(KbChunk)
                    .where(KbChunk.file_id == kb_file.id)
                    .order_by(KbChunk.chunk_index)
                )
            )
            .scalars()
            .all()
        )

    assert storage.puts == [
        (f"alice/{kb_file.id}.csv", path.read_bytes(), "text/csv")
    ]
    assert [chunk.block_type for chunk in chunks] == [
        "table_summary",
        "table",
    ]
    assert chunks[1].chunk_metadata == {"row_start": 1, "row_end": 2}
    assert kb_file.s3_key == f"alice/{kb_file.id}.csv"
    assert kb_file.content_md is not None
    assert kb_file.summary_md == "A short index summary."
    assert collection.index_md is not None
    assert f"### {path.name}" in collection.index_md
