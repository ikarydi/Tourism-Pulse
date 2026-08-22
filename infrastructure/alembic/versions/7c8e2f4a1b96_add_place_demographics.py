"""add place demographics

Revision ID: 7c8e2f4a1b96
Revises: 2a5c8b3e6f14
Create Date: 2026-08-22 00:40:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7c8e2f4a1b96'
down_revision: str | Sequence[str] | None = '2a5c8b3e6f14'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Reference data, not a Signal - population is a slow-moving context
    value, not a tourism-activity reading, so it gets its own table
    rather than a signals row (see db/models/place_demographics.py).
    """
    op.create_table(
        'place_demographics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('place_id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('population', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('source_observation_id', sa.Integer(), nullable=True),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['place_id'], ['places.id']),
        sa.ForeignKeyConstraint(['source_observation_id'], ['source_observations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('place_id', 'year'),
    )
    op.create_index(
        op.f('ix_place_demographics_place_id'),
        'place_demographics',
        ['place_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_place_demographics_place_id'), table_name='place_demographics')
    op.drop_table('place_demographics')
