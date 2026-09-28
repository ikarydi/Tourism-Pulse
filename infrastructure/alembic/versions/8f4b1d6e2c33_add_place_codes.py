"""add place source_code and urau_code

Revision ID: 8f4b1d6e2c33
Revises: 7e3a0c5f8b12
Create Date: 2026-09-27 21:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8f4b1d6e2c33'
down_revision: str | Sequence[str] | None = '7e3a0c5f8b12'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    source_code: stable identity of places generated from official
    geography (e.g. "NUTS2:HU11", "NUTS3:HU110", "URAU:HU001C"), so the
    EU-wide location loader can upsert instead of duplicating.
    urau_code: Eurostat Urban Audit city code, linking a place (generated
    or curated) to Eurostat's city statistics.
    """
    op.add_column('places', sa.Column('source_code', sa.String(length=32), nullable=True))
    op.add_column('places', sa.Column('urau_code', sa.String(length=16), nullable=True))
    op.create_index('ix_places_source_code', 'places', ['source_code'], unique=True)
    op.create_index('ix_places_urau_code', 'places', ['urau_code'])
    op.create_index('ix_places_place_type', 'places', ['place_type'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_places_place_type', table_name='places')
    op.drop_index('ix_places_urau_code', table_name='places')
    op.drop_index('ix_places_source_code', table_name='places')
    op.drop_column('places', 'urau_code')
    op.drop_column('places', 'source_code')
