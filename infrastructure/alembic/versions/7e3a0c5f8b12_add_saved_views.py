"""add saved views (user-built visualizations)

Revision ID: 7e3a0c5f8b12
Revises: 6d2f9b3e7a41
Create Date: 2026-09-27 19:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7e3a0c5f8b12'
down_revision: str | Sequence[str] | None = '6d2f9b3e7a41'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    User-built visualizations for the Explore workspace and dashboard: a
    catalog query plus chart settings, validated by the API on save.
    """
    op.create_table(
        'saved_views',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('spec', postgresql.JSONB(), nullable=False),
        sa.Column('pinned', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('saved_views')
