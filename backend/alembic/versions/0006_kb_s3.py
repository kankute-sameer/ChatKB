"""Store knowledge base PDF object keys.

Revision ID: 0006_kb_s3
Revises: 0005_kb_search
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_kb_s3"
down_revision: str | None = "0005_kb_search"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("kb_files", sa.Column("s3_key", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("kb_files", "s3_key")
