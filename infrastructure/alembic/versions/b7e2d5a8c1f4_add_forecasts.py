"""add forecasts

Revision ID: b7e2d5a8c1f4
Revises: a1c4e7b9d2f0
Create Date: 2026-09-27 20:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7e2d5a8c1f4'
down_revision: str | Sequence[str] | None = 'a1c4e7b9d2f0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Monthly forecasts of official series (Gate 2 model), live and backtest.
    Live rows are written once and never updated: they are the track record.
    """
    op.create_table(
        'forecasts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('place_id', sa.Integer(), nullable=False),
        sa.Column('signal_type', sa.String(length=100), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('model', sa.String(length=32), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('origin', sa.DateTime(timezone=True), nullable=False),
        sa.Column('target', sa.DateTime(timezone=True), nullable=False),
        sa.Column('horizon', sa.Integer(), nullable=False),
        sa.Column('point', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('low_80', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('high_80', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('low_95', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('high_95', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.ForeignKeyConstraint(['place_id'], ['places.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'place_id', 'signal_type', 'kind', 'origin', 'target',
            name='uq_forecasts_place_type_kind_origin_target',
        ),
    )
    op.create_index(
        'ix_forecasts_place_type_kind', 'forecasts', ['place_id', 'signal_type', 'kind']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_forecasts_place_type_kind', table_name='forecasts')
    op.drop_table('forecasts')
