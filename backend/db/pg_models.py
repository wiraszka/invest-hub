from __future__ import annotations

import uuid

from sqlalchemy import (
    ARRAY,
    TIMESTAMP,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func
from sqlalchemy.sql import text as sa_text


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Market data layer
# ---------------------------------------------------------------------------


class Security(Base):
    __tablename__ = "securities"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    isin = Column(Text, unique=True, nullable=True)
    figi = Column(Text, unique=True, nullable=True)
    name = Column(Text, nullable=False)
    exchange = Column(Text, nullable=True)
    currency = Column(Text, nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class NormalizedProfile(Base):
    __tablename__ = "profiles"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    security_id = Column(
        UUID(as_uuid=True),
        ForeignKey("securities.id", ondelete="CASCADE"),
        nullable=False,
    )
    sector = Column(Text, nullable=True)
    industry = Column(Text, nullable=True)
    country = Column(Text, nullable=True)
    asset_type = Column(Text, nullable=True)
    logo_url = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    employees = Column(Integer, nullable=True)
    source = Column(Text, nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (UniqueConstraint("security_id", name="uq_profiles_security_id"),)


class RawProfile(Base):
    __tablename__ = "raw_profiles"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    security_id = Column(
        UUID(as_uuid=True),
        ForeignKey("securities.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    raw_data = Column(JSONB, nullable=False)
    fetched_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_raw_profiles_security_id", "security_id"),
        Index("ix_raw_profiles_symbol_provider", "symbol", "provider"),
    )


class SecurityProviderXref(Base):
    __tablename__ = "security_provider_xref"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    security_id = Column(
        UUID(as_uuid=True), ForeignKey("securities.id"), nullable=False
    )
    provider = Column(Text, nullable=False)
    provider_ticker = Column(Text, nullable=False)
    provider_name = Column(Text, nullable=True)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("provider", "provider_ticker"),
        Index("ix_security_provider_xref_security_id", "security_id"),
    )


class RawQuote(Base):
    __tablename__ = "raw_quotes"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    security_id = Column(UUID(as_uuid=True), ForeignKey("securities.id"), nullable=True)
    provider = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    raw_data = Column(JSONB, nullable=False)
    fetched_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class RawFinancials(Base):
    __tablename__ = "raw_financials"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    security_id = Column(UUID(as_uuid=True), ForeignKey("securities.id"), nullable=True)
    provider = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    period = Column(Text, nullable=False)
    raw_data = Column(JSONB, nullable=False)
    fetched_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class NormalizedQuote(Base):
    __tablename__ = "quotes"

    security_id = Column(
        UUID(as_uuid=True), ForeignKey("securities.id"), primary_key=True
    )
    price = Column(Numeric(20, 4), nullable=True)
    currency = Column(Text, nullable=True)
    source = Column(Text, nullable=True)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class NormalizedFinancials(Base):
    __tablename__ = "financials"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    security_id = Column(
        UUID(as_uuid=True), ForeignKey("securities.id"), nullable=False
    )
    period = Column(Text, nullable=False)
    fiscal_year = Column(Integer, nullable=True)
    # Income statement
    revenue = Column(Numeric(20, 4), nullable=True)
    gross_profit = Column(Numeric(20, 4), nullable=True)
    operating_income = Column(Numeric(20, 4), nullable=True)
    net_income = Column(Numeric(20, 4), nullable=True)
    ebitda = Column(Numeric(20, 4), nullable=True)
    # Balance sheet
    cash = Column(Numeric(20, 4), nullable=True)
    total_debt = Column(Numeric(20, 4), nullable=True)
    net_debt = Column(Numeric(20, 4), nullable=True)
    total_equity = Column(Numeric(20, 4), nullable=True)
    total_assets = Column(Numeric(20, 4), nullable=True)
    # Cash flow
    operating_cash_flow = Column(Numeric(20, 4), nullable=True)
    capex = Column(Numeric(20, 4), nullable=True)
    free_cash_flow = Column(Numeric(20, 4), nullable=True)
    # Valuation / key metrics
    market_cap = Column(Numeric(20, 4), nullable=True)
    enterprise_value = Column(Numeric(20, 4), nullable=True)
    pe_ratio = Column(Numeric(20, 4), nullable=True)
    forward_pe = Column(Numeric(20, 6), nullable=True)
    peg_ratio = Column(Numeric(20, 6), nullable=True)
    ev_ebitda = Column(Numeric(20, 4), nullable=True)
    enterprise_to_revenue = Column(Numeric(20, 6), nullable=True)
    price_to_book = Column(Numeric(20, 4), nullable=True)
    # Per-share / returns
    eps = Column(Numeric(20, 6), nullable=True)
    forward_eps = Column(Numeric(20, 6), nullable=True)
    roe = Column(Numeric(20, 4), nullable=True)
    return_on_assets = Column(Numeric(20, 6), nullable=True)
    # Growth
    revenue_growth = Column(Numeric(20, 6), nullable=True)
    earnings_growth = Column(Numeric(20, 6), nullable=True)
    # Dividends
    dividend_yield = Column(Numeric(20, 6), nullable=True)
    dividend_rate = Column(Numeric(20, 6), nullable=True)
    payout_ratio = Column(Numeric(20, 6), nullable=True)
    # Risk / liquidity
    beta = Column(Numeric(20, 6), nullable=True)
    debt_to_equity = Column(Numeric(20, 6), nullable=True)
    quick_ratio = Column(Numeric(20, 6), nullable=True)
    current_ratio = Column(Numeric(20, 6), nullable=True)
    # Meta
    currency = Column(Text, nullable=True)
    sources = Column(ARRAY(Text), nullable=True)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (UniqueConstraint("security_id", "period"),)


# ---------------------------------------------------------------------------
# Leadership and market intelligence layers
# ---------------------------------------------------------------------------


class LeadershipRow(Base):
    __tablename__ = "leadership_data"

    security_id = Column(
        UUID(as_uuid=True), ForeignKey("securities.id"), primary_key=True
    )
    officers = Column(JSONB, nullable=False, server_default=sa_text("'[]'::jsonb"))
    held_percent_insiders = Column(Numeric(8, 6), nullable=True)
    held_percent_institutions = Column(Numeric(8, 6), nullable=True)
    audit_risk = Column(Integer, nullable=True)
    board_risk = Column(Integer, nullable=True)
    compensation_risk = Column(Integer, nullable=True)
    overall_governance_risk = Column(Integer, nullable=True)
    source = Column(Text, nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class MarketIntelligenceRow(Base):
    __tablename__ = "market_intelligence"

    security_id = Column(
        UUID(as_uuid=True), ForeignKey("securities.id"), primary_key=True
    )
    recommendation = Column(Text, nullable=True)
    recommendation_score = Column(Numeric(6, 4), nullable=True)
    analyst_count = Column(Integer, nullable=True)
    target_mean_price = Column(Numeric(20, 4), nullable=True)
    target_median_price = Column(Numeric(20, 4), nullable=True)
    target_high_price = Column(Numeric(20, 4), nullable=True)
    target_low_price = Column(Numeric(20, 4), nullable=True)
    shares_short = Column(Integer, nullable=True)
    short_ratio = Column(Numeric(8, 4), nullable=True)
    short_percent_of_float = Column(Numeric(8, 6), nullable=True)
    fifty_two_week_high = Column(Numeric(20, 4), nullable=True)
    fifty_two_week_low = Column(Numeric(20, 4), nullable=True)
    fifty_day_average = Column(Numeric(20, 4), nullable=True)
    two_hundred_day_average = Column(Numeric(20, 4), nullable=True)
    peers = Column(ARRAY(Text), nullable=True)
    source = Column(Text, nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# App layer — investments + user data
# ---------------------------------------------------------------------------


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    user_id = Column(Text, nullable=False)
    source = Column(Text, nullable=True)
    account_type = Column(Text, nullable=False)
    symbol = Column(Text, nullable=True)
    raw_symbol = Column(Text, nullable=True)
    name = Column(Text, nullable=True)
    activity_type = Column(Text, nullable=False)
    activity_sub_type = Column(Text, nullable=False)
    transaction_date = Column(Date, nullable=False)
    quantity = Column(Numeric(20, 8), nullable=True)
    unit_price = Column(Numeric(20, 4), nullable=True)
    commission = Column(Numeric(20, 4), nullable=True)
    net_cash_amount = Column(Numeric(20, 4), nullable=True)
    currency = Column(Text, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_transactions_user_source", "user_id", "source"),
        Index("ix_transactions_user_date", "user_id", "transaction_date"),
    )


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    user_id = Column(Text, nullable=False)
    exchange = Column(Text, nullable=True)
    raw_data = Column(JSONB, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_holdings_user_id", "user_id"),)


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id = Column(Text, primary_key=True)
    grouping_labels = Column(JSONB, nullable=True)
    grouping_assignments = Column(JSONB, nullable=True)
    sector_overrides = Column(JSONB, nullable=True)
    industry_overrides = Column(JSONB, nullable=True)
    visible_columns = Column(JSONB, nullable=True)
    middle_chart_column = Column(Text, nullable=True)
    chart_value_mode = Column(Text, nullable=True)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TrendsCache(Base):
    __tablename__ = "trends_cache"

    cache_key = Column(Text, primary_key=True)
    data = Column(JSONB, nullable=False)
    fetched_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# SEC filings layer
# ---------------------------------------------------------------------------


class SecFilingRow(Base):
    __tablename__ = "sec_filings"

    ticker = Column(Text, primary_key=True)
    security_id = Column(UUID(as_uuid=True), ForeignKey("securities.id"), nullable=True)
    form_type = Column(Text, nullable=False)
    accession_number = Column(Text, nullable=False)
    filing_date = Column(Date, nullable=False)
    item_1 = Column(Text, nullable=False, server_default=sa_text("''"))
    item_1a = Column(Text, nullable=False, server_default=sa_text("''"))
    item_7 = Column(Text, nullable=False, server_default=sa_text("''"))
    fetched_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_sec_filings_security_id", "security_id"),)


# ---------------------------------------------------------------------------
# Analysis layer
# ---------------------------------------------------------------------------


class AnalysisReportRow(Base):
    __tablename__ = "analysis_reports"

    ticker = Column(Text, primary_key=True)
    security_id = Column(UUID(as_uuid=True), ForeignKey("securities.id"), nullable=True)
    report_template = Column(Text, nullable=True)
    independence = Column(Text, nullable=True)
    report_markdown = Column(Text, nullable=True)
    report_generated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    analyzed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    chart_data = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    generated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
