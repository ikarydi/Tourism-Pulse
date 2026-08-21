"""add events source tracking

Revision ID: 0f35227cfed7
Revises: 7a3e82583e61
Create Date: 2026-08-21 13:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0f35227cfed7'
down_revision: str | Sequence[str] | None = '7a3e82583e61'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # The events table was manual-entry only (no source tracking). External
    # ingestion adapters (e.g. Ticketmaster) need a stable way to identify
    # "this row already came from that provider's event X" so repeated runs
    # upsert instead of duplicating - mirrors signals.source/source_url.
    op.add_column('events', sa.Column('source', sa.String(length=100), nullable=True))
    op.add_column('events', sa.Column('external_id', sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_events_source_external_id",
        "events",
        ["source", "external_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_events_source_external_id", "events", type_="unique")
    op.drop_column('events', 'external_id')
    op.drop_column('events', 'source')
