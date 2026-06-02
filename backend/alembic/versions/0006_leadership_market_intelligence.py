"""add leadership_data and market_intelligence tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-23
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leadership_data",
        sa.Column(
            "canonical_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.canonical_id"),
            primary_key=True,
        ),
        sa.Column(
            "officers",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("held_percent_insiders", sa.Numeric(8, 6), nullable=True),
        sa.Column("held_percent_institutions", sa.Numeric(8, 6), nullable=True),
        sa.Column("audit_risk", sa.Integer(), nullable=True),
        sa.Column("board_risk", sa.Integer(), nullable=True),
        sa.Column("compensation_risk", sa.Integer(), nullable=True),
        sa.Column("overall_governance_risk", sa.Integer(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "market_intelligence",
        sa.Column(
            "canonical_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.canonical_id"),
            primary_key=True,
        ),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("recommendation_score", sa.Numeric(6, 4), nullable=True),
        sa.Column("analyst_count", sa.Integer(), nullable=True),
        sa.Column("target_mean_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("target_median_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("target_high_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("target_low_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("shares_short", sa.Integer(), nullable=True),
        sa.Column("short_ratio", sa.Numeric(8, 4), nullable=True),
        sa.Column("short_percent_of_float", sa.Numeric(8, 6), nullable=True),
        sa.Column("fifty_two_week_high", sa.Numeric(20, 4), nullable=True),
        sa.Column("fifty_two_week_low", sa.Numeric(20, 4), nullable=True),
        sa.Column("fifty_day_average", sa.Numeric(20, 4), nullable=True),
        sa.Column("two_hundred_day_average", sa.Numeric(20, 4), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("market_intelligence")
    op.drop_table("leadership_data")
