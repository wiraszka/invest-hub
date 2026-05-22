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


class Company(Base):
    __tablename__ = "companies"

    canonical_id = Column(
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
    sector = Column(Text, nullable=True)
    country = Column(Text, nullable=True)
    asset_type = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CompanyProviderXref(Base):
    __tablename__ = "company_provider_xref"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    canonical_id = Column(UUID(as_uuid=True), ForeignKey("companies.canonical_id"), nullable=False)
    provider = Column(Text, nullable=False)
    provider_ticker = Column(Text, nullable=False)
    provider_name = Column(Text, nullable=True)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "provider_ticker"),
        Index("ix_company_provider_xref_canonical_id", "canonical_id"),
    )


class RawQuote(Base):
    __tablename__ = "raw_quotes"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    canonical_id = Column(UUID(as_uuid=True), ForeignKey("companies.canonical_id"), nullable=True)
    provider = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    raw_data = Column(JSONB, nullable=False)
    fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)


class RawFinancials(Base):
    __tablename__ = "raw_financials"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    canonical_id = Column(UUID(as_uuid=True), ForeignKey("companies.canonical_id"), nullable=True)
    provider = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    period = Column(Text, nullable=False)
    raw_data = Column(JSONB, nullable=False)
    fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)


class NormalizedQuote(Base):
    __tablename__ = "quotes"

    canonical_id = Column(UUID(as_uuid=True), ForeignKey("companies.canonical_id"), primary_key=True)
    price = Column(Numeric(20, 4), nullable=True)
    currency = Column(Text, nullable=True)
    source = Column(Text, nullable=True)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NormalizedFinancials(Base):
    __tablename__ = "financials"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    canonical_id = Column(UUID(as_uuid=True), ForeignKey("companies.canonical_id"), nullable=False)
    period = Column(Text, nullable=False)
    fiscal_year = Column(Integer, nullable=True)
    revenue = Column(Numeric(20, 4), nullable=True)
    gross_profit = Column(Numeric(20, 4), nullable=True)
    operating_income = Column(Numeric(20, 4), nullable=True)
    net_income = Column(Numeric(20, 4), nullable=True)
    ebitda = Column(Numeric(20, 4), nullable=True)
    cash = Column(Numeric(20, 4), nullable=True)
    total_debt = Column(Numeric(20, 4), nullable=True)
    net_debt = Column(Numeric(20, 4), nullable=True)
    total_equity = Column(Numeric(20, 4), nullable=True)
    total_assets = Column(Numeric(20, 4), nullable=True)
    operating_cash_flow = Column(Numeric(20, 4), nullable=True)
    capex = Column(Numeric(20, 4), nullable=True)
    free_cash_flow = Column(Numeric(20, 4), nullable=True)
    market_cap = Column(Numeric(20, 4), nullable=True)
    enterprise_value = Column(Numeric(20, 4), nullable=True)
    pe_ratio = Column(Numeric(20, 4), nullable=True)
    ev_ebitda = Column(Numeric(20, 4), nullable=True)
    price_to_book = Column(Numeric(20, 4), nullable=True)
    roe = Column(Numeric(20, 4), nullable=True)
    currency = Column(Text, nullable=True)
    sources = Column(ARRAY(Text), nullable=True)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("canonical_id", "period"),)


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
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

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
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

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
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class TrendsCache(Base):
    __tablename__ = "trends_cache"

    cache_key = Column(Text, primary_key=True)
    data = Column(JSONB, nullable=False)
    fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# Analysis layer
# ---------------------------------------------------------------------------


class AnalysisReportRow(Base):
    __tablename__ = "analysis_reports"

    ticker = Column(Text, primary_key=True)
    canonical_id = Column(UUID(as_uuid=True), ForeignKey("companies.canonical_id"), nullable=True)
    report_template = Column(Text, nullable=True)
    independence = Column(Text, nullable=True)
    report_markdown = Column(Text, nullable=True)
    report_generated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    analyzed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    structured_context = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    chart_data = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    generated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
