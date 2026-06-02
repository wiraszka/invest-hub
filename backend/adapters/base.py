from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from models.market_data import (
    CompanyIdentity,
    Financials,
    LeadershipData,
    MarketIntelligence,
    PriceHistory,
    ProviderResponse,
    Quote,
)


class IMarketDataAdapter(ABC):
    name: str
    supported_exchanges: list[str]
    capabilities: list[
        str
    ]  # subset of: "quote", "financials", "profile", "price_history", "leadership", "market_intelligence"

    @abstractmethod
    async def get_quote(self, ticker: str) -> ProviderResponse[Quote]: ...

    @abstractmethod
    async def get_financials(self, ticker: str) -> ProviderResponse[Financials]: ...

    @abstractmethod
    async def get_profile(self, ticker: str) -> ProviderResponse[CompanyIdentity]: ...

    async def get_price_history(
        self, ticker: str, days: int = 365, interval: str = "1day"
    ) -> ProviderResponse[PriceHistory]:
        return self.error_response("price_history not supported by this adapter")

    async def get_leadership(self, ticker: str) -> ProviderResponse[LeadershipData]:
        return self.error_response("leadership not supported by this adapter")

    async def get_market_intelligence(
        self, ticker: str
    ) -> ProviderResponse[MarketIntelligence]:
        return self.error_response("market_intelligence not supported by this adapter")

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
