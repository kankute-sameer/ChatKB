"""Add connectors column to agents.

Revision ID: 0003_agent_connectors
Revises: 0002_agents
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003_agent_connectors"
down_revision: str | None = "0002_agents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "connectors",
            JSONB(),
            server_default=sa.text("'[\"web_search\"]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "connectors")
