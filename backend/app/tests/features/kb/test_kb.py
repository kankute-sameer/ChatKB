from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.ids import new_id
from app.core.security import create_access_token
from app.features.kb.ingestion.assemble import assemble_collection_index
from app.features.kb.models import Collection, KbFile
from app.features.kb.retrieve import ChunkHit
from app.tests.conftest import TEST_PASSWORD, TEST_USERNAME
from app.tests.fakes import FakeStorage

PDF_BYTES = b"%PDF-1.4 test document"


async def _token(client: AsyncClient) -> str:
    response = await client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


async def _create_collection(client: AsyncClient, token: str) -> dict[str, object]:
    response = await client.post(
        "/v1/collections",
        headers=_headers(token),
        json={"name": "Product docs", "description": "Specs"},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    return body


async def _seed_stored_file(
    app: FastAPI,
    owner_id: str,
    *,
    filename: str = "stored.pdf",
    mime_type: str = "application/pdf",
    content_md: str | None = None,
) -> tuple[str, str, str]:
    collection_id = new_id("col")
    file_id = new_id("file")
    s3_key = f"{owner_id}/{file_id}{Path(filename).suffix}"
    now = datetime.now(UTC)
    async with app.state.session_factory() as session:
        session.add(
            Collection(
                id=collection_id,
                owner_id=owner_id,
                name="Stored files",
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
                s3_key=s3_key,
                size_bytes=100,
                mime_type=mime_type,
                status="ready",
                content_md=content_md,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    return collection_id, file_id, s3_key


@pytest.mark.asyncio
async def test_create_and_list_collections(client: AsyncClient) -> None:
    token = await _token(client)
    created = await _create_collection(client, token)
    assert created["name"] == "Product docs"
    assert created["visibility"] == "personal"
    assert str(created["id"]).startswith("col_")

    listed = await client.get("/v1/collections", headers=_headers(token))
    assert listed.status_code == 200
    rows = listed.json()
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0]["id"] == created["id"]


@pytest.mark.asyncio
async def test_collection_index_tracks_file_deletion(
    client: AsyncClient,
    app: FastAPI,
) -> None:
    token = await _token(client)
    created = await _create_collection(client, token)
    collection_id = str(created["id"])
    now = datetime.now(UTC)
    first_id = new_id("file")
    second_id = new_id("file")
    async with app.state.session_factory() as session:
        collection = await session.get(Collection, collection_id)
        assert collection is not None
        collection.index_md = assemble_collection_index(
            collection.name,
            collection.description,
            [
                ("first.md", "First file summary."),
                ("second.txt", "Second file summary."),
            ],
        )
        session.add_all(
            [
                KbFile(
                    id=first_id,
                    collection_id=collection_id,
                    filename="first.md",
                    s3_key=f"alice/{first_id}.md",
                    size_bytes=10,
                    mime_type="text/markdown",
                    status="ready",
                    content_md="# First",
                    summary_md="First file summary.",
                    created_at=now,
                    updated_at=now,
                ),
                KbFile(
                    id=second_id,
                    collection_id=collection_id,
                    filename="second.txt",
                    s3_key=f"alice/{second_id}.txt",
                    size_bytes=10,
                    mime_type="text/plain",
                    status="ready",
                    content_md="Second",
                    summary_md="Second file summary.",
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await session.commit()

    before = await client.get(
        f"/v1/collections/{collection_id}/index",
        headers=_headers(token),
    )
    assert before.status_code == 200
    assert "### first.md" in before.json()["content"]
    assert "### second.txt" in before.json()["content"]

    deleted = await client.delete(
        f"/v1/collections/{collection_id}/files/{first_id}",
        headers=_headers(token),
    )
    assert deleted.status_code == 204

    after = await client.get(
        f"/v1/collections/{collection_id}/index",
        headers=_headers(token),
    )
    assert after.status_code == 200
    assert "first.md" not in after.json()["content"]
    assert "### second.txt" in after.json()["content"]


@pytest.mark.asyncio
async def test_upload_returns_processing_immediately(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def hang_ingest(**kwargs: object) -> None:
        path = kwargs.get("file_path")
        if isinstance(path, Path):
            path.unlink(missing_ok=True)

    monkeypatch.setattr("app.features.kb.service.run_ingestion", hang_ingest)

    token = await _token(client)
    created = await _create_collection(client, token)
    collection_id = str(created["id"])

    upload = await client.post(
        f"/v1/collections/{collection_id}/files",
        headers=_headers(token),
        files={"file": ("handbook.pdf", PDF_BYTES, "application/pdf")},
    )
    assert upload.status_code == 202
    body = upload.json()
    assert body["status"] == "processing"
    assert body["ingestionStage"] == "Queued"
    assert body["ingestionProgress"] == 0
    assert body["filename"] == "handbook.pdf"
    assert str(body["id"]).startswith("file_")
    assert body["contentMd"] is None

    listed = await client.get(
        f"/v1/collections/{collection_id}/files",
        headers=_headers(token),
    )
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["status"] == "processing"
    assert rows[0]["ingestionStage"] == "Queued"
    assert rows[0]["ingestionProgress"] == 0
    assert rows[0]["filename"] == "handbook.pdf"


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_file(client: AsyncClient) -> None:
    token = await _token(client)
    created = await _create_collection(client, token)
    response = await client.post(
        f"/v1/collections/{created['id']}/files",
        headers=_headers(token),
        files={"file": ("notes.exe", b"hello", "application/octet-stream")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "content", "mime_type"),
    [
        ("guide.docx", b"PK\x03\x04docx", "application/octet-stream"),
        ("notes.txt", b"hello", "text/plain"),
        ("readme.md", b"# Hello", "text/markdown"),
        ("people.csv", b"name,age\nAda,36", "text/csv"),
        ("people.tsv", b"name\tage\nAda\t36", "text/tab-separated-values"),
        ("people.json", b'[{"name":"Ada"}]', "application/json"),
    ],
)
async def test_upload_accepts_supported_formats(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    content: bytes,
    mime_type: str,
) -> None:
    async def finish_ingest(**kwargs: object) -> None:
        path = kwargs.get("file_path")
        if isinstance(path, Path):
            path.unlink(missing_ok=True)

    monkeypatch.setattr("app.features.kb.service.run_ingestion", finish_ingest)
    token = await _token(client)
    created = await _create_collection(client, token)
    response = await client.post(
        f"/v1/collections/{created['id']}/files",
        headers=_headers(token),
        files={"file": (filename, content, mime_type)},
    )
    assert response.status_code == 202
    assert response.json()["filename"] == filename


@pytest.mark.asyncio
async def test_file_content_redirect_authorization_and_missing(
    client: AsyncClient,
    app: FastAPI,
) -> None:
    token = await _token(client)
    _, owned_file_id, owned_key = await _seed_stored_file(app, TEST_USERNAME)
    _, other_file_id, _ = await _seed_stored_file(app, "bob")

    authorized = await client.get(
        f"/v1/files/{owned_file_id}/content",
        headers=_headers(token),
        follow_redirects=False,
    )
    assert authorized.status_code == 302
    assert authorized.headers["location"].startswith(
        "https://example-bucket.s3.amazonaws.com/"
    )
    storage = app.state.storage
    assert isinstance(storage, FakeStorage)
    assert storage.presigned == [(owned_key, 300)]

    forbidden = await client.get(
        f"/v1/files/{other_file_id}/content",
        headers=_headers(token),
        follow_redirects=False,
    )
    assert forbidden.status_code == 403

    missing = await client.get(
        "/v1/files/file_missing/content",
        headers=_headers(token),
        follow_redirects=False,
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_non_pdf_file_view_returns_whole_content_and_authorizes(
    client: AsyncClient,
    app: FastAPI,
) -> None:
    token = await _token(client)
    _, text_file_id, text_key = await _seed_stored_file(
        app,
        TEST_USERNAME,
        filename="notes.txt",
        mime_type="text/plain",
    )
    _, docx_file_id, _ = await _seed_stored_file(
        app,
        TEST_USERNAME,
        filename="guide.docx",
        mime_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        content_md="# Guide\n\nThe full extracted document.",
    )
    _, other_file_id, _ = await _seed_stored_file(
        app,
        "bob",
        filename="private.csv",
        mime_type="text/csv",
    )
    storage = app.state.storage
    assert isinstance(storage, FakeStorage)
    storage.objects[text_key] = b"First paragraph.\n\nLast paragraph."

    text_response = await client.get(
        f"/v1/files/{text_file_id}/view",
        headers=_headers(token),
    )
    assert text_response.status_code == 200
    assert text_response.json()["content"] == "First paragraph.\n\nLast paragraph."

    docx_response = await client.get(
        f"/v1/files/{docx_file_id}/view",
        headers=_headers(token),
    )
    assert docx_response.status_code == 200
    assert docx_response.json()["content"] == "# Guide\n\nThe full extracted document."

    forbidden = await client.get(
        f"/v1/files/{other_file_id}/view",
        headers=_headers(token),
    )
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_user_can_query_collection_observability(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_hybrid_search(*args: object, **kwargs: object) -> list[ChunkHit]:
        return [
            ChunkHit(
                chunk_id="chunk_1",
                file_id="file_1",
                collection_id="col_1",
                text="The handbook permits remote work.",
                section_header="Remote work",
                page=3,
                anchor="p3-1",
                bbox=None,
                filename="handbook.pdf",
                mime_type="application/pdf",
                score=0.031,
            )
        ]

    monkeypatch.setattr(
        "app.features.kb.service.hybrid_search",
        fake_hybrid_search,
    )
    token = await _token(client)
    collection = await _create_collection(client, token)

    response = await client.post(
        f"/v1/observability/collections/{collection['id']}/query",
        headers=_headers(token),
        json={"query": "remote work", "limit": 10},
    )

    assert response.status_code == 200
    assert response.json() == {
        "query": "remote work",
        "results": [
            {
                "chunkId": "chunk_1",
                "fileId": "file_1",
                "filename": "handbook.pdf",
                "mimeType": "application/pdf",
                "text": "The handbook permits remote work.",
                "sectionHeader": "Remote work",
                "page": 3,
                "anchor": "p3-1",
                "score": 0.031,
            }
        ],
    }


@pytest.mark.asyncio
async def test_observability_query_is_available_to_other_users(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_hybrid_search(*args: object, **kwargs: object) -> list[ChunkHit]:
        return []

    monkeypatch.setattr(
        "app.features.kb.service.hybrid_search",
        fake_hybrid_search,
    )
    token = create_access_token("bob")
    collection = await _create_collection(client, token)

    response = await client.post(
        f"/v1/observability/collections/{collection['id']}/query",
        headers=_headers(token),
        json={"query": "secret"},
    )

    assert response.status_code == 200
    assert response.json() == {"query": "secret", "results": []}


@pytest.mark.asyncio
async def test_delete_file_removes_s3_object(
    client: AsyncClient,
    app: FastAPI,
) -> None:
    token = await _token(client)
    collection_id, file_id, s3_key = await _seed_stored_file(app, TEST_USERNAME)
    response = await client.delete(
        f"/v1/collections/{collection_id}/files/{file_id}",
        headers=_headers(token),
    )
    assert response.status_code == 204
    storage = app.state.storage
    assert isinstance(storage, FakeStorage)
    assert storage.deletes == [s3_key]


@pytest.mark.asyncio
async def test_delete_collection_removes_all_s3_objects(
    client: AsyncClient,
    app: FastAPI,
) -> None:
    token = await _token(client)
    collection_id, _, s3_key = await _seed_stored_file(app, TEST_USERNAME)
    response = await client.delete(
        f"/v1/collections/{collection_id}",
        headers=_headers(token),
    )
    assert response.status_code == 204
    storage = app.state.storage
    assert isinstance(storage, FakeStorage)
    assert storage.deletes == [s3_key]


@pytest.mark.asyncio
async def test_collection_agents_attach_list_and_detach(
    client: AsyncClient,
) -> None:
    token = await _token(client)
    collection = await _create_collection(client, token)
    agent = await client.post(
        "/v1/agents",
        headers=_headers(token),
        json={"name": "Research agent", "description": "Searches docs"},
    )
    assert agent.status_code == 200
    agent_id = str(agent.json()["id"])

    empty = await client.get(
        f"/v1/collections/{collection['id']}/agents",
        headers=_headers(token),
    )
    assert empty.status_code == 200
    assert empty.json() == []

    attached = await client.post(
        f"/v1/collections/{collection['id']}/agents",
        headers=_headers(token),
        json={"agentId": agent_id},
    )
    assert attached.status_code == 200
    assert attached.json()["id"] == agent_id

    listed = await client.get(
        f"/v1/collections/{collection['id']}/agents",
        headers=_headers(token),
    )
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [agent_id]

    from_agent = await client.get(
        f"/v1/agents/{agent_id}/collections",
        headers=_headers(token),
    )
    assert [row["id"] for row in from_agent.json()] == [collection["id"]]

    detached = await client.delete(
        f"/v1/collections/{collection['id']}/agents/{agent_id}",
        headers=_headers(token),
    )
    assert detached.status_code == 204
    listed_again = await client.get(
        f"/v1/collections/{collection['id']}/agents",
        headers=_headers(token),
    )
    assert listed_again.json() == []
