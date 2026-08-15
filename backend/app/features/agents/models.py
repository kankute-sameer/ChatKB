from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, String, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, JsonType


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, default="", nullable=False)
    instructions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    appearance: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    connectors: Mapped[list[Any]] = mapped_column(
        JsonType, default=lambda: ["web_search"], nullable=False
    )
    visibility: Mapped[str] = mapped_column(
        String, default="personal", server_default="personal", nullable=False
    )
    is_builder: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
