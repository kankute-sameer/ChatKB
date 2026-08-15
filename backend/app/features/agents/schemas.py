from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Visibility = Literal["personal", "workspace"]


class AgentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class AgentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    instructions: str | None = None
    connectors: list[str] | None = None


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str
    instructions: str
    appearance: dict[str, Any]
    connectors: list[str]
    visibility: Visibility
    is_builder: bool = Field(serialization_alias="isBuilder")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AgentInstructionsResponse(BaseModel):
    instructions: str


class AgentCollectionsUpdate(BaseModel):
    collection_ids: list[str] = Field(alias="collectionIds")

    model_config = ConfigDict(populate_by_name=True)
