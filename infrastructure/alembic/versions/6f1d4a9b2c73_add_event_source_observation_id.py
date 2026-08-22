"""add event source_observation_id

Revision ID: 6f1d4a9b2c73
Revises: 3d9a6c2e8f51
Create Date: 2026-08-22 01:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6f1d4a9b2c73'
down_revision: str | Sequence[str] | None = '3d9a6c2e8f51'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Closes the Event data-quality/lineage gap noted in commit 8c786c9
    and events/__main__.py's own comment - mirrors Signal.source_observation_id.
    """
    op.add_column(
        'events',
        sa.Column('source_observation_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_events_source_observation_id',
        'events',
        'source_observations',
        ['source_observation_id'],
        ['id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_events_source_observation_id', 'events', type_='foreignkey')
    op.drop_column('events', 'source_observation_id')
