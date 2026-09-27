"""Initial schema: pgvector extension, assets, search_units, all indexes.

Revision ID: 0001
Revises:
Create Date: 2026-09-24
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the pgvector extension, both tables and their indexes."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "assets",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("collection", sa.Text, nullable=False),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("asset_type", sa.Text, nullable=False),
        sa.Column("mime", sa.Text, nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("sha256", sa.Text, nullable=False),
        sa.Column("aliases", pg.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("error", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("title", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("tags", pg.ARRAY(sa.Text)),
        sa.Column("visible_text", sa.Text),
        sa.Column("image_type", sa.Text),
        sa.Column("metadata_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("collection", "sha256", name="uq_assets_collection_sha256"),
    )
    op.create_index(
        "ix_assets_collection_status_created", "assets", ["collection", "status", "created_at"]
    )

    op.create_table(
        "search_units",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "asset_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("collection", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("unit_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("start_char", sa.Integer),
        sa.Column("end_char", sa.Integer),
        sa.Column("body", sa.Text),
        sa.Column(
            "tsv",
            pg.TSVECTOR,
            sa.Computed("to_tsvector('english', coalesce(body, ''))", persisted=True),
        ),
        sa.Column("embedding", Vector(1024)),
        sa.Column("embedding_model", sa.Text),
    )
    op.create_index("ix_search_units_asset_id", "search_units", ["asset_id"])
    op.create_index("ix_search_units_tsv", "search_units", ["tsv"], postgresql_using="gin")
    op.create_index(
        "ix_search_units_embedding",
        "search_units",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Drop both tables and the pgvector extension."""
    op.drop_table("search_units")
    op.drop_table("assets")
    op.execute("DROP EXTENSION IF EXISTS vector")
