"""rename companies→securities, add profiles and raw_profiles tables

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-27
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Rename companies → securities; rename PK column canonical_id → id
    # ------------------------------------------------------------------
    op.rename_table("companies", "securities")
    op.alter_column("securities", "canonical_id", new_column_name="id")

    # ------------------------------------------------------------------
    # 2. Rename company_provider_xref → security_provider_xref
    #    Rename FK column canonical_id → security_id
    # ------------------------------------------------------------------
    op.rename_table("company_provider_xref", "security_provider_xref")
    op.alter_column(
        "security_provider_xref", "canonical_id", new_column_name="security_id"
    )
    op.drop_index(
        "ix_company_provider_xref_canonical_id",
        table_name="security_provider_xref",
    )
    op.create_index(
        "ix_security_provider_xref_security_id",
        "security_provider_xref",
        ["security_id"],
    )

    # ------------------------------------------------------------------
    # 3. Rename canonical_id → security_id in all dependent tables
    # ------------------------------------------------------------------
    for table in (
        "raw_quotes",
        "raw_financials",
        "quotes",
        "financials",
        "leadership_data",
        "market_intelligence",
        "analysis_reports",
    ):
        op.alter_column(table, "canonical_id", new_column_name="security_id")

    # sec_filings has its own index
    op.alter_column("sec_filings", "canonical_id", new_column_name="security_id")
    op.drop_index("ix_sec_filings_canonical_id", table_name="sec_filings")
    op.create_index("ix_sec_filings_security_id", "sec_filings", ["security_id"])

    # ------------------------------------------------------------------
    # 4. Create profiles table
    # ------------------------------------------------------------------
    op.create_table(
        "profiles",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "security_id",
            UUID(as_uuid=True),
            sa.ForeignKey("securities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sector", sa.Text(), nullable=True),
        sa.Column("industry", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("asset_type", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("employees", sa.Integer(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("security_id", name="uq_profiles_security_id"),
    )

    # ------------------------------------------------------------------
    # 5. Migrate profile data from securities → profiles
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO profiles
            (id, security_id, sector, industry, country, asset_type, logo_url, source)
        SELECT
            gen_random_uuid(), id, sector, industry, country, asset_type, logo_url,
            'migrated'
        FROM securities
        WHERE
            sector      IS NOT NULL
            OR industry   IS NOT NULL
            OR country    IS NOT NULL
            OR asset_type IS NOT NULL
            OR logo_url   IS NOT NULL
        """
    )

    # ------------------------------------------------------------------
    # 6. Drop profile columns from securities
    # ------------------------------------------------------------------
    for col in ("sector", "industry", "country", "asset_type", "logo_url"):
        op.drop_column("securities", col)

    # ------------------------------------------------------------------
    # 7. Create raw_profiles table
    # ------------------------------------------------------------------
    op.create_table(
        "raw_profiles",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "security_id",
            UUID(as_uuid=True),
            sa.ForeignKey("securities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("raw_data", JSONB(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_raw_profiles_security_id", "raw_profiles", ["security_id"])
    op.create_index(
        "ix_raw_profiles_symbol_provider", "raw_profiles", ["symbol", "provider"]
    )


def downgrade() -> None:
    # Drop new tables
    op.drop_table("raw_profiles")
    op.drop_table("profiles")

    # Restore profile columns to securities
    for col_name in ("sector", "industry", "country", "asset_type", "logo_url"):
        op.add_column("securities", sa.Column(col_name, sa.Text(), nullable=True))

    # Rename security_id back to canonical_id in dependent tables
    for table in (
        "raw_quotes",
        "raw_financials",
        "quotes",
        "financials",
        "leadership_data",
        "market_intelligence",
        "analysis_reports",
    ):
        op.alter_column(table, "security_id", new_column_name="canonical_id")

    op.drop_index("ix_sec_filings_security_id", table_name="sec_filings")
    op.create_index("ix_sec_filings_canonical_id", "sec_filings", ["security_id"])
    op.alter_column("sec_filings", "security_id", new_column_name="canonical_id")

    op.drop_index(
        "ix_security_provider_xref_security_id",
        table_name="security_provider_xref",
    )
    op.create_index(
        "ix_company_provider_xref_canonical_id",
        "security_provider_xref",
        ["security_id"],
    )
    op.alter_column(
        "security_provider_xref", "security_id", new_column_name="canonical_id"
    )
    op.rename_table("security_provider_xref", "company_provider_xref")

    op.alter_column("securities", "id", new_column_name="canonical_id")
    op.rename_table("securities", "companies")
