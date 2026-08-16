"""Move index markdown from files to collections.

Revision ID: 0008_collection_index
Revises: 0007_kb_file_formats
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_collection_index"
down_revision: str | None = "0007_kb_file_formats"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("collections", sa.Column("index_md", sa.Text(), nullable=True))
    op.alter_column("kb_files", "index_md", new_column_name="summary_md")
    op.execute(
        """
        UPDATE collections AS c
        SET index_md = generated.index_md
        FROM (
            SELECT
                collection_id,
                '# ' || max(collection_name) || E'\n\n## Files\n\n' ||
                string_agg(
                    '### ' || filename || E'\n\n' ||
                    COALESCE(summary_md, 'No summary available.'),
                    E'\n\n'
                    ORDER BY filename
                ) AS index_md
            FROM (
                SELECT
                    f.collection_id,
                    c2.name AS collection_name,
                    f.filename,
                    f.summary_md
                FROM kb_files AS f
                JOIN collections AS c2 ON c2.id = f.collection_id
                WHERE f.status = 'ready'
            ) AS ready_files
            GROUP BY collection_id
        ) AS generated
        WHERE c.id = generated.collection_id
        """
    )


def downgrade() -> None:
    op.alter_column("kb_files", "summary_md", new_column_name="index_md")
    op.drop_column("collections", "index_md")
