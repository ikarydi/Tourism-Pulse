"""activate youtube source

Revision ID: 785137d0c05d
Revises: d7ac39bf77f6
Create Date: 2026-08-21 18:53:39.250825

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '785137d0c05d'
down_revision: Union[str, Sequence[str], None] = 'd7ac39bf77f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

sources_table = sa.table(
    "sources",
    sa.column("name", sa.String),
    sa.column("is_active", sa.Boolean),
)


def upgrade() -> None:
    """Upgrade schema.

    The youtube row was seeded inactive by add_sources_table, ahead of
    its ingestion adapter landing (ingestion.youtube). The adapter now
    exists, so the registry entry goes active - a data-only migration,
    no schema change.
    """
    op.execute(
        sources_table.update()
        .where(sources_table.c.name == "youtube")
        .values(is_active=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sources_table.update()
        .where(sources_table.c.name == "youtube")
        .values(is_active=False)
    )
