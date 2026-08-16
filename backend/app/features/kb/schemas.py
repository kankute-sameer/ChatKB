from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Visibility = Literal["personal", "workspace"]
FileStatus = Literal["processing", "ready", "failed"]


class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    visibility: Visibility = "personal"


class CollectionResponse(BaseModel):
    id: str
    name: str
    description: str
    visibility: Visibility
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class KbFileSummary(BaseModel):
    id: str
    collection_id: str = Field(serialization_alias="collectionId")
    filename: str
    size_bytes: int = Field(serialization_alias="sizeBytes")
    mime_type: str = Field(serialization_alias="mimeType")
    status: FileStatus
    error: str | None = None
    page_count: int | None = Field(default=None, serialization_alias="pageCount")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class KbFileResponse(KbFileSummary):
    content_md: str | None = Field(default=None, serialization_alias="contentMd")


class CollectionIndexResponse(BaseModel):
    collection_id: str = Field(serialization_alias="collectionId")
    content: str

    model_config = ConfigDict(populate_by_name=True)


class KbFileViewResponse(BaseModel):
    filename: str
    mime_type: str = Field(serialization_alias="mimeType")
    content: str
    page_count: int | None = Field(default=None, serialization_alias="pageCount")

    model_config = ConfigDict(populate_by_name=True)


class ObservabilityQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    limit: int = Field(default=10, ge=1, le=20)


class ObservabilityQueryHit(BaseModel):
    chunk_id: str = Field(serialization_alias="chunkId")
    file_id: str = Field(serialization_alias="fileId")
    filename: str
    mime_type: str = Field(serialization_alias="mimeType")
    text: str
    section_header: str | None = Field(
        default=None,
        serialization_alias="sectionHeader",
    )
    page: int | None
    anchor: str
    score: float

    model_config = ConfigDict(populate_by_name=True)


class ObservabilityQueryResponse(BaseModel):
    query: str
    results: list[ObservabilityQueryHit]
