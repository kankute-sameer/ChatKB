from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.ids import new_id
from app.features.kb.models import Collection, KbFile
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


async def _seed_stored_file(app: FastAPI, owner_id: str) -> tuple[str, str, str]:
    collection_id = new_id("col")
    file_id = new_id("file")
    s3_key = f"{owner_id}/{file_id}.pdf"
    now = datetime.now(UTC)
    async with app.state.session_factory() as session:
        session.add(
            Collection(
                id=collection_id,
                owner_id=owner_id,
                name="Stored PDFs",
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
                filename="stored.pdf",
                s3_key=s3_key,
                size_bytes=100,
                mime_type="application/pdf",
                status="ready",
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
async def test_upload_returns_processing_immediately(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def hang_ingest(**kwargs: object) -> None:
        path = kwargs.get("pdf_path")
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
    assert rows[0]["filename"] == "handbook.pdf"


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf(client: AsyncClient) -> None:
    token = await _token(client)
    created = await _create_collection(client, token)
    response = await client.post(
        f"/v1/collections/{created['id']}/files",
        headers=_headers(token),
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


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
