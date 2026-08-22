"""add wikipedia source

Revision ID: 9b3d7e1c5a2f
Revises: 1f4b2c9a7d3e
Create Date: 2026-08-22 00:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9b3d7e1c5a2f'
down_revision: str | Sequence[str] | None = '1f4b2c9a7d3e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

sources_table = sa.table(
    "sources",
    sa.column("name", sa.String),
    sa.column("category", sa.String),
    sa.column("reliability", sa.Numeric),
    sa.column("notes", sa.Text),
    sa.column("is_active", sa.Boolean),
)


def upgrade() -> None:
    """Upgrade schema.

    ingestion.wikipedia is a real, live adapter from day one - the
    Wikimedia Analytics API is fully public and keyless.
    """
    op.bulk_insert(
        sources_table,
        [
            {
                "name": "wikipedia",
                "category": "social",
                "reliability": "0.750",
                "is_active": True,
                "notes": (
                    "Wikimedia Analytics API pageviews - the counts "
                    "themselves are a reliable server-log metric even "
                    "though the underlying article content is "
                    "crowd-edited, so rated above OSM/YouTube/OpenSky's "
                    "0.650 social tier but below an official-statistics "
                    "source."
                ),
            }
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sources_table.delete().where(sources_table.c.name == "wikipedia"))
