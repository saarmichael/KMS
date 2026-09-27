"""The two tables, as SQLAlchemy Core metadata. Mirrors the migrations exactly.

Alembic uses this metadata to draft later migrations; queries use these table objects.
"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Column,
    Computed,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR, UUID

EMBEDDING_DIMS = 1024

metadata = MetaData()

assets = Table(
    "assets",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("collection", Text, nullable=False),
    Column("filename", Text, nullable=False),
    Column("asset_type", Text, nullable=False),  # image | text
    Column("mime", Text, nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("sha256", Text, nullable=False),
    Column("aliases", ARRAY(Text), nullable=False, server_default=text("'{}'")),
    # pending | processing | ready | failed
    Column("status", Text, nullable=False, server_default="pending"),
    Column("error", Text),
    Column("started_at", DateTime(timezone=True)),  # lease start
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("title", Text),
    Column("description", Text),
    Column("tags", ARRAY(Text)),
    Column("visible_text", Text),
    Column("image_type", Text),  # photo screenshot document diagram other; null for text
    Column("vision_model", Text),
    Column("metadata_version", Integer, nullable=False, server_default="1"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint("collection", "sha256", name="uq_assets_collection_sha256"),
    Index("ix_assets_collection_status_created", "collection", "status", "created_at"),
)

search_units = Table(
    "search_units",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column(
        "asset_id",
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("collection", Text, nullable=False),  # denormalised for filtering
    Column("kind", Text, nullable=False),  # metadata | content | image | visible_text | filename
    Column("unit_index", Integer, nullable=False, server_default="0"),
    Column("start_char", Integer),
    Column("end_char", Integer),
    Column("body", Text),
    Column("tsv", TSVECTOR, Computed("to_tsvector('english', coalesce(body, ''))", persisted=True)),
    Column("embedding", Vector(EMBEDDING_DIMS)),
    Column("embedding_model", Text),
    Index("ix_search_units_asset_id", "asset_id"),
    Index("ix_search_units_tsv", "tsv", postgresql_using="gin"),
    Index(
        "ix_search_units_embedding",
        "embedding",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    ),
)
