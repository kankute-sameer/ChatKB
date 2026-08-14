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
