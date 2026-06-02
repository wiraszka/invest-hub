from __future__ import annotations

import pytest

from services.provider_registry import ProviderRegistry


@pytest.fixture
def registry() -> ProviderRegistry:
    return ProviderRegistry()


class TestProviderRegistry:
    def test_returns_adapters_for_quote_capability(
        self, registry: ProviderRegistry
    ) -> None:
        adapters = registry.for_capability("quote")

        assert len(adapters) > 0
        assert all("quote" in adapter.capabilities for adapter in adapters)

    def test_returns_adapters_for_financials_capability(
        self, registry: ProviderRegistry
    ) -> None:
        adapters = registry.for_capability("financials")

        assert len(adapters) > 0
        assert all("financials" in adapter.capabilities for adapter in adapters)

    def test_excludes_adapters_without_capability(
        self, registry: ProviderRegistry
    ) -> None:
        financials_adapters = registry.for_capability("financials")
        names = [a.name for a in financials_adapters]

        # Finnhub free tier does not support financials
        assert "finnhub" not in names

    def test_returns_empty_for_unknown_capability(
        self, registry: ProviderRegistry
    ) -> None:
        adapters = registry.for_capability("nonexistent")

        assert adapters == []

    def test_get_returns_adapter_by_name(self, registry: ProviderRegistry) -> None:
        fmp = registry.get("fmp")

        assert fmp is not None
        assert fmp.name == "fmp"

    def test_get_returns_none_for_unknown_name(
        self, registry: ProviderRegistry
    ) -> None:
        result = registry.get("eodhd")

        assert result is None
