from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import cache
from core.config import settings
from core.exceptions import ProviderUnavailableError
from db.pg_models import (
    LeadershipRow,
    MarketIntelligenceRow,
    NormalizedFinancials,
    NormalizedProfile,
    NormalizedQuote,
    RawFinancials,
    RawProfile,
    RawQuote,
)
from models.market_data import (
    CompanyIdentity,
    Financials,
    LeadershipData,
    MarketIntelligence,
    Quote,
)
from services.provider_registry import ProviderRegistry


def _financials_sufficient(data: Financials) -> bool:
    return bool(data.income or data.balance_sheet or data.cash_flow)


logger = logging.getLogger(__name__)


class MarketDataService:
    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    async def get_quote(
        self,
        ticker: str,
        security_id: str | None,
        session: AsyncSession,
        exchange_hint: str | None = None,
    ) -> Quote:
        cache_key = ("quote", ticker)

        # 1. In-process cache
        cached = cache.get(cache_key)
        if cached:
            return cached

        # 2. PostgreSQL normalized layer
        if security_id:
            result = await session.execute(
                select(NormalizedQuote).where(
                    NormalizedQuote.security_id == security_id
                )
            )
            row = result.scalars().first()
            if row and row.price is not None:
                quote = Quote(
                    security_id=str(row.security_id),
                    symbol=ticker,
                    price=float(row.price),
                    currency=row.currency or "USD",
                    source=row.source or "db",
                    fetched_at=row.updated_at,
                )
                cache.set(cache_key, quote, settings.quote_ttl_seconds)
                return quote

        # 3. Try adapters in priority order
        adapters = self._registry.for_capability("quote")
        attempted: list[str] = []
        for adapter in adapters:
            response = await adapter.get_quote(ticker)
            attempted.append(adapter.name)
            if response.data is None:
                logger.warning(
                    "adapter quote miss",
                    extra={"ticker": ticker, "provider": adapter.name},
                )
                continue

            quote = response.data
            if security_id:
                quote.security_id = security_id
                await self._persist_quote(quote, response.raw, adapter.name, session)

            logger.info(
                "quote fetched",
                extra={
                    "ticker": ticker,
                    "provider": adapter.name,
                    "price": quote.price,
                },
            )
            cache.set(cache_key, quote, settings.quote_ttl_seconds)
            return quote

        logger.error(
            "all quote providers exhausted",
            extra={"ticker": ticker, "attempted": attempted},
        )
        raise ProviderUnavailableError(ticker, attempted)

    async def get_financials(
        self,
        ticker: str,
        security_id: str | None,
        session: AsyncSession,
        exchange_hint: str | None = None,
    ) -> Financials:
        cache_key = ("financials", ticker)

        # 1. In-process cache
        cached = cache.get(cache_key)
        if cached:
            return cached

        # 2. PostgreSQL normalized layer
        if security_id:
            result = await session.execute(
                select(NormalizedFinancials)
                .where(NormalizedFinancials.security_id == security_id)
                .order_by(NormalizedFinancials.updated_at.desc())
                .limit(3)
            )
            rows = result.scalars().all()
            if rows:
                from datetime import datetime, timezone

                age = (datetime.now(timezone.utc) - rows[0].updated_at).total_seconds()
                if age < settings.financials_ttl_seconds:
                    financials = _rows_to_financials(rows, security_id)
                    cache.set(cache_key, financials, settings.financials_ttl_seconds)
                    return financials

        # 3. Try adapters in priority order
        adapters = self._registry.for_capability("financials")
        attempted: list[str] = []
        for adapter in adapters:
            response = await adapter.get_financials(ticker)
            attempted.append(adapter.name)
            if response.data is None or not _financials_sufficient(response.data):
                logger.warning(
                    "adapter financials miss",
                    extra={"ticker": ticker, "provider": adapter.name},
                )
                continue

            financials = response.data
            if security_id:
                financials.security_id = security_id
                await self._persist_financials(
                    financials, response.raw, ticker, adapter.name, session
                )

            logger.info(
                "financials fetched", extra={"ticker": ticker, "provider": adapter.name}
            )
            cache.set(cache_key, financials, settings.financials_ttl_seconds)
            return financials

        logger.error(
            "all financials providers exhausted",
            extra={"ticker": ticker, "attempted": attempted},
        )
        raise ProviderUnavailableError(ticker, attempted)

    async def get_profile(
        self,
        ticker: str,
        security_id: str | None,
        session: AsyncSession,
        exchange_hint: str | None = None,
    ) -> CompanyIdentity:
        cache_key = ("profile", ticker)

        cached = cache.get(cache_key)
        if cached:
            return cached

        # 1. PostgreSQL normalized profiles cache
        if security_id:
            result = await session.execute(
                select(NormalizedProfile).where(
                    NormalizedProfile.security_id == security_id
                )
            )
            profile_row = result.scalars().first()
            if profile_row:
                from datetime import datetime, timezone

                age = (
                    datetime.now(timezone.utc) - profile_row.updated_at
                ).total_seconds()
                if age < settings.profile_ttl_seconds:
                    identity = _profile_row_to_identity(profile_row, security_id)
                    cache.set(cache_key, identity, settings.profile_ttl_seconds)
                    return identity

        # 2. Fetch from adapters
        identity = CompanyIdentity(name=ticker, security_id=security_id)
        adapters = self._registry.for_capability("profile")
        raw_profile: dict = {}
        provider_name = "unknown"
        for adapter in adapters:
            response = await adapter.get_profile(ticker)
            if response.data is None:
                continue
            ap = response.data
            raw_profile = response.raw
            provider_name = adapter.name
            identity.description = identity.description or ap.description
            identity.sector = identity.sector or ap.sector
            identity.industry = identity.industry or ap.industry
            identity.employees = identity.employees or ap.employees
            identity.country = identity.country or ap.country
            identity.security_type = identity.security_type or ap.security_type
            identity.logo_url = identity.logo_url or ap.logo_url
            if ap.exchange:
                identity.exchange = ap.exchange
            if ap.name and ap.name != ticker:
                identity.name = ap.name
            break

        # 3. Persist to profiles + raw_profiles
        if security_id:
            await self._persist_profile_raw(
                security_id, ticker, provider_name, raw_profile, session
            )
            await self._persist_profile(identity, security_id, session)

        cache.set(cache_key, identity, settings.profile_ttl_seconds)
        return identity

    async def get_leadership(
        self,
        ticker: str,
        security_id: str | None,
        session: AsyncSession,
        exchange_hint: str | None = None,
    ) -> LeadershipData | None:
        cache_key = ("leadership", ticker)

        # 1. In-process cache
        cached = cache.get(cache_key)
        if cached:
            return cached

        # 2. PostgreSQL normalized layer
        if security_id:
            result = await session.execute(
                select(LeadershipRow).where(LeadershipRow.security_id == security_id)
            )
            row = result.scalars().first()
            if row:
                from datetime import datetime, timezone

                age = (datetime.now(timezone.utc) - row.updated_at).total_seconds()
                if age < settings.leadership_ttl_seconds:
                    leadership = _row_to_leadership(row)
                    cache.set(cache_key, leadership, settings.leadership_ttl_seconds)
                    return leadership

        # 3. Try adapters in priority order
        adapters = self._registry.for_capability("leadership")
        for adapter in adapters:
            try:
                response = await adapter.get_leadership(ticker)
                if response.data is None:
                    logger.warning(
                        "adapter leadership miss",
                        extra={"ticker": ticker, "provider": adapter.name},
                    )
                    continue

                leadership = response.data
                if security_id:
                    leadership.security_id = security_id
                    await self._persist_leadership(leadership, adapter.name, session)

                logger.info(
                    "leadership fetched",
                    extra={"ticker": ticker, "provider": adapter.name},
                )
                cache.set(cache_key, leadership, settings.leadership_ttl_seconds)
                return leadership
            except Exception:
                logger.warning(
                    "adapter leadership error",
                    extra={"ticker": ticker, "provider": adapter.name},
                    exc_info=True,
                )
                continue

        logger.warning("all leadership providers exhausted", extra={"ticker": ticker})
        return None

    async def get_market_intelligence(
        self,
        ticker: str,
        security_id: str | None,
        session: AsyncSession,
        exchange_hint: str | None = None,
    ) -> MarketIntelligence | None:
        cache_key = ("market_intelligence", ticker)

        # 1. In-process cache
        cached = cache.get(cache_key)
        if cached:
            return cached

        # 2. PostgreSQL normalized layer
        if security_id:
            result = await session.execute(
                select(MarketIntelligenceRow).where(
                    MarketIntelligenceRow.security_id == security_id
                )
            )
            row = result.scalars().first()
            if row:
                from datetime import datetime, timezone

                age = (datetime.now(timezone.utc) - row.updated_at).total_seconds()
                if age < settings.market_intelligence_ttl_seconds:
                    mi = _row_to_market_intelligence(row)
                    cache.set(cache_key, mi, settings.market_intelligence_ttl_seconds)
                    return mi

        # 3. Try adapters in priority order
        adapters = self._registry.for_capability("market_intelligence")
        for adapter in adapters:
            try:
                response = await adapter.get_market_intelligence(ticker)
                if response.data is None:
                    logger.warning(
                        "adapter market_intelligence miss",
                        extra={"ticker": ticker, "provider": adapter.name},
                    )
                    continue

                mi = response.data

                # Enrich with sector peers from Finnhub (soft-fail, returns [] on error)
                from adapters.finnhub import FinnhubAdapter

                finnhub = self._registry.get("finnhub")
                if isinstance(finnhub, FinnhubAdapter):
                    mi.peers = await finnhub.get_peers(ticker)

                if security_id:
                    mi.security_id = security_id
                    await self._persist_market_intelligence(mi, adapter.name, session)

                logger.info(
                    "market_intelligence fetched",
                    extra={"ticker": ticker, "provider": adapter.name},
                )
                cache.set(cache_key, mi, settings.market_intelligence_ttl_seconds)
                return mi
            except Exception:
                logger.warning(
                    "adapter market_intelligence error",
                    extra={"ticker": ticker, "provider": adapter.name},
                    exc_info=True,
                )
                continue

        logger.warning(
            "all market_intelligence providers exhausted", extra={"ticker": ticker}
        )
        return None

    # -------------------------------------------------------------------------
    # Persistence helpers
    # -------------------------------------------------------------------------

    async def _persist_quote(
        self,
        quote: Quote,
        raw: dict,
        provider: str,
        session: AsyncSession,
    ) -> None:
        await session.execute(
            insert(RawQuote).values(
                security_id=quote.security_id,
                provider=provider,
                symbol=quote.symbol,
                raw_data=raw,
            )
        )
        await session.execute(
            insert(NormalizedQuote)
            .values(
                security_id=quote.security_id,
                price=quote.price,
                currency=quote.currency,
                source=provider,
            )
            .on_conflict_do_update(
                index_elements=["security_id"],
                set_={
                    "price": quote.price,
                    "currency": quote.currency,
                    "source": provider,
                },
            )
        )
        await session.commit()

    async def _persist_financials(
        self,
        financials: Financials,
        raw: dict,
        ticker: str,
        provider: str,
        session: AsyncSession,
    ) -> None:
        await session.execute(
            insert(RawFinancials).values(
                security_id=financials.security_id,
                provider=provider,
                symbol=ticker,
                period="latest",
                raw_data=raw,
            )
        )

        for income in financials.income:
            values: dict = {
                "security_id": financials.security_id,
                "period": income.period,
                "fiscal_year": income.fiscal_year,
                "revenue": income.revenue,
                "gross_profit": income.gross_profit,
                "operating_income": income.operating_income,
                "net_income": income.net_income,
                "ebitda": income.ebitda,
                "currency": financials.currency,
                "sources": [provider],
            }

            cf = next(
                (c for c in financials.cash_flow if c.period == income.period), None
            )
            if cf:
                values.update(
                    {
                        "operating_cash_flow": cf.operating_cash_flow,
                        "capex": cf.capex,
                        "free_cash_flow": cf.free_cash_flow,
                    }
                )

            if (
                financials.balance_sheet
                and financials.balance_sheet.period == income.period
            ):
                bs = financials.balance_sheet
                values.update(
                    {
                        "cash": bs.cash,
                        "total_debt": bs.total_debt,
                        "net_debt": bs.net_debt,
                        "total_equity": bs.total_equity,
                        "total_assets": bs.total_assets,
                    }
                )

            if financials.metrics and financials.metrics.period == income.period:
                m = financials.metrics
                values.update(
                    {
                        "market_cap": m.market_cap,
                        "enterprise_value": m.enterprise_value,
                        "pe_ratio": m.pe_ratio,
                        "forward_pe": m.forward_pe,
                        "peg_ratio": m.peg_ratio,
                        "ev_ebitda": m.ev_ebitda,
                        "enterprise_to_revenue": m.enterprise_to_revenue,
                        "price_to_book": m.price_to_book,
                        "eps": m.eps,
                        "forward_eps": m.forward_eps,
                        "roe": m.roe,
                        "return_on_assets": m.return_on_assets,
                        "revenue_growth": m.revenue_growth,
                        "earnings_growth": m.earnings_growth,
                        "dividend_yield": m.dividend_yield,
                        "dividend_rate": m.dividend_rate,
                        "payout_ratio": m.payout_ratio,
                        "beta": m.beta,
                        "debt_to_equity": m.debt_to_equity,
                        "quick_ratio": m.quick_ratio,
                        "current_ratio": m.current_ratio,
                    }
                )

            await session.execute(
                insert(NormalizedFinancials)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=["security_id", "period"],
                    set_={
                        k: v
                        for k, v in values.items()
                        if k not in ("security_id", "period")
                    },
                )
            )

        await session.commit()

    async def _persist_profile_raw(
        self,
        security_id: str,
        ticker: str,
        provider: str,
        raw: dict,
        session: AsyncSession,
    ) -> None:
        if not raw:
            return
        await session.execute(
            insert(RawProfile).values(
                security_id=security_id,
                provider=provider,
                symbol=ticker,
                raw_data=raw,
            )
        )
        await session.commit()

    async def _persist_profile(
        self,
        identity: CompanyIdentity,
        security_id: str,
        session: AsyncSession,
    ) -> None:
        values = {
            "security_id": security_id,
            "sector": identity.sector,
            "industry": identity.industry,
            "country": identity.country,
            "asset_type": identity.security_type,
            "logo_url": identity.logo_url,
            "description": identity.description,
            "employees": identity.employees,
            "source": "adapter",
        }
        await session.execute(
            insert(NormalizedProfile)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_profiles_security_id",
                set_={k: v for k, v in values.items() if k != "security_id"},
            )
        )
        await session.commit()

    async def _persist_leadership(
        self,
        leadership: LeadershipData,
        provider: str,
        session: AsyncSession,
    ) -> None:
        officers_json = [o.model_dump() for o in leadership.officers]
        await session.execute(
            insert(LeadershipRow)
            .values(
                security_id=leadership.security_id,
                officers=officers_json,
                held_percent_insiders=leadership.held_percent_insiders,
                held_percent_institutions=leadership.held_percent_institutions,
                audit_risk=leadership.audit_risk,
                board_risk=leadership.board_risk,
                compensation_risk=leadership.compensation_risk,
                overall_governance_risk=leadership.overall_governance_risk,
                source=provider,
            )
            .on_conflict_do_update(
                index_elements=["security_id"],
                set_={
                    "officers": officers_json,
                    "held_percent_insiders": leadership.held_percent_insiders,
                    "held_percent_institutions": leadership.held_percent_institutions,
                    "audit_risk": leadership.audit_risk,
                    "board_risk": leadership.board_risk,
                    "compensation_risk": leadership.compensation_risk,
                    "overall_governance_risk": leadership.overall_governance_risk,
                    "source": provider,
                },
            )
        )
        await session.commit()

    async def _persist_market_intelligence(
        self,
        mi: MarketIntelligence,
        provider: str,
        session: AsyncSession,
    ) -> None:
        values = {
            "security_id": mi.security_id,
            "recommendation": mi.recommendation,
            "recommendation_score": mi.recommendation_score,
            "analyst_count": mi.analyst_count,
            "target_mean_price": mi.target_mean_price,
            "target_median_price": mi.target_median_price,
            "target_high_price": mi.target_high_price,
            "target_low_price": mi.target_low_price,
            "shares_short": mi.shares_short,
            "short_ratio": mi.short_ratio,
            "short_percent_of_float": mi.short_percent_of_float,
            "fifty_two_week_high": mi.fifty_two_week_high,
            "fifty_two_week_low": mi.fifty_two_week_low,
            "fifty_day_average": mi.fifty_day_average,
            "two_hundred_day_average": mi.two_hundred_day_average,
            "peers": mi.peers or None,
            "source": provider,
        }
        await session.execute(
            insert(MarketIntelligenceRow)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["security_id"],
                set_={k: v for k, v in values.items() if k != "security_id"},
            )
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Row → Pydantic conversion helpers
# ---------------------------------------------------------------------------


