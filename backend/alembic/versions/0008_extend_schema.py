"""extend schema: add industry/logo_url to companies, add extended KeyMetrics
columns to financials, drop structured_context from analysis_reports

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-27
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- companies: add industry and logo_url --------------------------------
    op.add_column("companies", sa.Column("industry", sa.Text(), nullable=True))
    op.add_column("companies", sa.Column("logo_url", sa.Text(), nullable=True))

    # -- financials: add extended KeyMetrics columns -------------------------
    for col_name in (
        "forward_pe",
        "peg_ratio",
        "revenue_growth",
        "earnings_growth",
        "forward_eps",
        "eps",
        "dividend_yield",
        "dividend_rate",
        "payout_ratio",
        "beta",
        "debt_to_equity",
        "quick_ratio",
        "current_ratio",
        "return_on_assets",
        "enterprise_to_revenue",
    ):
        op.add_column(
            "financials",
            sa.Column(col_name, sa.Numeric(20, 6), nullable=True),
        )

    # -- analysis_reports: drop structured_context ---------------------------
    op.drop_column("analysis_reports", "structured_context")


def downgrade() -> None:
    # Restore structured_context
    op.add_column(
        "analysis_reports",
        sa.Column(
            "structured_context",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    # Drop extended financials columns
    for col_name in (
        "forward_pe",
        "peg_ratio",
        "revenue_growth",
        "earnings_growth",
        "forward_eps",
        "eps",
        "dividend_yield",
        "dividend_rate",
        "payout_ratio",
        "beta",
        "debt_to_equity",
        "quick_ratio",
        "current_ratio",
        "return_on_assets",
        "enterprise_to_revenue",
    ):
        op.drop_column("financials", col_name)

    # Drop companies columns
    op.drop_column("companies", "logo_url")
    op.drop_column("companies", "industry")
