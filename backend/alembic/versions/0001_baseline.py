"""baseline — full schema as of v1.18.0

Revision ID: 0001
Revises:
Create Date: 2026-05-19

This migration reflects the complete schema that was applied manually during the
MongoDB → PostgreSQL migration.

On the existing Neon database, run:
    alembic stamp 0001

On a fresh database, run:
    alembic upgrade head
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- companies ---
    op.create_table(
        "companies",
        sa.Column("canonical_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("isin", sa.Text(), unique=True, nullable=True),
        sa.Column("figi", sa.Text(), unique=True, nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("exchange", sa.Text(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("sector", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("asset_type", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- company_provider_xref ---
    op.create_table(
        "company_provider_xref",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.canonical_id"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_ticker", sa.Text(), nullable=False),
        sa.Column("provider_name", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider", "provider_ticker"),
    )

    # --- raw_quotes ---
    op.create_table(
        "raw_quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.canonical_id"), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- raw_financials ---
    op.create_table(
        "raw_financials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.canonical_id"), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- quotes (normalized) ---
    op.create_table(
        "quotes",
        sa.Column("canonical_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.canonical_id"), primary_key=True),
        sa.Column("price", sa.Numeric(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- financials (normalized) ---
    op.create_table(
        "financials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.canonical_id"), nullable=False),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("revenue", sa.Numeric(), nullable=True),
        sa.Column("gross_profit", sa.Numeric(), nullable=True),
        sa.Column("operating_income", sa.Numeric(), nullable=True),
        sa.Column("net_income", sa.Numeric(), nullable=True),
        sa.Column("ebitda", sa.Numeric(), nullable=True),
        sa.Column("cash", sa.Numeric(), nullable=True),
        sa.Column("total_debt", sa.Numeric(), nullable=True),
        sa.Column("net_debt", sa.Numeric(), nullable=True),
        sa.Column("total_equity", sa.Numeric(), nullable=True),
        sa.Column("total_assets", sa.Numeric(), nullable=True),
        sa.Column("operating_cash_flow", sa.Numeric(), nullable=True),
        sa.Column("capex", sa.Numeric(), nullable=True),
        sa.Column("free_cash_flow", sa.Numeric(), nullable=True),
        sa.Column("market_cap", sa.Numeric(), nullable=True),
        sa.Column("enterprise_value", sa.Numeric(), nullable=True),
        sa.Column("pe_ratio", sa.Numeric(), nullable=True),
        sa.Column("ev_ebitda", sa.Numeric(), nullable=True),
        sa.Column("price_to_book", sa.Numeric(), nullable=True),
        sa.Column("roe", sa.Numeric(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("sources", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("canonical_id", "period"),
    )

    # --- transactions ---
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("account_type", sa.Text(), nullable=True),
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("raw_symbol", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("activity_type", sa.Text(), nullable=True),
        sa.Column("activity_sub_type", sa.Text(), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        sa.Column("quantity", sa.Numeric(), nullable=True),
        sa.Column("unit_price", sa.Numeric(), nullable=True),
        sa.Column("commission", sa.Numeric(), nullable=True),
        sa.Column("net_cash_amount", sa.Numeric(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
    )
    op.create_index("ix_transactions_user_source", "transactions", ["user_id", "source"])

    # --- holdings ---
    op.create_table(
        "holdings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_holdings_user_id", "holdings", ["user_id"])

    # --- user_preferences ---
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Text(), primary_key=True),
        sa.Column("grouping_labels", postgresql.JSONB(), nullable=True),
        sa.Column("grouping_assignments", postgresql.JSONB(), nullable=True),
        sa.Column("sector_overrides", postgresql.JSONB(), nullable=True),
        sa.Column("industry_overrides", postgresql.JSONB(), nullable=True),
        sa.Column("visible_columns", postgresql.JSONB(), nullable=True),
        sa.Column("middle_chart_column", sa.Text(), nullable=True),
        sa.Column("chart_value_mode", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- trends_cache ---
    op.create_table(
        "trends_cache",
        sa.Column("cache_key", sa.Text(), primary_key=True),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("trends_cache")
    op.drop_table("user_preferences")
    op.drop_index("ix_holdings_user_id", table_name="holdings")
    op.drop_table("holdings")
    op.drop_index("ix_transactions_user_source", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("financials")
    op.drop_table("quotes")
    op.drop_table("raw_financials")
    op.drop_table("raw_quotes")
    op.drop_table("company_provider_xref")
    op.drop_table("companies")