def _rows_to_financials(
    rows: list[NormalizedFinancials], security_id: str
) -> Financials:
    from models.market_data import BalanceSheet, CashFlow, IncomeStatement, KeyMetrics

    income = [
        IncomeStatement(
            period=row.period,
            fiscal_year=row.fiscal_year,
            revenue=float(row.revenue) if row.revenue is not None else None,
            gross_profit=float(row.gross_profit)
            if row.gross_profit is not None
            else None,
            operating_income=float(row.operating_income)
            if row.operating_income is not None
            else None,
            net_income=float(row.net_income) if row.net_income is not None else None,
            ebitda=float(row.ebitda) if row.ebitda is not None else None,
        )
        for row in rows
    ]

    latest = rows[0]
    balance: BalanceSheet | None = None
    if any(
        getattr(latest, f) is not None for f in ("cash", "total_debt", "total_assets")
    ):
        balance = BalanceSheet(
            period=latest.period,
            cash=float(latest.cash) if latest.cash is not None else None,
            total_debt=float(latest.total_debt)
            if latest.total_debt is not None
            else None,
            net_debt=float(latest.net_debt) if latest.net_debt is not None else None,
            total_equity=float(latest.total_equity)
            if latest.total_equity is not None
            else None,
            total_assets=float(latest.total_assets)
            if latest.total_assets is not None
            else None,
        )

    cash_flow = [
        CashFlow(
            period=row.period,
            operating_cash_flow=float(row.operating_cash_flow)
            if row.operating_cash_flow is not None
            else None,
            capex=float(row.capex) if row.capex is not None else None,
            free_cash_flow=float(row.free_cash_flow)
            if row.free_cash_flow is not None
            else None,
        )
        for row in rows
    ]

    def _f(v) -> float | None:
        return float(v) if v is not None else None

    metrics: KeyMetrics | None = None
    if latest.market_cap is not None:
        metrics = KeyMetrics(
            period=latest.period,
            market_cap=_f(latest.market_cap),
            enterprise_value=_f(latest.enterprise_value),
            pe_ratio=_f(latest.pe_ratio),
            forward_pe=_f(latest.forward_pe),
            peg_ratio=_f(latest.peg_ratio),
            ev_ebitda=_f(latest.ev_ebitda),
            enterprise_to_revenue=_f(latest.enterprise_to_revenue),
            price_to_book=_f(latest.price_to_book),
            eps=_f(latest.eps),
            forward_eps=_f(latest.forward_eps),
            roe=_f(latest.roe),
            return_on_assets=_f(latest.return_on_assets),
            revenue_growth=_f(latest.revenue_growth),
            earnings_growth=_f(latest.earnings_growth),
            dividend_yield=_f(latest.dividend_yield),
            dividend_rate=_f(latest.dividend_rate),
            payout_ratio=_f(latest.payout_ratio),
            beta=_f(latest.beta),
            debt_to_equity=_f(latest.debt_to_equity),
            quick_ratio=_f(latest.quick_ratio),
            current_ratio=_f(latest.current_ratio),
        )

    return Financials(
        security_id=security_id,
        currency=latest.currency or "USD",
        income=income,
        balance_sheet=balance,
        cash_flow=cash_flow,
        metrics=metrics,
    )


