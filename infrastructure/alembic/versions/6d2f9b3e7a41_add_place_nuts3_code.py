"""add place NUTS 3 code

Revision ID: 6d2f9b3e7a41
Revises: 5c1e8a4d2b90
Create Date: 2026-09-27 17:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6d2f9b3e7a41'
down_revision: str | Sequence[str] | None = '5c1e8a4d2b90'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    The NUTS 3 region containing a destination, alongside its NUTS 2 code:
    the observatory uses the finer region wherever Eurostat publishes the
    indicator for it (e.g. a county instead of a whole NUTS 2 region).
    """
    op.add_column('places', sa.Column('nuts3_code', sa.String(length=9), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('places', 'nuts3_code')
