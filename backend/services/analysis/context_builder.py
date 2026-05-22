from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.exceptions import ProviderUnavailableError
from models.market_data import CompanyIdentity, Financials, Quote
from services import sec as sec_service
from services.market_data_service import MarketDataService
from services.provider_registry import registry

logger = logging.getLogger(__name__)


@dataclass
class StructuredContext:
    ticker: str
    company_name: str
    exchange: str | None
    currency: str
    canonical_id: str | None
    template_key: str
    sector: str | None
    industry: str | None
    metrics_block: str
    filing_excerpt: str
    logo_url: str | None = None
    raw_snapshot: dict = field(default_factory=dict)


async def build(ticker: str, session: AsyncSession) -> StructuredContext:
    """Fetch all provider data in parallel and compute financial metrics.

    Raises ProviderUnavailableError if both financials and quote are unavailable.
    Filing text failures are soft — an empty string is used so the pipeline can
    still produce a data-driven report.
    """
    service = MarketDataService(registry)

    # Filing fetch runs in a thread and doesn't touch the session — start it early.
    filing_task = asyncio.create_task(asyncio.to_thread(_fetch_filing_sync, ticker))

    # Session-touching calls must run sequentially; AsyncSession is not safe for
    # concurrent coroutines (interleaved commits can corrupt transaction state).
    financials: Financials | None = None
    quote: Quote | None = None
    profile: CompanyIdentity | None = None

    try:
        financials = await service.get_financials(ticker, session)
    except BaseException as exc:
        logger.warning("financials unavailable", extra={"ticker": ticker, "error": str(exc)})

    try:
        quote = await service.get_quote(ticker, session)
    except BaseException as exc:
        logger.warning("quote unavailable", extra={"ticker": ticker, "error": str(exc)})

    try:
        profile = await service.get_profile(ticker, session)
    except BaseException as exc:
        logger.warning("profile unavailable", extra={"ticker": ticker, "error": str(exc)})

    filing_excerpt: str = ""
    try:
        filing_excerpt = await filing_task
    except BaseException as exc:
        logger.warning("filing unavailable", extra={"ticker": ticker, "error": str(exc)})

    if financials is None and quote is None:
        raise ProviderUnavailableError(ticker, [])

    logo_url: str | None = profile.logo_url if profile else None
    if logo_url is None:
        for name in settings.logo_providers:
            adapter = registry.get(name)
            if adapter is None:
                continue
            try:
                resp = await adapter.get_profile(ticker)
                if resp.data and resp.data.logo_url:
                    logo_url = resp.data.logo_url
                    break
            except Exception:
                continue

    company_name = profile.name if profile else ticker
    exchange = profile.exchange if profile else None
    currency = (
        (financials.currency if financials else None)
        or (quote.currency if quote else "USD")
    )
    canonical_id = (
        (financials.canonical_id if financials else None)
        or (profile.canonical_id if profile else None)
    )

    template_key = _classify_template(profile, financials)
    metrics_block = _format_metrics(ticker, financials, quote)
    return StructuredContext(
        ticker=ticker,
        company_name=company_name,
        exchange=exchange,
        currency=currency,
        canonical_id=canonical_id,
        template_key=template_key,
        sector=profile.sector if profile else None,
        industry=profile.industry if profile else None,
        logo_url=logo_url,
        metrics_block=metrics_block,
        filing_excerpt=filing_excerpt,
        raw_snapshot=_build_raw_snapshot(financials, quote, profile, metrics_block, filing_excerpt, logo_url),
    )


# ---------------------------------------------------------------------------
# Template classifier
# ---------------------------------------------------------------------------

_MINING_KEYWORDS = {"mining", "gold", "silver", "copper", "metal", "minerals", "coal", "iron", "steel", "aluminum", "zinc", "lithium", "uranium"}
_BIOTECH_KEYWORDS = {"biotechnology", "pharmaceutical", "drug", "therapeutics", "bioscience", "genomics", "oncology", "vaccine", "biologics"}
_HEALTHCARE_KEYWORDS = {"healthcare", "health care", "medical", "hospital", "diagnostic", "clinical"}
_ENERGY_KEYWORDS = {"energy", "oil", "gas", "petroleum", "utilities", "power", "pipeline", "lng", "refin"}
_TECH_KEYWORDS = {"technology", "software", "semiconductor", "internet", "communications", "hardware", "electronics", "cloud", "saas"}
_FINANCIAL_KEYWORDS = {"financial", "banking", "bank", "insurance", "real estate", "reit", "investment", "asset management", "brokerage"}


