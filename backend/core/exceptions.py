from __future__ import annotations


class MarketDataError(Exception):
    pass


class ProviderUnavailableError(MarketDataError):
    def __init__(self, symbol: str, providers: list[str]) -> None:
        self.symbol = symbol
        self.providers = providers
        super().__init__(f"All providers exhausted for {symbol}: {providers}")


class CircuitOpenError(MarketDataError):
    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Circuit breaker open for provider: {provider}")


class IdentityResolutionError(MarketDataError):
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        super().__init__(f"Could not resolve identity for: {symbol}")


class NormalizationError(MarketDataError):
    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"Normalization failed for {provider}: {message}")
