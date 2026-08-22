"""add gdacs source

Revision ID: 4e6f1a8d9c07
Revises: 9b3d7e1c5a2f
Create Date: 2026-08-22 00:20:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4e6f1a8d9c07'
down_revision: str | Sequence[str] | None = '9b3d7e1c5a2f'
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

    ingestion.gdacs is a real, live adapter from day one - GDACS's
    event-list endpoint is fully public and keyless.
    """
    op.bulk_insert(
        sources_table,
        [
            {
                "name": "gdacs",
                "category": "official",
                "reliability": "0.900",
                "is_active": True,
                "notes": (
                    "Global Disaster Alert and Coordination System - a "
                    "UN/European-Commission-affiliated multi-agency "
                    "system, rated in the official-statistics tier "
                    "alongside KSH/Eurostat rather than the crowd-sourced "
                    "social tier."
                ),
            }
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sources_table.delete().where(sources_table.c.name == "gdacs"))
