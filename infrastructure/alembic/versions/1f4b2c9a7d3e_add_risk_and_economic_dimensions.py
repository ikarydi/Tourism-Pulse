"""add risk and economic dimensions to pulse snapshots

Revision ID: 1f4b2c9a7d3e
Revises: 7e2f95d86290
Create Date: 2026-08-22 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1f4b2c9a7d3e'
down_revision: str | Sequence[str] | None = '7e2f95d86290'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Pulse expands from 4 to 6 dimensions (risk: GDACS hazard alerts,
    # economic: Eurostat tourism-economic activity - neither had a home in
    # the original demand/capacity/events/environment set). server_default
    # backfills existing snapshot rows to 0.0, matching how an unfed
    # dimension already defaults to 0.0 in pulse.engine's dimension_values.
    op.add_column(
        'pulse_snapshots',
        sa.Column(
            'risk',
            sa.Float(),
            nullable=False,
            server_default='0',
        ),
    )
    op.add_column(
        'pulse_snapshots',
        sa.Column(
            'economic',
            sa.Float(),
            nullable=False,
            server_default='0',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('pulse_snapshots', 'economic')
    op.drop_column('pulse_snapshots', 'risk')
