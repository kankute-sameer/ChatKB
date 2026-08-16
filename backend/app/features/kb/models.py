from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, TypeDecorator, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.db import Base, JsonType

EMBEDDING_DIMENSIONS = 1536


class EmbeddingVector(TypeDecorator[list[float]]):
    """pgvector on Postgres, JSON list on SQLite (tests).

    asyncpg's vector codec expects a list[float]. pgvector's VECTOR bind
    processor stringifies to '[0.1,0.2,...]', which then fails with
    "could not convert string to float".
    """

    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def bind_processor(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":

            def process(value: list[float] | None) -> list[float] | None:
                if value is None:
                    return None
                return [float(x) for x in value]

            return process
        return super().bind_processor(dialect)


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, default="", nullable=False)
    visibility: Mapped[str] = mapped_column(
        String, default="personal", server_default="personal", nullable=False
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
    files: Mapped[list["KbFile"]] = relationship(
        back_populates="collection",
        cascade="all, delete-orphan",
    )


class KbFile(Base):
    __tablename__ = "kb_files"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    collection_id: Mapped[str] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    s3_key: Mapped[str | None] = mapped_column(String, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, default="processing", server_default="processing", nullable=False
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    index_md: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    collection: Mapped[Collection] = relationship(back_populates="files")
    chunks: Mapped[list["KbChunk"]] = relationship(
        back_populates="file",
        cascade="all, delete-orphan",
    )


class KbChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    file_id: Mapped[str] = mapped_column(
        ForeignKey("kb_files.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    collection_id: Mapped[str] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    section_header: Mapped[str | None] = mapped_column(Text, nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anchor: Mapped[str] = mapped_column(String, nullable=False)
    bbox: Mapped[list[float] | None] = mapped_column(JsonType, nullable=True)
    block_type: Mapped[str] = mapped_column(String, nullable=False)
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JsonType,
        nullable=True,
    )
    embedding: Mapped[list[float]] = mapped_column(
        EmbeddingVector(EMBEDDING_DIMENSIONS), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    file: Mapped[KbFile] = relationship(back_populates="chunks")


class AgentCollection(Base):
    __tablename__ = "agent_collections"

    agent_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    collection_id: Mapped[str] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
