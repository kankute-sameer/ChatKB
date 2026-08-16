"""Support page-less and tabular knowledge-base chunks.

Revision ID: 0007_kb_file_formats
Revises: 0006_kb_s3
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0007_kb_file_formats"
down_revision: str | None = "0006_kb_s3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("kb_chunks", "page", existing_type=sa.Integer(), nullable=True)
    op.alter_column("kb_chunks", "bbox", existing_type=JSONB(), nullable=True)
    op.add_column("kb_chunks", sa.Column("metadata", JSONB(), nullable=True))


def downgrade() -> None:
    op.execute("UPDATE kb_chunks SET page = 0 WHERE page IS NULL")
    op.execute("UPDATE kb_chunks SET bbox = '[]'::jsonb WHERE bbox IS NULL")
    op.drop_column("kb_chunks", "metadata")
    op.alter_column("kb_chunks", "bbox", existing_type=JSONB(), nullable=False)
    op.alter_column("kb_chunks", "page", existing_type=sa.Integer(), nullable=False)
