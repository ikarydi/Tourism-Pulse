"""add openaq source

Revision ID: 2a5c8b3e6f14
Revises: 4e6f1a8d9c07
Create Date: 2026-08-22 00:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2a5c8b3e6f14'
down_revision: str | Sequence[str] | None = '4e6f1a8d9c07'
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

    ingestion.openaq is a real adapter, but seeded inactive - it needs a
    registered OPENAQ_API_KEY this project doesn't have yet (mirrors how
    YouTube was seeded inactive by add_sources_table until its adapter's
    commit flipped it - see 785137d0c05d_activate_youtube_source.py).
    """
    op.bulk_insert(
        sources_table,
        [
            {
                "name": "openaq",
                "category": "official",
                "reliability": "0.850",
                "is_active": False,
                "notes": (
                    "OpenAQ v3 nearest-station PM2.5 readings. Requires a "
                    "free registered API key (X-API-Key header) - flip "
                    "is_active once OPENAQ_API_KEY is configured."
                ),
            }
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sources_table.delete().where(sources_table.c.name == "openaq"))
