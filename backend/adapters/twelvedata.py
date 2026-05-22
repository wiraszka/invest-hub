from __future__ import annotations

import asyncio
import logging

import httpx

from adapters.base import IMarketDataAdapter
from core.circuit_breaker import CircuitBreaker
from core.config import settings
from core.exceptions import CircuitOpenError
from models.market_data import (
    CompanyIdentity,
    Financials,
    PriceHistory,
    PricePoint,
    ProviderResponse,
    Quote,
)

_BASE = "https://api.twelvedata.com"
logger = logging.getLogger(__name__)


def _normalize_ticker(ticker: str) -> str:
    if ticker.endswith(".TO"):
        return ticker[:-3] + ":TSX"
    if ticker.endswith(".V"):
        return ticker[:-2] + ":TSXV"
    return ticker


class TwelveDataAdapter(IMarketDataAdapter):
    name = "twelvedata"
    supported_exchanges = ["NYSE", "NASDAQ", "TSX", "TSXV", "OTC", "CRYPTO"]
    capabilities = ["quote", "price_history"]

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(settings.twelvedata_concurrency)
        self._circuit = CircuitBreaker(
            provider=self.name,
            failure_threshold=settings.circuit_failure_threshold,
            cooldown_seconds=settings.circuit_cooldown_seconds,
        )

    async def get_quote(self, ticker: str) -> ProviderResponse[Quote]:
        try:
            self._circuit.check()
        except CircuitOpenError as exc:
            return self.error_response(str(exc))

        async with self._semaphore:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(
                        f"{_BASE}/price",
                        params={"symbol": _normalize_ticker(ticker), "apikey": settings.td_api_key},
                    )
                    if not response.is_success:
                        self._circuit.record_failure()
                        return self.error_response(f"TwelveData returned {response.status_code}")
                    raw = response.json()
                    if "price" not in raw:
                        self._circuit.record_failure()
                        logger.warning("twelvedata quote empty", extra={"ticker": ticker})
                        return self.error_response(raw.get("message", f"No price for {ticker}"))
                    quote = Quote(
                        symbol=ticker,
                        price=float(raw["price"]),
                        currency="USD",
                        source=self.name,
                        fetched_at=self.now(),
                    )
                    self._circuit.record_success()
                    return ProviderResponse(data=quote, raw=raw, provider=self.name, fetched_at=self.now())
            except Exception as exc:
                self._circuit.record_failure()
                logger.exception("twelvedata get_quote error", extra={"ticker": ticker})
                return self.error_response(str(exc))

    async def get_price_history(self, ticker: str, days: int = 365, interval: str = "1day") -> ProviderResponse[PriceHistory]:
        try:
            self._circuit.check()
        except CircuitOpenError as exc:
            return self.error_response(str(exc))

        async with self._semaphore:
            try:
                from datetime import date, timedelta
                start_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
                end_date = date.today().strftime("%Y-%m-%d")
                async with httpx.AsyncClient(timeout=15) as client:
                    response = await client.get(
                        f"{_BASE}/time_series",
                        params={
                            "symbol": _normalize_ticker(ticker),
                            "interval": interval,
                            "start_date": start_date,
                            "end_date": end_date,
                            "apikey": settings.td_api_key,
                        },
                    )
                    response.raise_for_status()
                    raw = response.json()
                    if "values" not in raw:
                        self._circuit.record_failure()
                        return self.error_response(raw.get("message", "Unexpected response from TwelveData"))
                    history = PriceHistory(
                        ticker=ticker,
                        history=[
                            PricePoint(date=entry["datetime"], close=float(entry["close"]))
                            for entry in reversed(raw["values"])
                        ],
                    )
                    self._circuit.record_success()
                    return ProviderResponse(data=history, raw=raw, provider=self.name, fetched_at=self.now())
            except Exception as exc:
                self._circuit.record_failure()
                logger.exception("twelvedata get_price_history error", extra={"ticker": ticker})
                return self.error_response(str(exc))

    async def get_financials(self, ticker: str) -> ProviderResponse[Financials]:
        return self.error_response("TwelveData does not provide financials")

    async def get_profile(self, ticker: str) -> ProviderResponse[CompanyIdentity]:
        return self.error_response("TwelveData does not provide profile")
