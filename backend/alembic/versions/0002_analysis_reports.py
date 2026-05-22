"""add analysis_reports table

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-19
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.Text(), nullable=False),
        sa.Column(
            "canonical_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.canonical_id"),
            nullable=True,
        ),
        sa.Column("report_template", sa.Text(), nullable=False),
        sa.Column("independence", sa.Text(), nullable=False),
        sa.Column("report_markdown", sa.Text(), nullable=False),
        sa.Column("structured_context", postgresql.JSONB(), nullable=False),
        sa.Column("chart_data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "generated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("ticker"),
    )
    op.create_index("ix_analysis_reports_ticker", "analysis_reports", ["ticker"])


def downgrade() -> None:
    op.drop_index("ix_analysis_reports_ticker", table_name="analysis_reports")
    op.drop_table("analysis_reports")
