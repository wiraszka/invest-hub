from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.exceptions import ProviderUnavailableError
from db.pg import get_session_factory
from db.pg_models import (
    LeadershipRow,
    MarketIntelligenceRow,
    NormalizedFinancials,
    NormalizedProfile,
    NormalizedQuote,
    Security,
)
from models.market_data import (
    CompanyIdentity,
    FilingContext,
    Financials,
    LeadershipData,
    MarketIntelligence,
    Quote,
)
from services.identity import resolve_identity
from services.market_data_service import (
    MarketDataService,
    _row_to_leadership,
    _row_to_market_intelligence,
    _rows_to_financials,
)
from services.provider_registry import registry

logger = logging.getLogger(__name__)


@dataclass
class StructuredContext:
    ticker: str
    company_name: str
    exchange: str | None
    currency: str
    security_id: str | None
    template_key: str
    sector: str | None
    industry: str | None
    metrics_block: str
    filing_excerpt: str
    logo_url: str | None = None
    business_summary: str = ""
    leadership_block: str = ""
    market_intelligence_block: str = ""


async def fetch_providers(ticker: str, session: AsyncSession) -> StructuredContext:
    """Phase 1 — fetch all market-data provider sources; no SEC filing.

    Resolves identity once, then fires all external API calls concurrently for
    any cache misses.  DB writes remain sequential.  Raises
    ProviderUnavailableError if both financials and quote are unavailable.
    """
    service = MarketDataService(registry)

    # --- Step 1: resolve identity once (sequential, touches DB) -------------
    identity = await resolve_identity(ticker, "fmp", session)
    security_id = identity.security_id

    # --- Step 2: check in-process and DB caches sequentially (fast) ----------

    from core.cache import cache

    financials: Financials | None = _check_cache(cache, "financials", ticker)
    quote: Quote | None = _check_cache(cache, "quote", ticker)
    profile: CompanyIdentity | None = _check_cache(cache, "profile", ticker)
    leadership: LeadershipData | None = _check_cache(cache, "leadership", ticker)
    market_intelligence: MarketIntelligence | None = _check_cache(
        cache, "market_intelligence", ticker
    )

    if financials is None and security_id:
        financials = await _load_financials_from_db(
            security_id, session, settings.financials_ttl_seconds
        )
        if financials:
            cache.set(
                ("financials", ticker), financials, settings.financials_ttl_seconds
            )

    if quote is None and security_id:
        quote = await _load_quote_from_db(security_id, session)
        if quote:
            cache.set(("quote", ticker), quote, settings.quote_ttl_seconds)

    if leadership is None and security_id:
        leadership = await _load_leadership_from_db(
            security_id, session, settings.leadership_ttl_seconds
        )
        if leadership:
            cache.set(
                ("leadership", ticker), leadership, settings.leadership_ttl_seconds
            )

    if market_intelligence is None and security_id:
        market_intelligence = await _load_market_intelligence_from_db(
            security_id, session, settings.market_intelligence_ttl_seconds
        )
        if market_intelligence:
            cache.set(
                ("market_intelligence", ticker),
                market_intelligence,
                settings.market_intelligence_ttl_seconds,
            )

    # --- Step 3: fire external API calls concurrently for cache misses -------
    # Each task gets its own DB session so it can check cache, call the
    # adapter, and persist in one pass — no double-calls.
    needs_financials = financials is None
    needs_quote = quote is None
    needs_profile = profile is None or not profile.sector  # always enrich if sparse
    needs_leadership = leadership is None
    needs_mi = market_intelligence is None

    tasks: list = []
    task_keys: list[str] = []

    if needs_financials:
        tasks.append(
            _service_call_with_own_session(service.get_financials, ticker, security_id)
        )
        task_keys.append("financials")
    if needs_quote:
        tasks.append(
            _service_call_with_own_session(service.get_quote, ticker, security_id)
        )
        task_keys.append("quote")
    if needs_profile:
        tasks.append(
            _service_call_with_own_session(service.get_profile, ticker, security_id)
        )
        task_keys.append("profile")
    if needs_leadership:
        tasks.append(
            _service_call_with_own_session(service.get_leadership, ticker, security_id)
        )
        task_keys.append("leadership")
    if needs_mi:
        tasks.append(
            _service_call_with_own_session(
                service.get_market_intelligence, ticker, security_id
            )
        )
        task_keys.append("market_intelligence")

    if tasks:
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        for key, result in zip(task_keys, raw_results, strict=False):
            if isinstance(result, BaseException):
                logger.warning(
                    f"{key} unavailable",
                    extra={"ticker": ticker, "error": str(result)},
                )
            elif key == "financials":
                financials = result  # type: ignore[assignment]
            elif key == "quote":
                quote = result  # type: ignore[assignment]
            elif key == "profile":
                profile = result  # type: ignore[assignment]
            elif key == "leadership":
                leadership = result  # type: ignore[assignment]
            elif key == "market_intelligence":
                market_intelligence = result  # type: ignore[assignment]

    if financials is None and quote is None:
        raise ProviderUnavailableError(ticker, [])

    # --- Step 5: logo fallback -----------------------------------------------
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

    # --- Step 6: assemble StructuredContext (pure Python) --------------------
    company_name = (
        (profile.name if profile and profile.name else None) or identity.name or ticker
    )
    exchange = (profile.exchange if profile else None) or identity.exchange
    currency = (financials.currency if financials else None) or (
        quote.currency if quote else "USD"
    )

    metrics_block = _format_metrics(ticker, financials, quote)
    business_summary = (
        profile.description.strip() if profile and profile.description else ""
    )
    leadership_block = _format_leadership(leadership)
    market_intelligence_block = _format_market_intelligence(market_intelligence)

    return StructuredContext(
        ticker=ticker,
        company_name=company_name,
        exchange=exchange,
        currency=currency,
        security_id=security_id,
        template_key="",  # classification is Phase 3 — done in build_context()
        sector=profile.sector if profile else None,
        industry=profile.industry if profile else None,
        logo_url=logo_url,
        metrics_block=metrics_block,
        business_summary=business_summary,
        leadership_block=leadership_block,
        market_intelligence_block=market_intelligence_block,
        filing_excerpt="",
    )


