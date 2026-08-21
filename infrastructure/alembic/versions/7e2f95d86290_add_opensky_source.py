"""add opensky source

Revision ID: 7e2f95d86290
Revises: 2fcfd5e59713
Create Date: 2026-08-21 19:21:21.675759

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e2f95d86290'
down_revision: Union[str, Sequence[str], None] = '2fcfd5e59713'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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

    ingestion.opensky is a real, live adapter from day one - works
    anonymously, no key/partnership needed for basic access.
    """
    op.bulk_insert(
        sources_table,
        [
            {
                "name": "opensky",
                "category": "social",
                "reliability": "0.650",
                "is_active": True,
                "notes": (
                    "OpenSky Network - crowd-sourced ADS-B receiver "
                    "network, same epistemic tier as OSM's crowd-sourced "
                    "geographic data. Non-commercial license - fine for "
                    "this project's current research/development stage, "
                    "revisit before commercial use (see "
                    "ingestion.opensky's package docstring)."
                ),
            }
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sources_table.delete().where(sources_table.c.name == "opensky"))
