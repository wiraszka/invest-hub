from __future__ import annotations

import logging

from core.cache import cache
from services.provider_registry import registry

logger = logging.getLogger(__name__)

_DAILY_INTERVALS = {"1day", "1week", "1month"}
_HOURLY_TTL = 3600  # 1 h  — intraday data changes through the trading day
_DAILY_TTL = 86400  # 24 h — past daily closes never change


async def get_current_price(ticker: str) -> dict:
    """Return current price. Falls back through the quote provider chain."""
    for adapter in registry.for_capability("quote"):
        response = await adapter.get_quote(ticker)
        if response.data is not None:
            return {
                "ticker": ticker,
                "price": response.data.price,
                "currency": response.data.currency,
            }
        logger.warning("quote miss", extra={"ticker": ticker, "provider": adapter.name})

    raise ValueError(f"Could not retrieve price for {ticker} from any source")


async def get_price_history(
    ticker: str, days: int = 365, interval: str = "1day"
) -> dict:
    """Return closing prices. Falls back through the price_history provider chain."""
    cache_key = ("price_history", ticker, days, interval)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    adapters = registry.for_capability("price_history")
    for adapter in adapters:
        response = await adapter.get_price_history(ticker, days, interval)
        if response.data is None:
            logger.warning(
                "price_history miss",
                extra={
                    "ticker": ticker,
                    "provider": adapter.name,
                    "interval": interval,
                },
            )
            continue

        result = {
            "ticker": response.data.ticker,
            "interval": interval,
            "history": [
                {"date": p.date, "close": p.close} for p in response.data.history
            ],
        }
        ttl = _DAILY_TTL if interval in _DAILY_INTERVALS else _HOURLY_TTL
        cache.set(cache_key, result, ttl)
        return result

    raise ValueError(f"No price history for {ticker} from any provider")
