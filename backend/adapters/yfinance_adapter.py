from __future__ import annotations

import asyncio
import logging
import math
from functools import partial

import yfinance as yf

from adapters.base import IMarketDataAdapter
from core.circuit_breaker import CircuitBreaker
from core.config import settings
from core.exceptions import CircuitOpenError
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


logger = logging.getLogger(__name__)


class YFinanceAdapter(IMarketDataAdapter):
    name = "yfinance"
    supported_exchanges = ["NYSE", "NASDAQ", "TSX", "TSXV", "OTC"]
    capabilities = ["quote", "financials", "profile"]

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(settings.yfinance_concurrency)
        self._circuit = CircuitBreaker(
            provider=self.name,
            failure_threshold=settings.circuit_failure_threshold,
            cooldown_seconds=settings.circuit_cooldown_seconds,
        )

    async def _fetch_ticker(self, ticker: str) -> yf.Ticker:
        """Run yfinance's synchronous Ticker fetch in a thread pool to avoid blocking the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(yf.Ticker, ticker))

    async def get_quote(self, ticker: str) -> ProviderResponse[Quote]:
        try:
            self._circuit.check()
        except CircuitOpenError as exc:
            return self.error_response(str(exc))

        async with self._semaphore:
            try:
                ticker_obj = await self._fetch_ticker(ticker)
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, lambda: ticker_obj.info)

                price = info.get("currentPrice") or info.get("regularMarketPrice")
                if not price:
                    self._circuit.record_failure()
                    return self.error_response(f"No quote data for {ticker}")

                quote = Quote(
                    symbol=ticker,
                    price=float(price),
                    currency=info.get("currency", "USD"),
                    source=self.name,
                    fetched_at=self.now(),
                )
                self._circuit.record_success()
                return ProviderResponse(data=quote, raw=info, provider=self.name, fetched_at=self.now())
            except Exception as exc:
                self._circuit.record_failure()
                return self.error_response(str(exc))

    async def get_financials(self, ticker: str) -> ProviderResponse[Financials]:
        try:
            self._circuit.check()
        except CircuitOpenError as exc:
            return self.error_response(str(exc))

        async with self._semaphore:
            try:
                ticker_obj = await self._fetch_ticker(ticker)
                loop = asyncio.get_event_loop()

                info, income_stmt, balance_stmt, cashflow_stmt = await asyncio.gather(
                    loop.run_in_executor(None, lambda: ticker_obj.info),
                    loop.run_in_executor(None, lambda: ticker_obj.financials),
                    loop.run_in_executor(None, lambda: ticker_obj.balance_sheet),
                    loop.run_in_executor(None, lambda: ticker_obj.cashflow),
                )

                currency = info.get("financialCurrency", "USD")

                income: list[IncomeStatement] = []
                if income_stmt is not None and not income_stmt.empty:
                    for col in income_stmt.columns:
                        year = col.year if hasattr(col, "year") else str(col)[:4]
                        income.append(IncomeStatement(
                            period=f"FY{year}",
                            fiscal_year=int(year),
                            revenue=_safe_float(income_stmt, "Total Revenue", col),
                            gross_profit=_safe_float(income_stmt, "Gross Profit", col),
                            operating_income=_safe_float(income_stmt, "Operating Income", col),
                            net_income=_safe_float(income_stmt, "Net Income", col),
                            ebitda=_safe_float(income_stmt, "EBITDA", col),
                        ))

                balance: BalanceSheet | None = None
                if balance_stmt is not None and not balance_stmt.empty:
                    col = balance_stmt.columns[0]
                    year = col.year if hasattr(col, "year") else str(col)[:4]
                    balance = BalanceSheet(
                        period=f"FY{year}",
                        cash=_safe_float(balance_stmt, "Cash And Cash Equivalents", col),
                        total_debt=_safe_float(balance_stmt, "Total Debt", col),
                        total_equity=_safe_float(balance_stmt, "Stockholders Equity", col),
                        total_assets=_safe_float(balance_stmt, "Total Assets", col),
                    )
                    if balance.total_debt is not None and balance.cash is not None:
                        balance.net_debt = balance.total_debt - balance.cash

                cash_flow: list[CashFlow] = []
                if cashflow_stmt is not None and not cashflow_stmt.empty:
                    for col in cashflow_stmt.columns:
                        year = col.year if hasattr(col, "year") else str(col)[:4]
                        ocf = _safe_float(cashflow_stmt, "Operating Cash Flow", col)
                        capex = _safe_float(cashflow_stmt, "Capital Expenditure", col)
                        fcf = (ocf + capex) if (ocf is not None and capex is not None) else None
                        cash_flow.append(CashFlow(
                            period=f"FY{year}",
                            operating_cash_flow=ocf,
                            capex=capex,
                            free_cash_flow=fcf,
                        ))

                metrics: KeyMetrics | None = None
                if info:
                    metrics = KeyMetrics(
                        period="latest",
                        market_cap=info.get("marketCap"),
                        enterprise_value=info.get("enterpriseValue"),
                        pe_ratio=info.get("trailingPE"),
                        ev_ebitda=info.get("enterpriseToEbitda"),
                        price_to_book=info.get("priceToBook"),
                        roe=info.get("returnOnEquity"),
                    )

                raw_combined = {"info": info}
                financials = Financials(
                    currency=currency,
                    income=income,
                    balance_sheet=balance,
                    cash_flow=cash_flow,
                    metrics=metrics,
                )
                self._circuit.record_success()
                return ProviderResponse(data=financials, raw=raw_combined, provider=self.name, fetched_at=self.now())
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
                ticker_obj = await self._fetch_ticker(ticker)
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, lambda: ticker_obj.info)

                name = info.get("longName") or info.get("shortName")
                if not name:
                    self._circuit.record_failure()
                    return self.error_response(f"No profile for {ticker}")

                identity = CompanyIdentity(
                    isin=info.get("isin"),
                    name=name,
                    exchange=info.get("exchange"),
                    currency=info.get("currency"),
                )
                self._circuit.record_success()
                return ProviderResponse(data=identity, raw=info, provider=self.name, fetched_at=self.now())
            except Exception as exc:
                self._circuit.record_failure()
                return self.error_response(str(exc))


def _safe_float(df, row: str, col) -> float | None:
    try:
        value = df.loc[row, col]
        if value is None:
            return None
        return None if math.isnan(float(value)) else float(value)
    except (KeyError, TypeError, ValueError):
        return None
