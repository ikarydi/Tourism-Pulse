"""add news_articles and video_items

Revision ID: 3d9a6c2e8f51
Revises: 7c8e2f4a1b96
Create Date: 2026-08-22 00:50:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3d9a6c2e8f51'
down_revision: str | Sequence[str] | None = '7c8e2f4a1b96'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Silver layer, item-level: individual GDELT articles / YouTube videos,
    each tagged with classification.item_classifier's category output -
    see db/models/news_article.py and video_item.py.
    """
    op.create_table(
        'news_articles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('place_id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('title', sa.String(length=1000), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tone', sa.Float(), nullable=True),
        sa.Column('categories', sa.JSON(), nullable=False),
        sa.Column('source_observation_id', sa.Integer(), nullable=True),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['place_id'], ['places.id']),
        sa.ForeignKeyConstraint(['source_observation_id'], ['source_observations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'place_id', 'url'),
    )
    op.create_index(
        op.f('ix_news_articles_place_id'), 'news_articles', ['place_id'], unique=False
    )

    op.create_table(
        'video_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('place_id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('video_id', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=1000), nullable=False),
        sa.Column('channel', sa.String(length=255), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('categories', sa.JSON(), nullable=False),
        sa.Column('source_observation_id', sa.Integer(), nullable=True),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['place_id'], ['places.id']),
        sa.ForeignKeyConstraint(['source_observation_id'], ['source_observations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'place_id', 'video_id'),
    )
    op.create_index(
        op.f('ix_video_items_place_id'), 'video_items', ['place_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_video_items_place_id'), table_name='video_items')
    op.drop_table('video_items')
    op.drop_index(op.f('ix_news_articles_place_id'), table_name='news_articles')
    op.drop_table('news_articles')
