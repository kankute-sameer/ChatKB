from typing import Protocol


class Source(Protocol):
    def dedup_key(self) -> str: ...

    def to_source_part(self, cite_id: str) -> dict[str, object]: ...

    def to_tool_result(self, cite_id: str) -> dict[str, object]: ...


class WebSource:
    def __init__(
        self,
        url: str,
        title: str,
        snippet: str,
        published_date: str | None = None,
    ) -> None:
        self.url = url
        self.title = title
        self.snippet = snippet
        self.published_date = published_date

    def dedup_key(self) -> str:
        return self.url

    def to_source_part(self, cite_id: str) -> dict[str, object]:
        return {
            "type": "source-url",
            "sourceId": cite_id,
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "publishedDate": self.published_date,
        }

    def to_tool_result(self, cite_id: str) -> dict[str, object]:
        return {
            "cite_id": cite_id,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "published_date": self.published_date,
        }


class KbSource:
    def __init__(
        self,
        *,
        file_id: str,
        filename: str,
        media_type: str,
        page: int | None,
        anchor: str,
        bbox: list[float] | None,
        collection_id: str,
        snippet: str,
    ) -> None:
        self.file_id = file_id
        self.filename = filename
        self.media_type = media_type
        self.page = page
        self.anchor = anchor
        self.bbox = bbox
        self.collection_id = collection_id
        self.snippet = snippet

    def dedup_key(self) -> str:
        return f"{self.file_id}:{self.anchor}"

    def to_source_part(self, cite_id: str) -> dict[str, object]:
        return {
            "type": "source-document",
            "sourceId": cite_id,
            "mediaType": self.media_type,
            "title": self.filename,
            "fileId": self.file_id,
            "filename": self.filename,
            "page": self.page,
            "anchor": self.anchor,
            "bbox": self.bbox,
            "collectionId": self.collection_id,
            "snippet": self.snippet,
            "providerMetadata": {
                "chatkb": {
                    "fileId": self.file_id,
                    "page": self.page,
                    "anchor": self.anchor,
                    "bbox": self.bbox,
                    "collectionId": self.collection_id,
                    "snippet": self.snippet,
                }
            },
        }

    def to_tool_result(self, cite_id: str) -> dict[str, object]:
        return {
            "cite_id": cite_id,
            "file_id": self.file_id,
            "filename": self.filename,
            "media_type": self.media_type,
            "page": self.page,
            "snippet": self.snippet,
        }
