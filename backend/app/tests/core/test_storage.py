from __future__ import annotations

from typing import Any

import pytest

from app.core.storage import S3Storage


class _Client:
    def __init__(self) -> None:
        self.put_calls: list[dict[str, object]] = []
        self.get_calls: list[dict[str, object]] = []
        self.delete_calls: list[dict[str, object]] = []
        self.presign_calls: list[tuple[str, dict[str, object]]] = []

    async def put_object(self, **kwargs: object) -> None:
        self.put_calls.append(kwargs)

    async def get_object(self, **kwargs: object) -> dict[str, object]:
        self.get_calls.append(kwargs)
        return {"Body": _Body(b"stored table")}

    async def delete_object(self, **kwargs: object) -> None:
        self.delete_calls.append(kwargs)

    async def generate_presigned_url(
        self,
        operation: str,
        **kwargs: object,
    ) -> str:
        self.presign_calls.append((operation, kwargs))
        return "https://s3.example/presigned"


class _Body:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.closed = False

    async def read(self) -> bytes:
        return self.data

    def close(self) -> None:
        self.closed = True


class _ClientContext:
    def __init__(self, client: _Client) -> None:
        self.client = client
        self.closed = False

    async def __aenter__(self) -> _Client:
        return self.client

    async def __aexit__(self, *args: object) -> None:
        self.closed = True


class _Session:
    def __init__(self, context: _ClientContext) -> None:
        self.context = context
        self.calls: list[tuple[str, dict[str, object]]] = []

    def client(self, service: str, **kwargs: object) -> Any:
        self.calls.append((service, kwargs))
        return self.context


@pytest.mark.asyncio
async def test_s3_storage_put_get_delete_and_presign() -> None:
    client = _Client()
    context = _ClientContext(client)
    session = _Session(context)
    storage = S3Storage(
        bucket="documents",
        region="ap-south-1",
        session=session,
    )
    await storage.start()

    await storage.put("alice/file_1.pdf", b"%PDF", "application/pdf")
    content = await storage.get("alice/file_1.pdf")
    url = await storage.presigned_get_url("alice/file_1.pdf", expires_in=123)
    await storage.delete("alice/file_1.pdf")
    await storage.aclose()

    assert session.calls == [
        (
            "s3",
            {
                "region_name": "ap-south-1",
                "endpoint_url": "https://s3.ap-south-1.amazonaws.com",
            },
        )
    ]
    assert client.put_calls == [
        {
            "Bucket": "documents",
            "Key": "alice/file_1.pdf",
            "Body": b"%PDF",
            "ContentType": "application/pdf",
        }
    ]
    assert client.get_calls == [
        {"Bucket": "documents", "Key": "alice/file_1.pdf"}
    ]
    assert content == b"stored table"
    assert client.presign_calls == [
        (
            "get_object",
            {
                "Params": {
                    "Bucket": "documents",
                    "Key": "alice/file_1.pdf",
                },
                "ExpiresIn": 123,
            },
        )
    ]
    assert url == "https://s3.example/presigned"
    assert client.delete_calls == [
        {"Bucket": "documents", "Key": "alice/file_1.pdf"}
    ]
    assert context.closed
