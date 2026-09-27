"""add signal_breakdowns

Revision ID: a1c4e7b9d2f0
Revises: 8f4b1d6e2c33
Create Date: 2026-09-27 19:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1c4e7b9d2f0'
down_revision: str | Sequence[str] | None = '8f4b1d6e2c33'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Parts of a monthly signal along one dimension: Wikipedia views per
    language edition, GDELT tourism coverage per topic.
    """
    op.create_table(
        'signal_breakdowns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('place_id', sa.Integer(), nullable=False),
        sa.Column('signal_type', sa.String(length=100), nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('dimension', sa.String(length=32), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('value', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(['place_id'], ['places.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'place_id', 'signal_type', 'observed_at', 'dimension', 'key',
            name='uq_signal_breakdowns_place_type_observed_dimension_key',
        ),
    )
    op.create_index(
        'ix_signal_breakdowns_place_type_dimension',
        'signal_breakdowns',
        ['place_id', 'signal_type', 'dimension'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_signal_breakdowns_place_type_dimension', table_name='signal_breakdowns')
    op.drop_table('signal_breakdowns')
