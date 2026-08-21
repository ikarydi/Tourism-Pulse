"""add gdelt source

Revision ID: 2fcfd5e59713
Revises: 785137d0c05d
Create Date: 2026-08-21 19:14:28.085104

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2fcfd5e59713'
down_revision: Union[str, Sequence[str], None] = '785137d0c05d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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

    ingestion.gdelt is a real, live adapter from day one - unlike
    youtube/airbnb, there is no "seed inactive, flip later" step since
    GDELT requires no key/partnership to already be usable.
    """
    op.bulk_insert(
        sources_table,
        [
            {
                "name": "gdelt",
                "category": "news",
                "reliability": "0.850",
                "is_active": True,
                "notes": (
                    "GDELT DOC 2.0 API - aggregates and machine-translates "
                    "global news coverage in 65 languages. Same reliability "
                    "tier as the generic 'news' category: it reflects real "
                    "news outlets, but is not itself an editorial source."
                ),
            }
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sources_table.delete().where(sources_table.c.name == "gdelt"))