def _classify_template(
    profile: CompanyIdentity | None,
    financials: Financials | None,
) -> str:
    if profile and profile.security_type in ("etf", "mutualfund", "fund"):
        return "etf"

    is_revenue_generating = bool(
        financials
        and financials.income
        and any(p.revenue and p.revenue > 1_000_000 for p in financials.income)
    )

    sector_text = " ".join(filter(None, [
        profile.sector if profile else None,
        profile.industry if profile else None,
    ])).lower()

    def _matches(keywords: set[str]) -> bool:
        return any(kw in sector_text for kw in keywords)

    if _matches(_MINING_KEYWORDS):
        return "mining" if is_revenue_generating else "pre_revenue_mining"
    if _matches(_BIOTECH_KEYWORDS) or _matches(_HEALTHCARE_KEYWORDS):
        return "biotech" if is_revenue_generating else "pre_revenue_biotech"
    if _matches(_ENERGY_KEYWORDS):
        return "energy" if is_revenue_generating else "pre_revenue"
    if _matches(_TECH_KEYWORDS):
        return "tech" if is_revenue_generating else "pre_revenue"
    if _matches(_FINANCIAL_KEYWORDS):
        return "financial" if is_revenue_generating else "pre_revenue"

    return "general" if is_revenue_generating else "pre_revenue"


# ---------------------------------------------------------------------------
# Filing fetch (sync — called via asyncio.to_thread)
# ---------------------------------------------------------------------------


def _fetch_filing_sync(ticker: str) -> str:
    cik = sec_service.resolve_cik(ticker)
    submissions = sec_service.get_submissions(cik)
    accession, primary_doc, _form_type, _filing_date = sec_service.find_recent_annual(submissions)
    raw_text = sec_service.fetch_filing_text(cik, accession, primary_doc)
    return sec_service.extract_10k_sections(raw_text)


# ---------------------------------------------------------------------------
# Metric formatting helpers
# ---------------------------------------------------------------------------


def _fmt(value: float | None, prefix: str = "$") -> str:
    if value is None:
        return "N/A"
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1_000_000_000:
        return f"{sign}{prefix}{abs_val / 1_000_000_000:.2f}B"
    if abs_val >= 1_000_000:
        return f"{sign}{prefix}{abs_val / 1_000_000:.1f}M"
    return f"{sign}{prefix}{abs_val:,.0f}"


def _pct(numerator: float | None, denominator: float | None) -> str:
    if numerator is None or not denominator:
        return "N/A"
    return f"{numerator / denominator * 100:.1f}%"


def _yoy(current: float | None, prior: float | None) -> str:
    if current is None or not prior:
        return ""
    change = (current - prior) / abs(prior) * 100
    sign = "+" if change >= 0 else ""
    return f" ({sign}{change:.1f}% YoY)"


