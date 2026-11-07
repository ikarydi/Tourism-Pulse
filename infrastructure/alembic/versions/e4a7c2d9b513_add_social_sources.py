"""add social sources

Revision ID: e4a7c2d9b513
Revises: c3d9f1a6e8b2
Create Date: 2026-11-07 18:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4a7c2d9b513"
down_revision: str | Sequence[str] | None = "c3d9f1a6e8b2"
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

NEW_SOURCES = [
    {
        "name": "reddit",
        "category": "social",
        "reliability": "0.650",
        "is_active": True,
        "notes": (
            "Reddit Data API (app-only OAuth, non-commercial use). Monthly "
            "post counts and felt-pressure share for places with a local "
            "subreddit. Aggregates only; no post text or usernames stored."
        ),
    },
    {
        "name": "bluesky",
        "category": "social",
        "reliability": "0.650",
        "is_active": True,
        "notes": (
            "Bluesky (AT Protocol searchPosts). Monthly post counts, "
            "felt-pressure share and language mix per place. Aggregates "
            "only; no post text or handles stored."
        ),
    },
]


def upgrade() -> None:
    """Upgrade schema.

    Registers Reddit and Bluesky. YouTube's monthly upload counts reuse
    the existing youtube source.
    """
    op.bulk_insert(sources_table, NEW_SOURCES)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sources_table.delete().where(
            sources_table.c.name.in_([source["name"] for source in NEW_SOURCES])
        )
    )
