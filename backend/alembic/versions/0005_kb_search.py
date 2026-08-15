"""Attach collections to agents and add lexical tsvector.

Revision ID: 0005_kb_search
Revises: 0004_kb
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_kb_search"
down_revision: str | None = "0004_kb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_collections",
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("collection_id", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["collections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("agent_id", "collection_id"),
    )
    op.execute(
        """
        ALTER TABLE kb_chunks ADD COLUMN text_tsv tsvector
          GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED
        """
    )
    op.execute(
        "CREATE INDEX kb_chunks_tsv_idx ON kb_chunks USING GIN (text_tsv)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS kb_chunks_tsv_idx")
    op.execute("ALTER TABLE kb_chunks DROP COLUMN IF EXISTS text_tsv")
    op.drop_table("agent_collections")