def _format_metrics(
    ticker: str,
    financials: Financials | None,
    quote: Quote | None,
) -> str:
    lines: list[str] = [f"Ticker: {ticker}"]

    if quote:
        lines.append(f"Live price: {quote.price:.4f} {quote.currency}")

    if not financials:
        lines.append("\nNo financial data available.")
        return "\n".join(lines)

    lines.append(f"Reporting currency: {financials.currency}")

    # Income statement — up to 3 periods
    if financials.income:
        lines.append("\n--- Income Statement ---")
        for idx, period in enumerate(financials.income[:3]):
            label = f"FY{period.fiscal_year}" if period.fiscal_year else period.period
            prior = financials.income[idx + 1] if idx + 1 < len(financials.income) else None
            lines.append(f"\n{label}:")
            lines.append(
                f"  Revenue:           {_fmt(period.revenue)}"
                f"{_yoy(period.revenue, prior.revenue if prior else None)}"
            )
            lines.append(
                f"  Gross profit:      {_fmt(period.gross_profit)}"
                f"  (margin: {_pct(period.gross_profit, period.revenue)})"
            )
            lines.append(
                f"  Operating income:  {_fmt(period.operating_income)}"
                f"  (margin: {_pct(period.operating_income, period.revenue)})"
            )
            lines.append(
                f"  EBITDA:            {_fmt(period.ebitda)}"
                f"  (margin: {_pct(period.ebitda, period.revenue)})"
            )
            lines.append(
                f"  Net income:        {_fmt(period.net_income)}"
                f"  (margin: {_pct(period.net_income, period.revenue)})"
            )

    # Balance sheet
    if financials.balance_sheet:
        bs = financials.balance_sheet
        lines.append("\n--- Balance Sheet ---")
        lines.append(f"  Cash:              {_fmt(bs.cash)}")
        lines.append(f"  Total debt:        {_fmt(bs.total_debt)}")
        net_label = "Net cash" if (bs.net_debt is not None and bs.net_debt < 0) else "Net debt"
        lines.append(f"  {net_label}:          {_fmt(bs.net_debt)}")
        lines.append(f"  Total equity:      {_fmt(bs.total_equity)}")
        lines.append(f"  Total assets:      {_fmt(bs.total_assets)}")

    # Cash flow
    if financials.cash_flow:
        cf = financials.cash_flow[0]
        lines.append("\n--- Cash Flow ---")
        lines.append(f"  Operating CF:      {_fmt(cf.operating_cash_flow)}")
        lines.append(f"  CapEx:             {_fmt(cf.capex)}")
        lines.append(f"  Free cash flow:    {_fmt(cf.free_cash_flow)}")
        if cf.free_cash_flow and financials.income and financials.income[0].net_income:
            fcf_conv = cf.free_cash_flow / financials.income[0].net_income
            lines.append(f"  FCF conversion:    {fcf_conv:.2f}x (FCF / Net income)")

    # Valuation metrics
    if financials.metrics:
        metrics = financials.metrics
        lines.append("\n--- Valuation Metrics ---")
        lines.append(f"  Market cap:        {_fmt(metrics.market_cap)}")
        lines.append(f"  Enterprise value:  {_fmt(metrics.enterprise_value)}")
        lines.append(
            f"  P/E ratio:         {metrics.pe_ratio:.1f}x"
            if metrics.pe_ratio else "  P/E ratio:         N/A"
        )
        lines.append(
            f"  EV/EBITDA:         {metrics.ev_ebitda:.1f}x"
            if metrics.ev_ebitda else "  EV/EBITDA:         N/A"
        )
        lines.append(
            f"  Price/Book:        {metrics.price_to_book:.2f}x"
            if metrics.price_to_book else "  Price/Book:        N/A"
        )
        lines.append(
            f"  ROE:               {metrics.roe * 100:.1f}%"
            if metrics.roe else "  ROE:               N/A"
        )
        if metrics.market_cap and financials.cash_flow and financials.cash_flow[0].free_cash_flow:
            fcf_yield = financials.cash_flow[0].free_cash_flow / metrics.market_cap * 100
            lines.append(f"  FCF yield:         {fcf_yield:.1f}%")

    return "\n".join(lines)


def _build_raw_snapshot(
    financials: Financials | None,
    quote: Quote | None,
    profile: CompanyIdentity | None,
    metrics_block: str,
    filing_excerpt: str,
    logo_url: str | None = None,
) -> dict:
    snapshot: dict = {"metrics_block": metrics_block, "filing_excerpt": filing_excerpt, "logo_url": logo_url}
    if financials:
        snapshot["financials"] = {
            "currency": financials.currency,
            "income": [period.model_dump(mode="json") for period in financials.income],
            "balance_sheet": financials.balance_sheet.model_dump(mode="json") if financials.balance_sheet else None,
            "cash_flow": [cf.model_dump(mode="json") for cf in financials.cash_flow],
            "metrics": financials.metrics.model_dump(mode="json") if financials.metrics else None,
        }
    if quote:
        snapshot["quote"] = quote.model_dump(mode="json")
    if profile:
        snapshot["profile"] = profile.model_dump(mode="json")
    return snapshot
