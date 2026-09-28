"""add pulse snapshot pressure

Revision ID: 3a7c9e1f5b20
Revises: 8d2f5c1a9e04
Create Date: 2026-09-27 12:40:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3a7c9e1f5b20'
down_revision: str | Sequence[str] | None = '8d2f5c1a9e04'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Tourism-pressure index, reported beside the Pulse rather than blended
    into it (pulse.engine.PRESSURE_DIMENSION). Nullable with no default:
    existing snapshots never computed pressure, and a place without
    pressure signals has no reading - 0 would claim "no pressure".
    """
    op.add_column(
        'pulse_snapshots',
        sa.Column('pressure', sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('pulse_snapshots', 'pressure')
