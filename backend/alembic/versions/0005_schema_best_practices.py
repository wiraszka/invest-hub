"""schema best practices: uuid defaults, numeric precision, holdings cleanup, analysis_reports pk

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-21
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_FINANCIAL_AMOUNT_COLS = [
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "ebitda",
    "cash",
    "total_debt",
    "net_debt",
    "total_equity",
    "total_assets",
    "operating_cash_flow",
    "capex",
    "free_cash_flow",
    "market_cap",
    "enterprise_value",
    "pe_ratio",
    "ev_ebitda",
    "price_to_book",
    "roe",
]


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # UUID server defaults — all UUID PKs get gen_random_uuid() as DB default
    # -----------------------------------------------------------------------
    for table, col in [
        ("companies", "canonical_id"),
        ("company_provider_xref", "id"),
        ("raw_quotes", "id"),
        ("raw_financials", "id"),
        ("financials", "id"),
        ("transactions", "id"),
        ("holdings", "id"),
    ]:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {col} SET DEFAULT gen_random_uuid()"
        )

    # -----------------------------------------------------------------------
    # company_provider_xref — index on canonical_id (used in WHERE/JOIN)
    # -----------------------------------------------------------------------
    op.create_index(
        "ix_company_provider_xref_canonical_id",
        "company_provider_xref",
        ["canonical_id"],
    )

    # -----------------------------------------------------------------------
    # transactions — created_at, composite index, NOT NULL, CHECK, precision
    # -----------------------------------------------------------------------
    op.add_column(
        "transactions",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.execute(
        "CREATE INDEX ix_transactions_user_date "
        "ON transactions (user_id, transaction_date DESC)"
    )

    # Populate NULLs with sensible defaults before tightening nullability
    op.execute(
        "UPDATE transactions SET transaction_date = '1970-01-01' "
        "WHERE transaction_date IS NULL"
    )
    op.execute(
        "UPDATE transactions SET activity_type = 'Trade' WHERE activity_type IS NULL"
    )
    op.execute(
        "UPDATE transactions SET activity_sub_type = '' WHERE activity_sub_type IS NULL"
    )
    op.execute("UPDATE transactions SET account_type = '' WHERE account_type IS NULL")
    op.execute("UPDATE transactions SET currency = 'CAD' WHERE currency IS NULL")

    op.alter_column("transactions", "transaction_date", nullable=False)
    op.alter_column("transactions", "activity_type", nullable=False)
    op.alter_column("transactions", "activity_sub_type", nullable=False)
    op.alter_column("transactions", "account_type", nullable=False)
    op.alter_column("transactions", "currency", nullable=False)

    # NOT VALID skips row-by-row validation of existing data at migration time
    op.execute(
        "ALTER TABLE transactions "
        "ADD CONSTRAINT ck_transactions_activity_type "
        "CHECK (activity_type IN ('Trade', 'Dividend', 'CorporateAction')) NOT VALID"
    )

    op.alter_column("transactions", "quantity", type_=sa.Numeric(20, 8))
    op.alter_column("transactions", "unit_price", type_=sa.Numeric(20, 4))
    op.alter_column("transactions", "commission", type_=sa.Numeric(20, 4))
    op.alter_column("transactions", "net_cash_amount", type_=sa.Numeric(20, 4))

    # -----------------------------------------------------------------------
    # holdings — drop redundant structured columns, add exchange, rename ts
    # -----------------------------------------------------------------------
    for col in ("source", "symbol", "name", "quantity", "currency"):
        op.drop_column("holdings", col)

    op.add_column("holdings", sa.Column("exchange", sa.Text(), nullable=True))
    op.execute(
        "UPDATE holdings SET exchange = raw_data->>'exchange' "
        "WHERE raw_data ? 'exchange' AND raw_data->>'exchange' != ''"
    )

    # updated_at was insert-only (no onupdate) — correct name is created_at
    op.alter_column("holdings", "updated_at", new_column_name="created_at")

    # -----------------------------------------------------------------------
    # analysis_reports — drop surrogate id, promote ticker to primary key
    # -----------------------------------------------------------------------
    op.drop_index("ix_analysis_reports_ticker", table_name="analysis_reports")
    op.drop_constraint(
        "analysis_reports_ticker_key", "analysis_reports", type_="unique"
    )
    op.drop_constraint("analysis_reports_pkey", "analysis_reports", type_="primary")
    op.drop_column("analysis_reports", "id")
    op.create_primary_key("analysis_reports_pkey", "analysis_reports", ["ticker"])

    op.execute(
        "ALTER TABLE analysis_reports "
        "ALTER COLUMN structured_context SET DEFAULT '{}'::jsonb"
    )
    op.execute(
        "ALTER TABLE analysis_reports ALTER COLUMN chart_data SET DEFAULT '{}'::jsonb"
    )

    # -----------------------------------------------------------------------
    # financials + quotes — explicit Numeric precision
    # -----------------------------------------------------------------------
    for col in _FINANCIAL_AMOUNT_COLS:
        op.alter_column("financials", col, type_=sa.Numeric(20, 4))

    op.alter_column("quotes", "price", type_=sa.Numeric(20, 4))


def downgrade() -> None:
    # quotes
    op.alter_column("quotes", "price", type_=sa.Numeric())

    # financials
    for col in _FINANCIAL_AMOUNT_COLS:
        op.alter_column("financials", col, type_=sa.Numeric())

    # analysis_reports — restore id PK (id values regenerated; data loss)
    op.execute(
        "ALTER TABLE analysis_reports ALTER COLUMN structured_context DROP DEFAULT"
    )
    op.execute("ALTER TABLE analysis_reports ALTER COLUMN chart_data DROP DEFAULT")
    op.drop_constraint("analysis_reports_pkey", "analysis_reports", type_="primary")
    op.add_column(
        "analysis_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute("UPDATE analysis_reports SET id = gen_random_uuid()")
    op.alter_column("analysis_reports", "id", nullable=False)
    op.create_primary_key("analysis_reports_pkey", "analysis_reports", ["id"])
    op.create_unique_constraint(
        "analysis_reports_ticker_key", "analysis_reports", ["ticker"]
    )
    op.create_index("ix_analysis_reports_ticker", "analysis_reports", ["ticker"])

    # holdings — restore dropped columns (data loss; original values unrecoverable)
    op.alter_column("holdings", "created_at", new_column_name="updated_at")
    op.drop_column("holdings", "exchange")
    for col, col_type in [
        ("currency", sa.Text()),
        ("quantity", sa.Numeric()),
        ("name", sa.Text()),
        ("symbol", sa.Text()),
        ("source", sa.Text()),
    ]:
        op.add_column("holdings", sa.Column(col, col_type, nullable=True))

    # transactions
    op.execute("ALTER TABLE transactions DROP CONSTRAINT ck_transactions_activity_type")
    op.alter_column("transactions", "transaction_date", nullable=True)
    op.alter_column("transactions", "activity_type", nullable=True)
    op.alter_column("transactions", "activity_sub_type", nullable=True)
    op.alter_column("transactions", "account_type", nullable=True)
    op.alter_column("transactions", "currency", nullable=True)
    op.execute("DROP INDEX ix_transactions_user_date")
    op.drop_column("transactions", "created_at")
    op.alter_column("transactions", "quantity", type_=sa.Numeric())
    op.alter_column("transactions", "unit_price", type_=sa.Numeric())
    op.alter_column("transactions", "commission", type_=sa.Numeric())
    op.alter_column("transactions", "net_cash_amount", type_=sa.Numeric())

    # company_provider_xref
    op.drop_index(
        "ix_company_provider_xref_canonical_id",
        table_name="company_provider_xref",
    )

    # UUID defaults
    for table, col in [
        ("holdings", "id"),
        ("transactions", "id"),
        ("financials", "id"),
        ("raw_financials", "id"),
        ("raw_quotes", "id"),
        ("company_provider_xref", "id"),
        ("companies", "canonical_id"),
    ]:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} DROP DEFAULT")
