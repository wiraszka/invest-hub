"""add peers column to market_intelligence

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "market_intelligence",
        sa.Column("peers", ARRAY(sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("market_intelligence", "peers")
