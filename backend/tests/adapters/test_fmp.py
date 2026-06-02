from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from adapters.fmp import FMPAdapter
from models.market_data import CompanyIdentity, Financials, Quote


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

    async def test_returns_error_on_missing_price_field(
        self, adapter: FMPAdapter
    ) -> None:
        raw_payload = [{"symbol": "AAPL", "volume": 12345}]

        with patch.object(adapter, "_get", new=AsyncMock(return_value=raw_payload)):
            with patch("adapters.fmp.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_quote("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_on_exception(self, adapter: FMPAdapter) -> None:
        with patch.object(
            adapter, "_get", new=AsyncMock(side_effect=RuntimeError("network error"))
        ):
            with patch("adapters.fmp.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_quote("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_circuit_opens_after_threshold_failures(
        self, adapter: FMPAdapter
    ) -> None:
        with patch.object(adapter, "_get", new=AsyncMock(return_value=None)):
            with patch("adapters.fmp.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                for _ in range(adapter._circuit.failure_threshold):
                    await adapter.get_quote("FAIL")

        assert adapter._circuit.is_open

    async def test_returns_error_when_circuit_is_open(
        self, adapter: FMPAdapter
    ) -> None:
        import time

        adapter._circuit._failures = adapter._circuit.failure_threshold
        adapter._circuit._opened_at = time.monotonic()

        response = await adapter.get_quote("AAPL")

        assert response.data is None
        assert response.error is not None


class TestGetFinancials:
    async def test_returns_financials_on_success(self, adapter: FMPAdapter) -> None:
        income_payload = [
            {
                "fiscalYear": "2024",
                "reportedCurrency": "USD",
                "revenue": 100_000_000,
                "grossProfit": 60_000_000,
                "operatingIncome": 30_000_000,
                "netIncome": 20_000_000,
                "ebitda": 35_000_000,
            }
        ]
        balance_payload = [
            {
                "fiscalYear": "2024",
                "cashAndCashEquivalents": 5_000_000,
                "totalDebt": 10_000_000,
                "netDebt": 5_000_000,
                "totalStockholdersEquity": 50_000_000,
                "totalAssets": 80_000_000,
            }
        ]
        metrics_payload = [
            {
                "fiscalYear": "2024",
                "marketCap": 3_000_000_000_000,
                "enterpriseValue": 3_050_000_000_000,
                "peRatio": 31.5,
                "evToEBITDA": 25.0,
                "pbRatio": 48.2,
                "pegRatio": 2.8,
                "returnOnEquity": 1.47,
                "returnOnAssets": 0.28,
                "eps": 6.42,
                "dividendYield": 0.005,
                "payoutRatio": 0.15,
                "beta": 1.24,
                "debtToEquity": 1.73,
                "quickRatio": 0.91,
                "currentRatio": 1.04,
            }
        ]

        async def mock_get(client, path: str, **params):
            if "income-statement" in path:
                return income_payload
            if "balance-sheet" in path:
                return balance_payload
            if "key-metrics" in path:
                return metrics_payload
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
        assert response.data.metrics is not None
        assert response.data.metrics.market_cap == pytest.approx(3_000_000_000_000)
        assert response.data.metrics.peg_ratio == pytest.approx(2.8)
        assert response.data.metrics.return_on_assets == pytest.approx(0.28)
        assert response.data.metrics.quick_ratio == pytest.approx(0.91)
        assert response.data.metrics.current_ratio == pytest.approx(1.04)
        assert response.data.metrics.payout_ratio == pytest.approx(0.15)

    async def test_returns_error_on_empty_income(self, adapter: FMPAdapter) -> None:
        async def mock_get(client, path: str, **params):
            return []

        with patch.object(adapter, "_get", new=mock_get):
            with patch("adapters.fmp.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_financials("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_on_none_response(self, adapter: FMPAdapter) -> None:
        async def mock_get(client, path: str, **params):
            return None

        with patch.object(adapter, "_get", new=mock_get):
            with patch("adapters.fmp.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_financials("AAPL")

        assert response.data is None
        assert response.error is not None


class TestGetProfile:
    async def test_returns_profile_on_success(self, adapter: FMPAdapter) -> None:
        raw_payload = [
            {
                "symbol": "AAPL",
                "companyName": "Apple Inc.",
                "exchange": "NASDAQ",
                "currency": "USD",
                "isin": "US0378331005",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "description": "Apple designs consumer electronics.",
                "country": "US",
                "fullTimeEmployees": "150000",
                "isEtf": False,
                "isFund": False,
            }
        ]

        with patch.object(adapter, "_get", new=AsyncMock(return_value=raw_payload)):
            with patch("adapters.fmp.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_profile("AAPL")

        assert response.data is not None
        assert isinstance(response.data, CompanyIdentity)
        assert response.data.name == "Apple Inc."
        assert response.data.exchange == "NASDAQ"
        assert response.data.sector == "Technology"
        assert response.data.industry == "Consumer Electronics"
        assert response.data.country == "US"
        assert response.data.employees == 150000
        assert response.data.security_type == "equity"
        assert response.error is None

    async def test_returns_etf_security_type(self, adapter: FMPAdapter) -> None:
        raw_payload = [
            {
                "symbol": "SPY",
                "companyName": "SPDR S&P 500 ETF Trust",
                "exchange": "NYSE",
                "currency": "USD",
                "isEtf": True,
                "isFund": False,
            }
        ]

        with patch.object(adapter, "_get", new=AsyncMock(return_value=raw_payload)):
            with patch("adapters.fmp.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_profile("SPY")

        assert response.data is not None
        assert response.data.security_type == "etf"

    async def test_returns_error_on_empty_profile(self, adapter: FMPAdapter) -> None:
        with patch.object(adapter, "_get", new=AsyncMock(return_value=None)):
            with patch("adapters.fmp.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_profile("UNKNOWN")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_on_missing_name_field(
        self, adapter: FMPAdapter
    ) -> None:
        raw_payload = [{"symbol": "AAPL", "exchange": "NASDAQ"}]

        with patch.object(adapter, "_get", new=AsyncMock(return_value=raw_payload)):
            with patch("adapters.fmp.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                response = await adapter.get_profile("AAPL")

        assert response.data is None
        assert response.error is not None