async def build_context(
    ticker: str,
    session: AsyncSession,
    template_key: str | None = None,
    filing: FilingContext | None = None,
) -> StructuredContext:
    """Phase 3 — classify template + assemble full LLM input from DB tables.

    Pure DB reads + Python formatting — no external API calls.  Template
    classification happens here when template_key is not provided (the normal
    path from run_format()).  Callers may pass a pre-computed key if needed.

    Args:
        ticker:       The ticker symbol.
        session:      Active async DB session.
        template_key: Optional override; classified internally when omitted.
        filing:       Optional Phase 2 result; items are concatenated into
                      filing_excerpt (capped at 24 000 chars).
    """
    # Resolve security_id
    identity = await resolve_identity(ticker, "fmp", session)
    sid = identity.security_id

    # Load all raw data from relational tables
    financials: Financials | None = None
    quote: Quote | None = None
    leadership: LeadershipData | None = None
    market_intelligence: MarketIntelligence | None = None
    security: Security | None = None
    profile: NormalizedProfile | None = None

    if sid:
        financials = await _load_financials_from_db(sid, session, ttl_seconds=None)
        quote = await _load_quote_from_db(sid, session)
        leadership = await _load_leadership_from_db(sid, session, ttl_seconds=None)
        market_intelligence = await _load_market_intelligence_from_db(
            sid, session, ttl_seconds=None
        )
        security_result = await session.execute(
            select(Security).where(Security.id == sid)
        )
        security = security_result.scalar_one_or_none()

        profile_result = await session.execute(
            select(NormalizedProfile).where(NormalizedProfile.security_id == sid)
        )
        profile = profile_result.scalar_one_or_none()

    # Identity fields from securities table
    company_name = (security.name if security else None) or ticker
    exchange = security.exchange if security else None
    currency = (financials.currency if financials else None) or (
        quote.currency if quote else "USD"
    )

    # Profile enrichment fields from profiles table
    sector = profile.sector if profile else None
    industry = profile.industry if profile else None
    logo_url = profile.logo_url if profile else None
    business_summary = (profile.description or "").strip() if profile else ""

    # Classify template when not provided (normal Phase 3 path)
    if template_key is None:
        _profile_ci: CompanyIdentity | None = None
        if profile:
            _profile_ci = CompanyIdentity(
                name=company_name,
                sector=profile.sector,
                industry=profile.industry,
                security_type=profile.asset_type,
            )
        template_key = _classify_template(_profile_ci, financials)

    # Format LLM blocks on the fly
    metrics_block = _format_metrics(ticker, financials, quote)
    leadership_block = _format_leadership(leadership)
    market_intelligence_block = _format_market_intelligence(market_intelligence)

    # Assemble filing excerpt
    if filing is not None:
        parts = [filing.item_1, filing.item_1a, filing.item_7]
        filing_excerpt = "\n\n".join(p for p in parts if p)[:24_000]
    else:
        filing_excerpt = ""

    return StructuredContext(
        ticker=ticker,
        company_name=company_name,
        exchange=exchange,
        currency=currency,
        security_id=str(sid) if sid else None,
        template_key=template_key,
        sector=sector,
        industry=industry,
        logo_url=logo_url,
        metrics_block=metrics_block,
        business_summary=business_summary,
        leadership_block=leadership_block,
        market_intelligence_block=market_intelligence_block,
        filing_excerpt=filing_excerpt,
    )


