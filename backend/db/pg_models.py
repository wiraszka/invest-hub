from __future__ import annotations

import uuid

from sqlalchemy import (
    ARRAY,
    TIMESTAMP,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    canonical_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    isin = Column(Text, unique=True, nullable=True)
    figi = Column(Text, unique=True, nullable=True)
    name = Column(Text, nullable=False)
    exchange = Column(Text, nullable=True)
    currency = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CompanyProviderXref(Base):
    __tablename__ = "company_provider_xref"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_id = Column(UUID(as_uuid=True), ForeignKey("companies.canonical_id"), nullable=False)
    provider = Column(Text, nullable=False)
    provider_ticker = Column(Text, nullable=False)
    provider_name = Column(Text, nullable=True)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("provider", "provider_ticker"),)


class RawQuote(Base):
    __tablename__ = "raw_quotes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_id = Column(UUID(as_uuid=True), ForeignKey("companies.canonical_id"), nullable=True)
    provider = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    raw_data = Column(JSONB, nullable=False)
    fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)


class RawFinancials(Base):
    __tablename__ = "raw_financials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_id = Column(UUID(as_uuid=True), ForeignKey("companies.canonical_id"), nullable=True)
    provider = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    period = Column(Text, nullable=False)
    raw_data = Column(JSONB, nullable=False)
    fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)


class NormalizedQuote(Base):
    __tablename__ = "quotes"

    canonical_id = Column(UUID(as_uuid=True), ForeignKey("companies.canonical_id"), primary_key=True)
    price = Column(Numeric, nullable=True)
    currency = Column(Text, nullable=True)
    source = Column(Text, nullable=True)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NormalizedFinancials(Base):
    __tablename__ = "financials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_id = Column(UUID(as_uuid=True), ForeignKey("companies.canonical_id"), nullable=False)
    period = Column(Text, nullable=False)
    fiscal_year = Column(Integer, nullable=True)
    revenue = Column(Numeric, nullable=True)
    gross_profit = Column(Numeric, nullable=True)
    operating_income = Column(Numeric, nullable=True)
    net_income = Column(Numeric, nullable=True)
    ebitda = Column(Numeric, nullable=True)
    cash = Column(Numeric, nullable=True)
    total_debt = Column(Numeric, nullable=True)
    net_debt = Column(Numeric, nullable=True)
    total_equity = Column(Numeric, nullable=True)
    total_assets = Column(Numeric, nullable=True)
    operating_cash_flow = Column(Numeric, nullable=True)
    capex = Column(Numeric, nullable=True)
    free_cash_flow = Column(Numeric, nullable=True)
    market_cap = Column(Numeric, nullable=True)
    enterprise_value = Column(Numeric, nullable=True)
    pe_ratio = Column(Numeric, nullable=True)
    ev_ebitda = Column(Numeric, nullable=True)
    price_to_book = Column(Numeric, nullable=True)
    roe = Column(Numeric, nullable=True)
    currency = Column(Text, nullable=True)
    sources = Column(ARRAY(Text), nullable=True)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("canonical_id", "period"),)
