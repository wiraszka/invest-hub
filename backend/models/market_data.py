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
    sector: str | None = None
    industry: str | None = None
    description: str | None = None
    country: str | None = None
    employees: int | None = None
    security_type: str | None = None
    logo_url: str | None = None


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
    eps: float | None = None
    forward_eps: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    debt_to_equity: float | None = None


class Financials(BaseModel):
    canonical_id: str | None = None
    currency: str
    income: list[IncomeStatement] = []
    balance_sheet: BalanceSheet | None = None
    cash_flow: list[CashFlow] = []
    metrics: KeyMetrics | None = None


class PricePoint(BaseModel):
    date: str
    close: float


class PriceHistory(BaseModel):
    ticker: str
    history: list[PricePoint]


class TrendsPoint(BaseModel):
    commodity: str
    interest: int
    momentum: float | None = None


class TrendsResult(BaseModel):
    series: list[dict]
    latest: list[TrendsPoint]


class ProviderResponse(BaseModel, Generic[T]):
    data: T | None = None
    raw: dict = {}
    provider: str
    fetched_at: datetime
    error: str | None = None


class AnalysisData(BaseModel):
    ticker: str
    company_name: str
    exchange: str | None
    currency: str
    sector: str | None = None
    industry: str | None = None
    logo_url: str | None = None
    financials: dict
    template_key: str
    generated_at: datetime


class AnalysisResult(BaseModel):
    ticker: str
    independence: str
    chart_data: dict
    analyzed_at: datetime


class AnalysisReport(BaseModel):
    ticker: str
    report_template: str
    independence: str
    report_markdown: str
    generated_at: datetime