def _row_to_leadership(row: LeadershipRow) -> LeadershipData:
    from models.market_data import CompanyOfficer

    officers = [
        CompanyOfficer(
            name=o.get("name", ""),
            title=o.get("title", ""),
            age=o.get("age"),
            total_pay=o.get("total_pay"),
        )
        for o in (row.officers or [])
    ]
    return LeadershipData(
        security_id=str(row.security_id),
        officers=officers,
        held_percent_insiders=float(row.held_percent_insiders)
        if row.held_percent_insiders is not None
        else None,
        held_percent_institutions=float(row.held_percent_institutions)
        if row.held_percent_institutions is not None
        else None,
        audit_risk=row.audit_risk,
        board_risk=row.board_risk,
        compensation_risk=row.compensation_risk,
        overall_governance_risk=row.overall_governance_risk,
    )


def _row_to_market_intelligence(row: MarketIntelligenceRow) -> MarketIntelligence:
    def _f(v) -> float | None:
        return float(v) if v is not None else None

    return MarketIntelligence(
        security_id=str(row.security_id),
        recommendation=row.recommendation,
        recommendation_score=_f(row.recommendation_score),
        analyst_count=row.analyst_count,
        target_mean_price=_f(row.target_mean_price),
        target_median_price=_f(row.target_median_price),
        target_high_price=_f(row.target_high_price),
        target_low_price=_f(row.target_low_price),
        shares_short=row.shares_short,
        short_ratio=_f(row.short_ratio),
        short_percent_of_float=_f(row.short_percent_of_float),
        fifty_two_week_high=_f(row.fifty_two_week_high),
        fifty_two_week_low=_f(row.fifty_two_week_low),
        fifty_day_average=_f(row.fifty_day_average),
        two_hundred_day_average=_f(row.two_hundred_day_average),
        peers=list(row.peers) if row.peers else [],
    )


def _profile_row_to_identity(
    row: NormalizedProfile, security_id: str
) -> CompanyIdentity:
    """Reconstruct a CompanyIdentity from a profiles row (enrichment fields only)."""
    return CompanyIdentity(
        security_id=security_id,
        name="",  # name lives in the securities table, not profiles
        sector=row.sector,
        industry=row.industry,
        country=row.country,
        security_type=row.asset_type,
        logo_url=row.logo_url,
        description=row.description,
        employees=row.employees,
    )
