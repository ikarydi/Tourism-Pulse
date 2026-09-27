"""add pressure observatory: NUTS regions, regional indicators, place NUTS code

Revision ID: 5c1e8a4d2b90
Revises: 3a7c9e1f5b20
Create Date: 2026-09-27 15:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5c1e8a4d2b90'
down_revision: str | Sequence[str] | None = '3a7c9e1f5b20'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

sources_table = sa.table(
    "sources",
    sa.column("name", sa.String),
    sa.column("category", sa.String),
    sa.column("reliability", sa.Numeric),
    sa.column("notes", sa.Text),
    sa.column("is_active", sa.Boolean),
)


def upgrade() -> None:
    """Upgrade schema.

    Tourism-pressure observatory: NUTS region boundaries (PostGIS, loaded
    from GISCO), official regional tourism indicators for every EU region
    (Eurostat), and each place's NUTS code linking the two.
    """
    op.create_table(
        'nuts_regions',
        sa.Column('code', sa.String(length=9), primary_key=True),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('country_code', sa.String(length=2), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('nuts_version', sa.String(length=10), nullable=False),
    )
    # PostGIS column via SQL: the ORM maps it with db.types.Geometry.
    op.execute("ALTER TABLE nuts_regions ADD COLUMN geom geometry(MultiPolygon, 4326) NOT NULL")
    op.create_index(
        'ix_nuts_regions_geom', 'nuts_regions', ['geom'], postgresql_using='gist'
    )

    op.create_table(
        'regional_indicators',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nuts_code', sa.String(length=9), nullable=False),
        sa.Column('indicator', sa.String(length=50), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column(
            'source_observation_id',
            sa.Integer(),
            sa.ForeignKey('source_observations.id'),
            nullable=True,
        ),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('nuts_code', 'indicator', 'year'),
    )
    op.create_index('ix_regional_indicators_nuts_code', 'regional_indicators', ['nuts_code'])
    op.create_index('ix_regional_indicators_indicator', 'regional_indicators', ['indicator'])

    op.add_column('places', sa.Column('nuts_code', sa.String(length=9), nullable=True))

    op.bulk_insert(
        sources_table,
        [
            {
                "name": "gisco",
                "category": "official",
                "reliability": "1.000",
                "is_active": True,
                "notes": (
                    "Eurostat GISCO - official NUTS region boundaries, "
                    "used as reference geography for the pressure "
                    "observatory, not as a Pulse signal."
                ),
            }
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sources_table.delete().where(sources_table.c.name == "gisco"))
    op.drop_column('places', 'nuts_code')
    op.drop_index('ix_regional_indicators_indicator', table_name='regional_indicators')
    op.drop_index('ix_regional_indicators_nuts_code', table_name='regional_indicators')
    op.drop_table('regional_indicators')
    op.drop_index('ix_nuts_regions_geom', table_name='nuts_regions')
    op.drop_table('nuts_regions')
