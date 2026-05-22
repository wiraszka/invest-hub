from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import services.sec as sec_service
from adapters.base import IMarketDataAdapter
from core.config import settings
from models.market_data import (
    BalanceSheet,
    CashFlow,
    CompanyIdentity,
    Financials,
    IncomeStatement,
    ProviderResponse,
    Quote,
)

logger = logging.getLogger(__name__)


class SECAdapter(IMarketDataAdapter):
    name = "sec"
    supported_exchanges = ["NYSE", "NASDAQ"]
    capabilities = ["financials", "profile"]

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(settings.sec_concurrency)

    async def get_quote(self, ticker: str) -> ProviderResponse[Quote]:
        return self.error_response("SEC does not provide quote data")

    async def get_financials(self, ticker: str) -> ProviderResponse[Financials]:
        async with self._semaphore:
            try:
                result = await asyncio.to_thread(_fetch_financials_sync, ticker)
                return ProviderResponse(
                    data=result, raw={}, provider=self.name, fetched_at=datetime.now(timezone.utc)
                )
            except Exception as exc:
                logger.exception("sec get_financials error", extra={"ticker": ticker})
                return self.error_response(str(exc))

    async def get_profile(self, ticker: str) -> ProviderResponse[CompanyIdentity]:
        async with self._semaphore:
            try:
                result = await asyncio.to_thread(_fetch_profile_sync, ticker)
                return ProviderResponse(
                    data=result, raw={}, provider=self.name, fetched_at=datetime.now(timezone.utc)
                )
            except Exception as exc:
                logger.exception("sec get_profile error", extra={"ticker": ticker})
                return self.error_response(str(exc))


def _fetch_financials_sync(ticker: str) -> Financials:
    cik = sec_service.resolve_cik(ticker)
    submissions = sec_service.get_submissions(cik)
    _, _, form_type, _ = sec_service.find_recent_annual(submissions)
    facts, currency = sec_service.get_xbrl_facts(cik, form_type)

    income = IncomeStatement(
        period="annual",
        revenue=facts.get("revenue"),
        net_income=facts.get("net_income"),
    )
    balance = BalanceSheet(
        period="annual",
        cash=facts.get("cash"),
        total_debt=facts.get("total_debt"),
        net_debt=facts.get("net_debt"),
    )
    cash_flow = CashFlow(
        period="annual",
        operating_cash_flow=facts.get("operating_cash_flow"),
    )
    return Financials(
        currency=currency,
        income=[income],
        balance_sheet=balance,
        cash_flow=[cash_flow],
    )


def _fetch_profile_sync(ticker: str) -> CompanyIdentity:
    cik = sec_service.resolve_cik(ticker)
    submissions = sec_service.get_submissions(cik)
    name = submissions.get("name") or ticker
    exchanges = submissions.get("exchanges") or []
    exchange = exchanges[0] if exchanges else None
    return CompanyIdentity(name=name, exchange=exchange)
