from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from adapters.finnhub import FinnhubAdapter, _clean_peers
from models.market_data import CompanyIdentity, Quote


@pytest.fixture
def adapter() -> FinnhubAdapter:
    return FinnhubAdapter()


class TestGetQuote:
    async def test_returns_quote_on_success(self, adapter: FinnhubAdapter) -> None:
        raw_payload = {"c": 185.5, "h": 187.0, "l": 184.0, "o": 185.0, "pc": 184.5}

        with patch.object(adapter, "_get", new=AsyncMock(return_value=raw_payload)):
            with patch("adapters.finnhub.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_quote("AAPL")

        assert response.data is not None
        assert isinstance(response.data, Quote)
        assert response.data.price == 185.5
        assert response.provider == "finnhub"
        assert response.error is None

    async def test_returns_error_when_price_is_zero(
        self, adapter: FinnhubAdapter
    ) -> None:
        raw_payload = {"c": 0, "h": 0, "l": 0}

        with patch.object(adapter, "_get", new=AsyncMock(return_value=raw_payload)):
            with patch("adapters.finnhub.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_quote("UNKNOWN")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_on_none_response(
        self, adapter: FinnhubAdapter
    ) -> None:
        with patch.object(adapter, "_get", new=AsyncMock(return_value=None)):
            with patch("adapters.finnhub.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_quote("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_on_exception(self, adapter: FinnhubAdapter) -> None:
        with patch.object(
            adapter, "_get", new=AsyncMock(side_effect=RuntimeError("timeout"))
        ):
            with patch("adapters.finnhub.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_quote("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_when_circuit_is_open(
        self, adapter: FinnhubAdapter
    ) -> None:
        import time

        adapter._circuit._failures = adapter._circuit.failure_threshold
        adapter._circuit._opened_at = time.monotonic()

        response = await adapter.get_quote("AAPL")

        assert response.data is None
        assert response.error is not None


class TestGetFinancials:
    async def test_always_returns_error(self, adapter: FinnhubAdapter) -> None:
        response = await adapter.get_financials("AAPL")

        assert response.data is None
        assert "free tier" in (response.error or "").lower()


class TestGetProfile:
    async def test_returns_profile_on_success(self, adapter: FinnhubAdapter) -> None:
        raw_payload = {
            "name": "Apple Inc.",
            "ticker": "AAPL",
            "exchange": "NASDAQ",
            "currency": "USD",
            "isin": "US0378331005",
            "finnhubIndustry": "Technology",
            "country": "US",
            "type": "EQ",
        }

        with patch.object(adapter, "_get", new=AsyncMock(return_value=raw_payload)):
            with patch("adapters.finnhub.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_profile("AAPL")

        assert response.data is not None
        assert isinstance(response.data, CompanyIdentity)
        assert response.data.name == "Apple Inc."
        assert response.data.industry == "Technology"
        assert response.data.country == "US"
        assert response.data.security_type == "eq"
        assert response.error is None

    async def test_normalizes_security_type_to_lowercase(
        self, adapter: FinnhubAdapter
    ) -> None:
        raw_payload = {
            "name": "SPDR S&P 500 ETF",
            "exchange": "NYSE",
            "currency": "USD",
            "type": "ETF",
        }

        with patch.object(adapter, "_get", new=AsyncMock(return_value=raw_payload)):
            with patch("adapters.finnhub.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_profile("SPY")

        assert response.data is not None
        assert response.data.security_type == "etf"

    async def test_returns_error_on_missing_name(self, adapter: FinnhubAdapter) -> None:
        raw_payload = {"ticker": "AAPL", "exchange": "NASDAQ"}

        with patch.object(adapter, "_get", new=AsyncMock(return_value=raw_payload)):
            with patch("adapters.finnhub.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_profile("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_on_none_response(
        self, adapter: FinnhubAdapter
    ) -> None:
        with patch.object(adapter, "_get", new=AsyncMock(return_value=None)):
            with patch("adapters.finnhub.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_profile("AAPL")

        assert response.data is None
        assert response.error is not None


class TestCleanPeers:
    def test_removes_exact_self_ticker(self) -> None:
        result = _clean_peers("MU", ["NVDA", "MU", "AMD", "INTC"])

        assert "MU" not in result
        assert result == ["NVDA", "AMD", "INTC"]

    def test_removes_cross_listed_self_ticker(self) -> None:
        result = _clean_peers("AEM", ["ABX.TO", "AEM.TO", "FNV.TO"])

        assert "AEM.TO" not in result
        assert result == ["ABX.TO", "FNV.TO"]

    def test_deduplicates(self) -> None:
        result = _clean_peers("MU", ["NVDA", "AMD", "NVDA", "INTC"])

        assert result.count("NVDA") == 1

    def test_caps_at_eight(self) -> None:
        raw = [f"T{i}" for i in range(20)]

        result = _clean_peers("OTHER", raw)

        assert len(result) == 8

    def test_returns_empty_for_empty_input(self) -> None:
        result = _clean_peers("MU", [])

        assert result == []

    def test_case_insensitive_self_removal(self) -> None:
        result = _clean_peers("mu", ["NVDA", "MU", "AMD"])

        assert "MU" not in result


class TestGetPeers:
    async def test_returns_cleaned_peer_list(self, adapter: FinnhubAdapter) -> None:
        raw_payload = ["NVDA", "AVGO", "MU", "AMD", "INTC"]

        with patch.object(adapter, "_get", new=AsyncMock(return_value=raw_payload)):
            with patch("adapters.finnhub.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await adapter.get_peers("MU")

        assert "MU" not in result
        assert "NVDA" in result
        assert isinstance(result, list)

    async def test_returns_empty_list_on_none_response(
        self, adapter: FinnhubAdapter
    ) -> None:
        with patch.object(adapter, "_get", new=AsyncMock(return_value=None)):
            with patch("adapters.finnhub.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await adapter.get_peers("MU")

        assert result == []

    async def test_returns_empty_list_on_exception(
        self, adapter: FinnhubAdapter
    ) -> None:
        with patch.object(
            adapter, "_get", new=AsyncMock(side_effect=RuntimeError("network error"))
        ):
            with patch("adapters.finnhub.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await adapter.get_peers("MU")

        assert result == []

    async def test_returns_empty_list_on_non_list_response(
        self, adapter: FinnhubAdapter
    ) -> None:
        with patch.object(
            adapter, "_get", new=AsyncMock(return_value={"error": "not found"})
        ):
            with patch("adapters.finnhub.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await adapter.get_peers("MU")

        assert result == []
