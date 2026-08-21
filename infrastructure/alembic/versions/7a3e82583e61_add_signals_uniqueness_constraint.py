"""add signals uniqueness constraint

Revision ID: 7a3e82583e61
Revises: 8b1b700cdd39
Create Date: 2026-08-21 11:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7a3e82583e61'
down_revision: str | Sequence[str] | None = '8b1b700cdd39'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Prevents duplicate signals for the same place/signal_type/observed_at/
    # source, so re-running an ingestion job (e.g. the KSH ingestion command)
    # is idempotent by construction, not just by convention.
    op.create_unique_constraint(
        "uq_signals_place_type_observed_source",
        "signals",
        ["place_id", "signal_type", "observed_at", "source"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_signals_place_type_observed_source",
        "signals",
        type_="unique",
    )
