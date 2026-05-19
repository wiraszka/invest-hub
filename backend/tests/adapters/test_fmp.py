from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.fmp import FMPAdapter
from models.market_data import Financials, Quote


@pytest.fixture
def adapter() -> FMPAdapter:
    return FMPAdapter()


class TestGetQuote:
    async def test_returns_quote_on_success(self, adapter: FMPAdapter) -> None:
        raw_payload = [{"price": 42.5, "currency": "USD", "symbol": "AAPL"}]

        with patch.object(adapter, "_get", new=AsyncMock(return_value=raw_payload)):
            with patch("adapters.fmp.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_quote("AAPL")

        assert response.data is not None
        assert isinstance(response.data, Quote)
        assert response.data.price == 42.5
        assert response.data.symbol == "AAPL"
        assert response.provider == "fmp"
        assert response.error is None

    async def test_returns_error_on_empty_response(self, adapter: FMPAdapter) -> None:
        with patch.object(adapter, "_get", new=AsyncMock(return_value=None)):
            with patch("adapters.fmp.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_quote("UNKNOWN")

        assert response.data is None
        assert response.error is not None

    async def test_circuit_opens_after_threshold_failures(self, adapter: FMPAdapter) -> None:
        with patch.object(adapter, "_get", new=AsyncMock(return_value=None)):
            with patch("adapters.fmp.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                for _ in range(adapter._circuit.failure_threshold):
                    await adapter.get_quote("FAIL")

        assert adapter._circuit.is_open


class TestGetFinancials:
    async def test_returns_financials_on_success(self, adapter: FMPAdapter) -> None:
        income_payload = [{
            "calendarYear": "2024",
            "reportedCurrency": "USD",
            "revenue": 100_000_000,
            "grossProfit": 60_000_000,
            "operatingIncome": 30_000_000,
            "netIncome": 20_000_000,
            "ebitda": 35_000_000,
        }]
        balance_payload = [{
            "calendarYear": "2024",
            "cashAndCashEquivalents": 5_000_000,
            "totalDebt": 10_000_000,
            "netDebt": 5_000_000,
            "totalStockholdersEquity": 50_000_000,
            "totalAssets": 80_000_000,
        }]

        async def mock_get(client, path: str):
            if "income-statement" in path:
                return income_payload
            if "balance-sheet" in path:
                return balance_payload
            return []

        with patch.object(adapter, "_get", new=mock_get):
            with patch("adapters.fmp.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_financials("AAPL")

        assert response.data is not None
        assert isinstance(response.data, Financials)
        assert response.data.currency == "USD"
        assert len(response.data.income) == 1
        assert response.data.income[0].revenue == 100_000_000
        assert response.data.income[0].period == "FY2024"