async def build(ticker: str, session: AsyncSession) -> StructuredContext:
    """Compatibility shim — delegates to ``fetch_providers()``.

    The filing excerpt is no longer fetched here; use ``run_filing()`` in the
    pipeline to fetch and store the SEC filing independently.
    """
    return await fetch_providers(ticker, session)


# ---------------------------------------------------------------------------
# DB load helpers (no external I/O)
# ---------------------------------------------------------------------------


def _check_cache(cache, key: str, ticker: str):
    return cache.get((key, ticker))


async def _load_financials_from_db(
    security_id, session: AsyncSession, ttl_seconds: float | None
) -> Financials | None:
    from datetime import datetime, timezone

    result = await session.execute(
        select(NormalizedFinancials)
        .where(NormalizedFinancials.security_id == security_id)
        .order_by(NormalizedFinancials.updated_at.desc())
        .limit(3)
    )
    rows = result.scalars().all()
    if not rows:
        return None
    if ttl_seconds is not None:
        age = (datetime.now(timezone.utc) - rows[0].updated_at).total_seconds()
        if age >= ttl_seconds:
            return None
    return _rows_to_financials(rows, str(security_id))


async def _load_quote_from_db(security_id, session: AsyncSession) -> Quote | None:
    result = await session.execute(
        select(NormalizedQuote).where(NormalizedQuote.security_id == security_id)
    )
    row = result.scalars().first()
    if row is None or row.price is None:
        return None
    return Quote(
        security_id=str(security_id),
        symbol="",
        price=float(row.price),
        currency=row.currency or "USD",
        source=row.source or "db",
        fetched_at=row.updated_at,
    )


async def _load_leadership_from_db(
    security_id, session: AsyncSession, ttl_seconds: float | None
) -> LeadershipData | None:
    from datetime import datetime, timezone

    result = await session.execute(
        select(LeadershipRow).where(LeadershipRow.security_id == security_id)
    )
    row = result.scalars().first()
    if row is None:
        return None
    if ttl_seconds is not None:
        age = (datetime.now(timezone.utc) - row.updated_at).total_seconds()
        if age >= ttl_seconds:
            return None
    return _row_to_leadership(row)


async def _load_market_intelligence_from_db(
    security_id, session: AsyncSession, ttl_seconds: float | None
) -> MarketIntelligence | None:
    from datetime import datetime, timezone

    result = await session.execute(
        select(MarketIntelligenceRow).where(
            MarketIntelligenceRow.security_id == security_id
        )
    )
    row = result.scalars().first()
    if row is None:
        return None
    if ttl_seconds is not None:
        age = (datetime.now(timezone.utc) - row.updated_at).total_seconds()
        if age >= ttl_seconds:
            return None
    return _row_to_market_intelligence(row)


async def _service_call_with_own_session(method, ticker: str, security_id: str | None):
    """Call a service method with a dedicated DB session.

    Each concurrent task in fetch_providers() gets its own session so they
    can run in parallel without sharing session state.  The session is closed
    after the call regardless of success or failure.
    """
    session_factory = get_session_factory()
    async with session_factory() as own_session:
        return await method(ticker, security_id, own_session)


# ---------------------------------------------------------------------------
# Template classifier
# ---------------------------------------------------------------------------

