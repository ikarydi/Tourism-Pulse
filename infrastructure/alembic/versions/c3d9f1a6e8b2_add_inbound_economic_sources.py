"""add inbound and economic sources

Revision ID: c3d9f1a6e8b2
Revises: b7e2d5a8c1f4
Create Date: 2026-09-28 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3d9f1a6e8b2'
down_revision: str | Sequence[str] | None = 'b7e2d5a8c1f4'
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

NEW_SOURCES = [
    {
        "name": "eurocontrol",
        "category": "airport",
        "reliability": "0.980",
        "is_active": True,
        "notes": (
            "EUROCONTROL Aviation Intelligence Portal - daily IFR arrivals and "
            "departures per European airport, summed to months. Inbound "
            "traffic context and a Gate 3 forecasting candidate; not a Pulse "
            "signal."
        ),
    },
    {
        "name": "european_commission",
        "category": "official",
        "reliability": "1.000",
        "is_active": True,
        "notes": (
            "European Commission (DG ECFIN) business surveys - monthly "
            "balances for accommodation (NACE 55) and travel agencies and "
            "tour operators (NACE 79). Not a Pulse signal."
        ),
    },
]


def upgrade() -> None:
    """Upgrade schema.

    Registers the two new sources behind flight counts and the business
    survey. Eurostat's new series (prices, turnover, origin countries,
    regional output and jobs) reuse the existing eurostat source.
    """
    op.bulk_insert(sources_table, NEW_SOURCES)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sources_table.delete().where(
            sources_table.c.name.in_([source["name"] for source in NEW_SOURCES])
        )
    )
