from __future__ import annotations

import asyncio
import logging

import httpx

from adapters.base import IMarketDataAdapter
from core.circuit_breaker import CircuitBreaker
from core.config import settings
from core.exceptions import CircuitOpenError, NormalizationError
from models.market_data import (
    BalanceSheet,
    CashFlow,
    CompanyIdentity,
    Financials,
    IncomeStatement,
    KeyMetrics,
    ProviderResponse,
    Quote,
)

_BASE = "https://financialmodelingprep.com/stable"
logger = logging.getLogger(__name__)


class FMPAdapter(IMarketDataAdapter):
    name = "fmp"
    supported_exchanges = ["NYSE", "NASDAQ", "TSX", "TSXV", "OTC"]
    capabilities = ["quote", "financials", "profile"]

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(settings.fmp_concurrency)
        self._circuit = CircuitBreaker(
            provider=self.name,
            failure_threshold=settings.circuit_failure_threshold,
            cooldown_seconds=settings.circuit_cooldown_seconds,
        )

    async def _get(self, client: httpx.AsyncClient, path: str, **params) -> list | dict | None:
        try:
            response = await client.get(
                f"{_BASE}{path}",
                params={"apikey": settings.fmp_api_key, **params},
                timeout=10,
            )
            if not response.is_success:
                return None
            data = response.json()
            return data if data else None
        except Exception:
            return None

    async def get_quote(self, ticker: str) -> ProviderResponse[Quote]:
        try:
            self._circuit.check()
        except CircuitOpenError as exc:
            return self.error_response(str(exc))

        async with self._semaphore:
            try:
                async with httpx.AsyncClient() as client:
                    raw = await self._get(client, "/quote", symbol=ticker)
                    if not raw or not isinstance(raw, list) or not raw[0].get("price"):
                        self._circuit.record_failure()
                        logger.warning("fmp quote empty", extra={"ticker": ticker})
                        return self.error_response(f"No quote data for {ticker}")

                    entry = raw[0]
                    quote = Quote(
                        symbol=ticker,
                        price=float(entry["price"]),
                        currency="USD",
                        source=self.name,
                        fetched_at=self.now(),
                    )
                    self._circuit.record_success()
                    return ProviderResponse(data=quote, raw=entry, provider=self.name, fetched_at=self.now())
            except Exception as exc:
                self._circuit.record_failure()
                logger.exception("fmp get_quote error", extra={"ticker": ticker})
                return self.error_response(str(exc))

    async def get_financials(self, ticker: str) -> ProviderResponse[Financials]:
        try:
            self._circuit.check()
        except CircuitOpenError as exc:
            return self.error_response(str(exc))

        async with self._semaphore:
            try:
                async with httpx.AsyncClient() as client:
                    income_raw, balance_raw, cashflow_raw, metrics_raw = await asyncio.gather(
                        self._get(client, "/income-statement", symbol=ticker, limit=3),
                        self._get(client, "/balance-sheet-statement", symbol=ticker, limit=1),
                        self._get(client, "/cash-flow-statement", symbol=ticker, limit=3),
                        self._get(client, "/key-metrics", symbol=ticker, limit=1),
                    )

                if not income_raw or not isinstance(income_raw, list):
                    self._circuit.record_failure()
                    return self.error_response(f"No financials for {ticker}")

                currency = income_raw[0].get("reportedCurrency", "USD")

                income = [
                    IncomeStatement(
                        period=f"FY{entry.get('fiscalYear') or entry.get('date', '')[:4]}",
                        fiscal_year=int(entry["fiscalYear"]) if entry.get("fiscalYear") else None,
                        revenue=entry.get("revenue"),
                        gross_profit=entry.get("grossProfit"),
                        operating_income=entry.get("operatingIncome"),
                        net_income=entry.get("netIncome"),
                        ebitda=entry.get("ebitda"),
                    )
                    for entry in income_raw
                ]

                balance: BalanceSheet | None = None
                if balance_raw and isinstance(balance_raw, list) and balance_raw:
                    entry = balance_raw[0]
                    period = f"FY{entry.get('fiscalYear') or entry.get('date', '')[:4]}"
                    balance = BalanceSheet(
                        period=period,
                        cash=entry.get("cashAndCashEquivalents"),
                        total_debt=entry.get("totalDebt"),
                        net_debt=entry.get("netDebt"),
                        total_equity=entry.get("totalStockholdersEquity"),
                        total_assets=entry.get("totalAssets"),
                    )

                cash_flow = []
                if cashflow_raw and isinstance(cashflow_raw, list):
                    cash_flow = [
                        CashFlow(
                            period=f"FY{entry.get('fiscalYear') or entry.get('date', '')[:4]}",
                            operating_cash_flow=entry.get("operatingCashFlow"),
                            capex=entry.get("capitalExpenditure"),
                            free_cash_flow=entry.get("freeCashFlow"),
                        )
                        for entry in cashflow_raw
                    ]

                metrics: KeyMetrics | None = None
                if metrics_raw and isinstance(metrics_raw, list) and metrics_raw:
                    entry = metrics_raw[0]
                    period = f"FY{entry.get('fiscalYear') or entry.get('date', '')[:4]}"
                    metrics = KeyMetrics(
                        period=period,
                        market_cap=entry.get("marketCap"),
                        enterprise_value=entry.get("enterpriseValue"),
                        ev_ebitda=entry.get("evToEBITDA"),
                        roe=entry.get("returnOnEquity"),
                    )

                raw_combined = {
                    "income": income_raw,
                    "balance_sheet": balance_raw,
                    "cash_flow": cashflow_raw,
                    "metrics": metrics_raw,
                }
                financials = Financials(
                    currency=currency,
                    income=income,
                    balance_sheet=balance,
                    cash_flow=cash_flow,
                    metrics=metrics,
                )
                self._circuit.record_success()
                return ProviderResponse(data=financials, raw=raw_combined, provider=self.name, fetched_at=self.now())
            except NormalizationError as exc:
                self._circuit.record_failure()
                return self.error_response(str(exc))
            except Exception as exc:
                self._circuit.record_failure()
                return self.error_response(str(exc))

    async def get_profile(self, ticker: str) -> ProviderResponse[CompanyIdentity]:
        try:
            self._circuit.check()
        except CircuitOpenError as exc:
            return self.error_response(str(exc))

        async with self._semaphore:
            try:
                async with httpx.AsyncClient() as client:
                    raw = await self._get(client, "/profile", symbol=ticker)
                    if not raw or not isinstance(raw, list) or not raw[0].get("companyName"):
                        self._circuit.record_failure()
                        return self.error_response(f"No profile for {ticker}")

                    entry = raw[0]
                    identity = CompanyIdentity(
                        isin=entry.get("isin"),
                        name=entry["companyName"],
                        exchange=entry.get("exchange"),
                        currency=entry.get("currency"),
                    )
                    self._circuit.record_success()
                    return ProviderResponse(data=identity, raw=entry, provider=self.name, fetched_at=self.now())
            except Exception as exc:
                self._circuit.record_failure()
                return self.error_response(str(exc))
