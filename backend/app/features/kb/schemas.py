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
    index_md: str | None = Field(default=None, serialization_alias="indexMd")
