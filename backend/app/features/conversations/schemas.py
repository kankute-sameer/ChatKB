from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["user", "assistant"]


class UIMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    role: Role
    parts: list[dict[str, Any]]


class ConversationCreateResponse(BaseModel):
    id: str
    title: str | None
    active_response_id: str | None = Field(serialization_alias="activeResponseId")
    last_event_id: int | None = Field(serialization_alias="lastEventId")
    created_at: datetime
    updated_at: datetime
    last_active_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ConversationSummary(BaseModel):
    id: str
    title: str | None
    active_response_id: str | None = Field(serialization_alias="activeResponseId")
    last_event_id: int | None = Field(serialization_alias="lastEventId")
    created_at: datetime
    updated_at: datetime
    last_active_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ConversationDetail(BaseModel):
    id: str
    title: str | None
    messages: list[UIMessage]
    active_response_id: str | None = Field(serialization_alias="activeResponseId")
    last_event_id: int | None = Field(serialization_alias="lastEventId")
    created_at: datetime
    updated_at: datetime
    last_active_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class CreateResponseRequest(BaseModel):
    id: str
    message: UIMessage
    stream: bool = True
    trigger: str = "submit-message"


class StopRequest(BaseModel):
    active_stream_id: str | None = Field(default=None, alias="activeStreamId")
    assistant_message: UIMessage | None = Field(default=None, alias="assistantMessage")

    model_config = ConfigDict(populate_by_name=True)


class StopResponse(BaseModel):
    success: bool = True
