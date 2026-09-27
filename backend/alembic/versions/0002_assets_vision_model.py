"""Record which vision model wrote each asset's metadata.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the nullable `assets.vision_model` column."""
    op.add_column("assets", sa.Column("vision_model", sa.Text))


def downgrade() -> None:
    """Drop the `assets.vision_model` column."""
    op.drop_column("assets", "vision_model")
