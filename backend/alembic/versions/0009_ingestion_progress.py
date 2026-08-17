"""Add ingestion progress to knowledge base files.

Revision ID: 0009_ingestion_progress
Revises: 0008_collection_index
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_ingestion_progress"
down_revision: str | None = "0008_collection_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "kb_files",
        sa.Column(
            "ingestion_stage",
            sa.String(),
            nullable=False,
            server_default="Queued",
        ),
    )
    op.add_column(
        "kb_files",
        sa.Column(
            "ingestion_progress",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.execute(
        """
        UPDATE kb_files
        SET
            ingestion_stage = CASE
                WHEN status = 'ready' THEN 'Complete'
                WHEN status = 'failed' THEN 'Failed'
                ELSE 'Queued'
            END,
            ingestion_progress = CASE
                WHEN status = 'ready' THEN 100
                ELSE 0
            END
        """
    )


def downgrade() -> None:
    op.drop_column("kb_files", "ingestion_progress")
    op.drop_column("kb_files", "ingestion_stage")
