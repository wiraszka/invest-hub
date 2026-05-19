from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import cache
from core.config import settings
from core.exceptions import ProviderUnavailableError
from db.pg_models import (
    NormalizedFinancials,
    NormalizedQuote,
    RawFinancials,
    RawQuote,
)
from models.market_data import CompanyIdentity, Financials, Quote
from services.identity import resolve_identity
from services.provider_registry import ProviderRegistry


class MarketDataService:
    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    async def get_quote(
        self,
        ticker: str,
        session: AsyncSession,
        exchange_hint: str | None = None,
    ) -> Quote:
        cache_key = ("quote", ticker)

        # 1. In-process cache
        cached = cache.get(cache_key)
        if cached:
            return cached

        # 2. PostgreSQL normalized layer
        identity = await resolve_identity(ticker, "fmp", session, exchange_hint)
        if identity.canonical_id:
            result = await session.execute(
                select(NormalizedQuote).where(NormalizedQuote.canonical_id == identity.canonical_id)
            )
            row = result.scalars().first()
            if row and row.price is not None:
                quote = Quote(
                    canonical_id=str(row.canonical_id),
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
                continue

            quote = response.data
            if identity.canonical_id:
                quote.canonical_id = identity.canonical_id
                await self._persist_quote(quote, response.raw, adapter.name, session)

            cache.set(cache_key, quote, settings.quote_ttl_seconds)
            return quote

        raise ProviderUnavailableError(ticker, attempted)

    async def get_financials(
        self,
        ticker: str,
        session: AsyncSession,
        exchange_hint: str | None = None,
    ) -> Financials:
        cache_key = ("financials", ticker)

        # 1. In-process cache
        cached = cache.get(cache_key)
        if cached:
            return cached

        # 2. PostgreSQL normalized layer — return most recent period if fresh enough
        identity = await resolve_identity(ticker, "fmp", session, exchange_hint)
        if identity.canonical_id:
            result = await session.execute(
                select(NormalizedFinancials)
                .where(NormalizedFinancials.canonical_id == identity.canonical_id)
                .order_by(NormalizedFinancials.updated_at.desc())
                .limit(3)
            )
            rows = result.scalars().all()
            if rows:
                from datetime import datetime, timezone
                age = (datetime.now(timezone.utc) - rows[0].updated_at).total_seconds()
                if age < settings.financials_ttl_seconds:
                    financials = _rows_to_financials(rows, identity.canonical_id)
                    cache.set(cache_key, financials, settings.financials_ttl_seconds)
                    return financials

        # 3. Try adapters in priority order
        adapters = self._registry.for_capability("financials")
        attempted: list[str] = []
        for adapter in adapters:
            response = await adapter.get_financials(ticker)
            attempted.append(adapter.name)
            if response.data is None:
                continue

            financials = response.data
            if identity.canonical_id:
                financials.canonical_id = identity.canonical_id
                await self._persist_financials(financials, response.raw, ticker, adapter.name, session)

            cache.set(cache_key, financials, settings.financials_ttl_seconds)
            return financials

        raise ProviderUnavailableError(ticker, attempted)

    async def get_profile(
        self,
        ticker: str,
        session: AsyncSession,
        exchange_hint: str | None = None,
    ) -> CompanyIdentity:
        cache_key = ("profile", ticker)

        cached = cache.get(cache_key)
        if cached:
            return cached

        # Identity resolution itself queries xref + OpenFIGI
        identity = await resolve_identity(ticker, "fmp", session, exchange_hint)
        if identity.name != ticker:
            cache.set(cache_key, identity, settings.profile_ttl_seconds)
            return identity

        # Fall back to adapter profile if identity is still just a stub
        adapters = self._registry.for_capability("profile")
        attempted: list[str] = []
        for adapter in adapters:
            response = await adapter.get_profile(ticker)
            attempted.append(adapter.name)
            if response.data is None:
                continue
            profile = response.data
            cache.set(cache_key, profile, settings.profile_ttl_seconds)
            return profile

        raise ProviderUnavailableError(ticker, attempted)

    async def _persist_quote(
        self,
        quote: Quote,
        raw: dict,
        provider: str,
        session: AsyncSession,
    ) -> None:
        await session.execute(
            insert(RawQuote).values(
                canonical_id=quote.canonical_id,
                provider=provider,
                symbol=quote.symbol,
                raw_data=raw,
            )
        )
        await session.execute(
            insert(NormalizedQuote)
            .values(
                canonical_id=quote.canonical_id,
                price=quote.price,
                currency=quote.currency,
                source=provider,
            )
            .on_conflict_do_update(
                index_elements=["canonical_id"],
                set_={"price": quote.price, "currency": quote.currency, "source": provider},
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
                canonical_id=financials.canonical_id,
                provider=provider,
                symbol=ticker,
                period="latest",
                raw_data=raw,
            )
        )

        for income in financials.income:
            values: dict = {
                "canonical_id": financials.canonical_id,
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

            cf = next((c for c in financials.cash_flow if c.period == income.period), None)
            if cf:
                values.update({
                    "operating_cash_flow": cf.operating_cash_flow,
                    "capex": cf.capex,
                    "free_cash_flow": cf.free_cash_flow,
                })

            if financials.balance_sheet and financials.balance_sheet.period == income.period:
                bs = financials.balance_sheet
                values.update({
                    "cash": bs.cash,
                    "total_debt": bs.total_debt,
                    "net_debt": bs.net_debt,
                    "total_equity": bs.total_equity,
                    "total_assets": bs.total_assets,
                })

            if financials.metrics and financials.metrics.period == income.period:
                m = financials.metrics
                values.update({
                    "market_cap": m.market_cap,
                    "enterprise_value": m.enterprise_value,
                    "pe_ratio": m.pe_ratio,
                    "ev_ebitda": m.ev_ebitda,
                    "price_to_book": m.price_to_book,
                    "roe": m.roe,
                })

            await session.execute(
                insert(NormalizedFinancials)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=["canonical_id", "period"],
                    set_={k: v for k, v in values.items() if k not in ("canonical_id", "period")},
                )
            )

        await session.commit()


def _rows_to_financials(rows: list[NormalizedFinancials], canonical_id: str) -> Financials:
    from models.market_data import BalanceSheet, CashFlow, IncomeStatement, KeyMetrics

    income = [
        IncomeStatement(
            period=row.period,
            fiscal_year=row.fiscal_year,
            revenue=float(row.revenue) if row.revenue is not None else None,
            gross_profit=float(row.gross_profit) if row.gross_profit is not None else None,
            operating_income=float(row.operating_income) if row.operating_income is not None else None,
            net_income=float(row.net_income) if row.net_income is not None else None,
            ebitda=float(row.ebitda) if row.ebitda is not None else None,
        )
        for row in rows
    ]

    latest = rows[0]
    balance: BalanceSheet | None = None
    if any(getattr(latest, f) is not None for f in ("cash", "total_debt", "total_assets")):
        balance = BalanceSheet(
            period=latest.period,
            cash=float(latest.cash) if latest.cash is not None else None,
            total_debt=float(latest.total_debt) if latest.total_debt is not None else None,
            net_debt=float(latest.net_debt) if latest.net_debt is not None else None,
            total_equity=float(latest.total_equity) if latest.total_equity is not None else None,
            total_assets=float(latest.total_assets) if latest.total_assets is not None else None,
        )

    cash_flow = [
        CashFlow(
            period=row.period,
            operating_cash_flow=float(row.operating_cash_flow) if row.operating_cash_flow is not None else None,
            capex=float(row.capex) if row.capex is not None else None,
            free_cash_flow=float(row.free_cash_flow) if row.free_cash_flow is not None else None,
        )
        for row in rows
    ]

    metrics: KeyMetrics | None = None
    if latest.market_cap is not None:
        metrics = KeyMetrics(
            period=latest.period,
            market_cap=float(latest.market_cap),
            enterprise_value=float(latest.enterprise_value) if latest.enterprise_value is not None else None,
            pe_ratio=float(latest.pe_ratio) if latest.pe_ratio is not None else None,
            ev_ebitda=float(latest.ev_ebitda) if latest.ev_ebitda is not None else None,
            price_to_book=float(latest.price_to_book) if latest.price_to_book is not None else None,
            roe=float(latest.roe) if latest.roe is not None else None,
        )

    return Financials(
        canonical_id=canonical_id,
        currency=latest.currency or "USD",
        income=income,
        balance_sheet=balance,
        cash_flow=cash_flow,
        metrics=metrics,
    )
