"""add sec_filings table

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-27
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sec_filings",
        sa.Column("ticker", sa.Text(), nullable=False),
        sa.Column(
            "canonical_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("form_type", sa.Text(), nullable=False),
        sa.Column("accession_number", sa.Text(), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("item_1", sa.Text(), nullable=False, server_default=""),
        sa.Column("item_1a", sa.Text(), nullable=False, server_default=""),
        sa.Column("item_7", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "fetched_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("ticker"),
        sa.ForeignKeyConstraint(
            ["canonical_id"],
            ["companies.canonical_id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_sec_filings_canonical_id", "sec_filings", ["canonical_id"])


def downgrade() -> None:
    op.drop_index("ix_sec_filings_canonical_id", table_name="sec_filings")
    op.drop_table("sec_filings")