_MINING_KEYWORDS = {
    "mining",
    "gold",
    "silver",
    "copper",
    "metal",
    "minerals",
    "coal",
    "iron",
    "steel",
    "aluminum",
    "zinc",
    "lithium",
    "uranium",
}
_BIOTECH_KEYWORDS = {
    "biotechnology",
    "pharmaceutical",
    "drug",
    "therapeutics",
    "bioscience",
    "genomics",
    "oncology",
    "vaccine",
    "biologics",
}
_HEALTHCARE_KEYWORDS = {
    "healthcare",
    "health care",
    "medical",
    "hospital",
    "diagnostic",
    "clinical",
}
_ENERGY_KEYWORDS = {
    "energy",
    "oil",
    "gas",
    "petroleum",
    "utilities",
    "power",
    "pipeline",
    "lng",
    "refin",
}
_TECH_KEYWORDS = {
    "technology",
    "software",
    "semiconductor",
    "internet",
    "communications",
    "hardware",
    "electronics",
    "cloud",
    "saas",
}
_REIT_KEYWORDS = {
    "real estate investment trust",
    "reit",
    "real estate",
}
_FINANCIAL_KEYWORDS = {
    "financial",
    "banking",
    "bank",
    "insurance",
    "investment",
    "asset management",
    "brokerage",
}


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

    sector_text = " ".join(
        filter(
            None,
            [
                profile.sector if profile else None,
                profile.industry if profile else None,
            ],
        )
    ).lower()

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
    if _matches(_REIT_KEYWORDS):
        return "reit" if is_revenue_generating else "pre_revenue"
    if _matches(_FINANCIAL_KEYWORDS):
        return "financial" if is_revenue_generating else "pre_revenue"

    return "general" if is_revenue_generating else "pre_revenue"


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
            prior = (
                financials.income[idx + 1] if idx + 1 < len(financials.income) else None
            )
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
        net_label = (
            "Net cash" if (bs.net_debt is not None and bs.net_debt < 0) else "Net debt"
        )
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
        m = financials.metrics
        lines.append("\n--- Valuation Metrics ---")
        lines.append(f"  Market cap:        {_fmt(m.market_cap)}")
        lines.append(f"  Enterprise value:  {_fmt(m.enterprise_value)}")
        lines.append(
            f"  P/E (trailing):    {m.pe_ratio:.1f}x"
            if m.pe_ratio
            else "  P/E (trailing):    N/A"
        )
        lines.append(
            f"  P/E (forward):     {m.forward_pe:.1f}x"
            if m.forward_pe
            else "  P/E (forward):     N/A"
        )
        lines.append(
            f"  PEG ratio:         {m.peg_ratio:.2f}"
            if m.peg_ratio
            else "  PEG ratio:         N/A"
        )
        lines.append(
            f"  EV/EBITDA:         {m.ev_ebitda:.1f}x"
            if m.ev_ebitda
            else "  EV/EBITDA:         N/A"
        )
        lines.append(
            f"  EV/Revenue:        {m.enterprise_to_revenue:.2f}x"
            if m.enterprise_to_revenue
            else "  EV/Revenue:        N/A"
        )
        lines.append(
            f"  Price/Book:        {m.price_to_book:.2f}x"
            if m.price_to_book
            else "  Price/Book:        N/A"
        )
        lines.append(
            f"  ROE:               {m.roe * 100:.1f}%"
            if m.roe
            else "  ROE:               N/A"
        )
        lines.append(
            f"  ROA:               {m.return_on_assets * 100:.1f}%"
            if m.return_on_assets
            else "  ROA:               N/A"
        )
        lines.append(
            f"  Revenue growth:    {m.revenue_growth * 100:.1f}%  (trailing YoY)"
            if m.revenue_growth
            else "  Revenue growth:    N/A"
        )
        lines.append(
            f"  Earnings growth:   {m.earnings_growth * 100:.1f}%  (trailing YoY)"
            if m.earnings_growth
            else "  Earnings growth:   N/A"
        )
        lines.append(
            f"  EPS (trailing):    ${m.eps:.2f}"
            if m.eps
            else "  EPS (trailing):    N/A"
        )
        lines.append(
            f"  EPS (forward):     ${m.forward_eps:.2f}"
            if m.forward_eps
            else "  EPS (forward):     N/A"
        )
        lines.append(
            f"  Dividend yield:    {m.dividend_yield * 100:.2f}%"
            if m.dividend_yield
            else "  Dividend yield:    N/A"
        )
        lines.append(
            f"  Dividend rate:     ${m.dividend_rate:.2f}/share"
            if m.dividend_rate
            else "  Dividend rate:     N/A"
        )
        lines.append(
            f"  Payout ratio:      {m.payout_ratio * 100:.1f}%"
            if m.payout_ratio
            else "  Payout ratio:      N/A"
        )
        lines.append(
            f"  Beta:              {m.beta:.2f}"
            if m.beta
            else "  Beta:              N/A"
        )
        lines.append(
            f"  Debt/Equity:       {m.debt_to_equity:.2f}x"
            if m.debt_to_equity
            else "  Debt/Equity:       N/A"
        )
        lines.append(
            f"  Quick ratio:       {m.quick_ratio:.2f}"
            if m.quick_ratio
            else "  Quick ratio:       N/A"
        )
        lines.append(
            f"  Current ratio:     {m.current_ratio:.2f}"
            if m.current_ratio
            else "  Current ratio:     N/A"
        )
        if (
            m.market_cap
            and financials.cash_flow
            and financials.cash_flow[0].free_cash_flow
        ):
            fcf_yield = financials.cash_flow[0].free_cash_flow / m.market_cap * 100
            lines.append(f"  FCF yield:         {fcf_yield:.1f}%")

    return "\n".join(lines)


