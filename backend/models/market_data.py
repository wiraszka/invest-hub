from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class CompanyIdentity(BaseModel):
    security_id: str | None = None
    isin: str | None = None
    figi: str | None = None
    name: str
    exchange: str | None = None
    currency: str | None = None
    # Profile enrichment fields (populated by get_profile(), not resolve_identity())
    sector: str | None = None
    industry: str | None = None
    description: str | None = None
    country: str | None = None
    employees: int | None = None
    security_type: str | None = None
    logo_url: str | None = None


class Quote(BaseModel):
    security_id: str | None = None
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
    forward_pe: float | None = None
    ev_ebitda: float | None = None
    enterprise_to_revenue: float | None = None
    price_to_book: float | None = None
    peg_ratio: float | None = None
    roe: float | None = None
    return_on_assets: float | None = None
    eps: float | None = None
    forward_eps: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    dividend_yield: float | None = None
    dividend_rate: float | None = None
    payout_ratio: float | None = None
    beta: float | None = None
    debt_to_equity: float | None = None
    quick_ratio: float | None = None
    current_ratio: float | None = None


class Financials(BaseModel):
    security_id: str | None = None
    currency: str
    income: list[IncomeStatement] = []
    balance_sheet: BalanceSheet | None = None
    cash_flow: list[CashFlow] = []
    metrics: KeyMetrics | None = None


class CompanyOfficer(BaseModel):
    name: str
    title: str
    age: int | None = None
    total_pay: int | None = None  # USD, most recent fiscal year


class LeadershipData(BaseModel):
    security_id: str | None = None
    officers: list[CompanyOfficer] = []
    held_percent_insiders: float | None = None
    held_percent_institutions: float | None = None
    audit_risk: int | None = None
    board_risk: int | None = None
    compensation_risk: int | None = None
    overall_governance_risk: int | None = None


class MarketIntelligence(BaseModel):
    security_id: str | None = None
    # Analyst consensus
    recommendation: str | None = None
    recommendation_score: float | None = None  # 1.0 = strong_buy → 5.0 = sell
    analyst_count: int | None = None
    target_mean_price: float | None = None
    target_median_price: float | None = None
    target_high_price: float | None = None
    target_low_price: float | None = None
    # Short interest
    shares_short: int | None = None
    short_ratio: float | None = None
    short_percent_of_float: float | None = None
    # Price context
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    fifty_day_average: float | None = None
    two_hundred_day_average: float | None = None
    # Peer companies (from Finnhub /stock/peers)
    peers: list[str] = []


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


class FilingContext(BaseModel):
    ticker: str
    form_type: str
    accession_number: str
    filing_date: str  # ISO date string e.g. "2024-10-31"
    item_1: str = ""
    item_1a: str = ""
    item_7: str = ""
    fetched_at: datetime


class AnalysisData(BaseModel):
    ticker: str
    company_name: str
    exchange: str | None
    currency: str
    sector: str | None = None
    industry: str | None = None
    logo_url: str | None = None
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


class FormattedContext(BaseModel):
    ticker: str
    company_name: str
    exchange: str | None
    currency: str
    template_key: str
    sector: str | None = None
    industry: str | None = None
    metrics_block: str
    business_summary: str
    leadership_block: str
    market_intelligence_block: str
    filing_excerpt: str
