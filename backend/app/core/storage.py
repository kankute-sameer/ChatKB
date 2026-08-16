from __future__ import annotations

from typing import Any, Protocol

from fastapi import Request

from app.core.config import Settings


class Storage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def presigned_get_url(self, key: str, expires_in: int = 300) -> str: ...

    async def delete(self, key: str) -> None: ...


class S3Storage:
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        session: Any,
    ) -> None:
        self.bucket = bucket
        self.region = region
        self._session = session
        self._client_context: Any | None = None
        self._client: Any | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> S3Storage:
        import aioboto3  # type: ignore[import-untyped]

        session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        return cls(
            bucket=settings.s3_bucket,
            region=settings.aws_region,
            session=session,
        )

    async def start(self) -> None:
        if self._client is not None:
            return
        self._client_context = self._session.client(
            "s3",
            region_name=self.region,
            endpoint_url=f"https://s3.{self.region}.amazonaws.com",
        )
        self._client = await self._client_context.__aenter__()

    async def aclose(self) -> None:
        if self._client_context is None:
            return
        await self._client_context.__aexit__(None, None, None)
        self._client_context = None
        self._client = None

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        client = self._require_client()
        await client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def get(self, key: str) -> bytes:
        client = self._require_client()
        response = await client.get_object(Bucket=self.bucket, Key=key)
        body = response["Body"]
        try:
            return bytes(await body.read())
        finally:
            body.close()

    async def presigned_get_url(self, key: str, expires_in: int = 300) -> str:
        client = self._require_client()
        url = await client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return str(url)

    async def delete(self, key: str) -> None:
        client = self._require_client()
        await client.delete_object(Bucket=self.bucket, Key=key)

    def _require_client(self) -> Any:
        if self._client is None:
            raise RuntimeError("S3 storage has not been started")
        return self._client


def get_storage(request: Request) -> Storage:
    return request.app.state.storage  # type: ignore[no-any-return]
