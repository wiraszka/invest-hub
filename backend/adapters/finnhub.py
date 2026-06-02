from __future__ import annotations

import asyncio
import logging

import httpx

from adapters.base import IMarketDataAdapter
from core.circuit_breaker import CircuitBreaker
from core.config import settings
from core.exceptions import CircuitOpenError
from models.market_data import CompanyIdentity, Financials, ProviderResponse, Quote

_BASE = "https://finnhub.io/api/v1"
_MAX_PEERS = 8
logger = logging.getLogger(__name__)


def _clean_peers(ticker: str, raw: list) -> list[str]:
    """Remove the queried ticker (including cross-listed variants), deduplicate, cap at _MAX_PEERS.

    Finnhub includes the subject ticker itself in the list (e.g. querying "MU"
    returns "MU"; querying "AEM" returns "AEM.TO"). Strip any entry whose base
    ticker (before the first ".") matches the queried ticker's base, case-insensitively.
    """
    queried_base = ticker.upper().split(".")[0]
    seen: set[str] = set()
    result: list[str] = []
    for t in raw:
        t_str = str(t).strip()
        if not t_str:
            continue
        base = t_str.upper().split(".")[0]
        if base == queried_base or t_str in seen:
            continue
        seen.add(t_str)
        result.append(t_str)
        if len(result) >= _MAX_PEERS:
            break
    return result


class FinnhubAdapter(IMarketDataAdapter):
    name = "finnhub"
    supported_exchanges = ["NYSE", "NASDAQ", "TSX"]
    capabilities = ["quote", "profile"]  # Finnhub free tier has no financials endpoint

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(settings.finnhub_concurrency)
        self._circuit = CircuitBreaker(
            provider=self.name,
            failure_threshold=settings.circuit_failure_threshold,
            cooldown_seconds=settings.circuit_cooldown_seconds,
        )

    async def _get(
        self, client: httpx.AsyncClient, path: str, params: dict | None = None
    ) -> dict | None:
        try:
            response = await client.get(
                f"{_BASE}{path}",
                params={"token": settings.finnhub_api_key, **(params or {})},
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
                    raw = await self._get(client, "/quote", {"symbol": ticker})
                    # Finnhub returns {"c": current, "h": high, "l": low, ...}; c=0 means no data
                    if not raw or not raw.get("c"):
                        self._circuit.record_failure()
                        logger.warning("finnhub quote empty", extra={"ticker": ticker})
                        return self.error_response(f"No quote data for {ticker}")

                    quote = Quote(
                        symbol=ticker,
                        price=float(raw["c"]),
                        currency="USD",  # Finnhub free tier doesn't return currency
                        source=self.name,
                        fetched_at=self.now(),
                    )
                    self._circuit.record_success()
                    return ProviderResponse(
                        data=quote, raw=raw, provider=self.name, fetched_at=self.now()
                    )
            except Exception as exc:
                self._circuit.record_failure()
                return self.error_response(str(exc))

    async def get_financials(self, ticker: str) -> ProviderResponse[Financials]:
        # Not supported on Finnhub free tier
        return self.error_response("Financials not available on Finnhub free tier")

    async def get_peers(self, ticker: str) -> list[str]:
        """Return cleaned list of sector peer tickers from Finnhub /stock/peers.

        Always returns a list (empty on any failure). Never raises.
        """
        try:
            async with httpx.AsyncClient() as client:
                raw = await self._get(client, "/stock/peers", {"symbol": ticker})
                if not raw or not isinstance(raw, list):
                    return []
                return _clean_peers(ticker, raw)
        except Exception:
            return []

    async def get_profile(self, ticker: str) -> ProviderResponse[CompanyIdentity]:
        try:
            self._circuit.check()
        except CircuitOpenError as exc:
            return self.error_response(str(exc))

        async with self._semaphore:
            try:
                async with httpx.AsyncClient() as client:
                    raw = await self._get(client, "/stock/profile2", {"symbol": ticker})
                    if not raw or not raw.get("name"):
                        self._circuit.record_failure()
                        return self.error_response(f"No profile for {ticker}")

                    raw_type = raw.get("type", "")
                    identity = CompanyIdentity(
                        isin=raw.get("isin"),
                        name=raw["name"],
                        exchange=raw.get("exchange"),
                        currency=raw.get("currency"),
                        industry=raw.get("finnhubIndustry"),
                        country=raw.get("country"),
                        security_type=raw_type.lower() if raw_type else None,
                    )
                    self._circuit.record_success()
                    return ProviderResponse(
                        data=identity,
                        raw=raw,
                        provider=self.name,
                        fetched_at=self.now(),
                    )
            except Exception as exc:
                self._circuit.record_failure()
                return self.error_response(str(exc))
