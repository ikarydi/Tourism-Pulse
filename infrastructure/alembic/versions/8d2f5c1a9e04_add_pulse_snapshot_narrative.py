"""add pulse snapshot narrative

Revision ID: 8d2f5c1a9e04
Revises: 6f1d4a9b2c73
Create Date: 2026-08-22 01:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8d2f5c1a9e04'
down_revision: str | Sequence[str] | None = '6f1d4a9b2c73'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    LLM-written analyst narrative (pulse.narrative) - nullable, since no
    LLM provider is configured by default (settings.groq_api_key unset).
    """
    op.add_column(
        'pulse_snapshots',
        sa.Column('narrative', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('pulse_snapshots', 'narrative')
