"""Add agents and bind conversations to them.

Revision ID: 0002_agents
Revises: 0001_conversations
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from app.features.agents.builder import (
    BUILDER_AGENT_ID,
    BUILDER_INSTRUCTIONS,
    BUILDER_OWNER_ID,
)

revision: str = "0002_agents"
down_revision: str | None = "0001_conversations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("appearance", JSONB(), nullable=False),
        sa.Column(
            "visibility",
            sa.String(),
            server_default="personal",
            nullable=False,
        ),
        sa.Column(
            "is_builder",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agents_owner_id", "agents", ["owner_id"], unique=False)

    op.execute(
        sa.text(
            """
            INSERT INTO agents (
                id, owner_id, name, description, instructions,
                appearance, visibility, is_builder, created_at, updated_at
            ) VALUES (
                :id, :owner_id, :name, :description, :instructions,
                CAST(:appearance AS jsonb), :visibility, true, now(), now()
            )
            """
        ).bindparams(
            id=BUILDER_AGENT_ID,
            owner_id=BUILDER_OWNER_ID,
            name="Agent Creator",
            description="Helps you design, refine, and publish work agents.",
            instructions=BUILDER_INSTRUCTIONS,
            appearance='{"type": "preset", "key": "blue-blur"}',
            visibility="workspace",
        )
    )

    op.add_column(
        "conversations",
        sa.Column("target_agent_id", sa.String(), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "session_type",
            sa.String(),
            server_default="chat",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_conversations_target_agent_id",
        "conversations",
        ["target_agent_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_conversations_target_agent_id",
        "conversations",
        "agents",
        ["target_agent_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_conversations_target_agent_id", "conversations", type_="foreignkey"
    )
    op.drop_index("ix_conversations_target_agent_id", table_name="conversations")
    op.drop_column("conversations", "session_type")
    op.drop_column("conversations", "target_agent_id")
    op.drop_index("ix_agents_owner_id", table_name="agents")
    op.drop_table("agents")
