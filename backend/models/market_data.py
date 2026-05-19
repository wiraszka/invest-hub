from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class CompanyIdentity(BaseModel):
    canonical_id: str | None = None
    isin: str | None = None
    figi: str | None = None
    name: str
    exchange: str | None = None
    currency: str | None = None


class Quote(BaseModel):
    canonical_id: str | None = None
    symbol: str
    price: float
    currency: str
    source: str
    fetched_at: datetime


class IncomeStatement(BaseModel):
    period: str
    fiscal_year: int | None = None
    revenue: float | None = None
    gross_profit: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    ebitda: float | None = None


class BalanceSheet(BaseModel):
    period: str
    cash: float | None = None
    total_debt: float | None = None
    net_debt: float | None = None
    total_equity: float | None = None
    total_assets: float | None = None


class CashFlow(BaseModel):
    period: str
    operating_cash_flow: float | None = None
    capex: float | None = None
    free_cash_flow: float | None = None


class KeyMetrics(BaseModel):
    period: str
    market_cap: float | None = None
    enterprise_value: float | None = None
    pe_ratio: float | None = None
    ev_ebitda: float | None = None
    price_to_book: float | None = None
    roe: float | None = None


class Financials(BaseModel):
    canonical_id: str | None = None
    currency: str
    income: list[IncomeStatement] = []
    balance_sheet: BalanceSheet | None = None
    cash_flow: list[CashFlow] = []
    metrics: KeyMetrics | None = None


class ProviderResponse(BaseModel, Generic[T]):
    data: T | None = None
    raw: dict = {}
    provider: str
    fetched_at: datetime
    error: str | None = None
