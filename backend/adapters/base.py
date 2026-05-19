from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from models.market_data import CompanyIdentity, Financials, ProviderResponse, Quote


class IMarketDataAdapter(ABC):
    name: str
    supported_exchanges: list[str]
    capabilities: list[str]  # subset of: "quote", "financials", "profile"

    @abstractmethod
    async def get_quote(self, ticker: str) -> ProviderResponse[Quote]:
        ...

    @abstractmethod
    async def get_financials(self, ticker: str) -> ProviderResponse[Financials]:
        ...

    @abstractmethod
    async def get_profile(self, ticker: str) -> ProviderResponse[CompanyIdentity]:
        ...

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

    def error_response(self, error: str) -> ProviderResponse:
        return ProviderResponse(
            data=None,
            raw={},
            provider=self.name,
            fetched_at=self.now(),
            error=error,
        )
