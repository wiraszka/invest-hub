from __future__ import annotations

from adapters.base import IMarketDataAdapter
from adapters.finnhub import FinnhubAdapter
from adapters.fmp import FMPAdapter
from adapters.yfinance_adapter import YFinanceAdapter
from core.config import settings


class ProviderRegistry:
    """
    Maps (capability, exchange) to an ordered list of adapters.
    Priority order is driven by settings so it can be changed without a code deploy.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, IMarketDataAdapter] = {
            "fmp": FMPAdapter(),
            "finnhub": FinnhubAdapter(),
            "yfinance": YFinanceAdapter(),
        }

    def for_capability(self, capability: str) -> list[IMarketDataAdapter]:
        """Return adapters that support the given capability, in configured priority order."""
        priority = {
            "quote": settings.quote_providers,
            "financials": settings.financials_providers,
            "profile": settings.profile_providers,
        }.get(capability, [])

        ordered = []
        for name in priority:
            adapter = self._adapters.get(name)
            if adapter and capability in adapter.capabilities:
                ordered.append(adapter)
        return ordered

    def get(self, name: str) -> IMarketDataAdapter | None:
        return self._adapters.get(name)


# Module-level singleton — instantiated once at startup via DI wiring in api/index.py
registry = ProviderRegistry()