def _format_leadership(leadership: LeadershipData | None) -> str:
    if not leadership:
        return ""

    lines: list[str] = ["--- Leadership & Governance ---"]

    if leadership.officers:
        lines.append("Officers:")
        for officer in leadership.officers:
            pay_str = f", ${officer.total_pay:,} last FY" if officer.total_pay else ""
            age_str = f", age {officer.age}" if officer.age else ""
            lines.append(f"  {officer.title:<40} {officer.name}{age_str}{pay_str}")

    if leadership.held_percent_insiders is not None:
        lines.append(
            f"Insider ownership:       {leadership.held_percent_insiders * 100:.2f}%"
        )
    if leadership.held_percent_institutions is not None:
        lines.append(
            f"Institutional ownership: {leadership.held_percent_institutions * 100:.2f}%"
        )

    risk_fields = [
        ("audit_risk", "Audit"),
        ("board_risk", "Board"),
        ("compensation_risk", "Compensation"),
        ("overall_governance_risk", "Overall"),
    ]
    risk_parts = [
        f"{label}: {getattr(leadership, field)}"
        for field, label in risk_fields
        if getattr(leadership, field) is not None
    ]
    if risk_parts:
        lines.append("Governance risk (1 = low, 10 = high):")
        lines.append("  " + "  |  ".join(risk_parts))

    return "\n".join(lines)


def _format_market_intelligence(mi: MarketIntelligence | None) -> str:
    if not mi:
        return ""

    lines: list[str] = []

    # Analyst consensus
    if any(
        v is not None
        for v in [mi.recommendation, mi.analyst_count, mi.target_mean_price]
    ):
        lines.append("--- Analyst Consensus ---")
        if mi.recommendation or mi.recommendation_score is not None:
            rec_str = mi.recommendation or "N/A"
            score_str = (
                f"  (score {mi.recommendation_score:.1f}/5.0)"
                if mi.recommendation_score
                else ""
            )
            count_str = f"  —  {mi.analyst_count} analysts" if mi.analyst_count else ""
            lines.append(f"  Recommendation:    {rec_str}{score_str}{count_str}")
        if mi.target_mean_price is not None:
            median_str = (
                f", median ${mi.target_median_price:,.2f}"
                if mi.target_median_price
                else ""
            )
            lines.append(
                f"  Price targets:     mean ${mi.target_mean_price:,.2f}{median_str}"
            )
        if mi.target_high_price is not None and mi.target_low_price is not None:
            lines.append(
                f"  Target range:      ${mi.target_low_price:,.2f} – ${mi.target_high_price:,.2f}"
            )

    # Short interest
    if any(
        v is not None
        for v in [mi.shares_short, mi.short_ratio, mi.short_percent_of_float]
    ):
        lines.append("--- Short Interest ---")
        if mi.shares_short is not None:
            lines.append(f"  Shares short:      {mi.shares_short:,}")
        if mi.short_ratio is not None:
            lines.append(f"  Days to cover:     {mi.short_ratio:.1f}")
        if mi.short_percent_of_float is not None:
            lines.append(f"  Short % of float:  {mi.short_percent_of_float * 100:.2f}%")

    # Price context
    if any(v is not None for v in [mi.fifty_two_week_high, mi.fifty_day_average]):
        lines.append("--- Price Context ---")
        if mi.fifty_two_week_high is not None and mi.fifty_two_week_low is not None:
            lines.append(
                f"  52-week range:     ${mi.fifty_two_week_low:,.2f} – ${mi.fifty_two_week_high:,.2f}"
            )
        if mi.fifty_day_average is not None:
            lines.append(f"  50-day average:    ${mi.fifty_day_average:,.2f}")
        if mi.two_hundred_day_average is not None:
            lines.append(f"  200-day average:   ${mi.two_hundred_day_average:,.2f}")

    # Peer companies
    if mi.peers:
        lines.append("--- Peer Companies ---")
        lines.append(f"  Sector peers:      {', '.join(mi.peers)}")

    return "\n".join(lines)
