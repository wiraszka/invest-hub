from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.twelvedata import TwelveDataAdapter
from models.market_data import PriceHistory, Quote


@pytest.fixture
def adapter() -> TwelveDataAdapter:
    return TwelveDataAdapter()


class TestGetQuote:
    async def test_returns_quote_on_success(self, adapter: TwelveDataAdapter) -> None:
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {"price": "150.25"}

        with patch("adapters.twelvedata.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            response = await adapter.get_quote("AAPL")

        assert response.data is not None
        assert isinstance(response.data, Quote)
        assert response.data.price == 150.25
        assert response.data.symbol == "AAPL"
        assert response.provider == "twelvedata"
        assert response.error is None

    async def test_returns_error_on_http_failure(
        self, adapter: TwelveDataAdapter
    ) -> None:
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 429

        with patch("adapters.twelvedata.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            response = await adapter.get_quote("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_on_missing_price_field(
        self, adapter: TwelveDataAdapter
    ) -> None:
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {"message": "Rate limit exceeded"}

        with patch("adapters.twelvedata.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            response = await adapter.get_quote("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_on_exception(self, adapter: TwelveDataAdapter) -> None:
        with patch("adapters.twelvedata.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=RuntimeError("network error"))
            mock_client_cls.return_value = mock_client

            response = await adapter.get_quote("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_when_circuit_is_open(
        self, adapter: TwelveDataAdapter
    ) -> None:
        adapter._circuit._failures = adapter._circuit.failure_threshold
        adapter._circuit._opened_at = time.monotonic()

        response = await adapter.get_quote("AAPL")

        assert response.data is None
        assert response.error is not None


class TestGetPriceHistory:
    async def test_returns_history_on_success(self, adapter: TwelveDataAdapter) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "values": [
                {"datetime": "2024-01-02", "close": "185.50"},
                {"datetime": "2024-01-01", "close": "184.00"},
            ]
        }

        with patch("adapters.twelvedata.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            response = await adapter.get_price_history("AAPL", days=2)

        assert response.data is not None
        assert isinstance(response.data, PriceHistory)
        assert response.data.ticker == "AAPL"
        assert len(response.data.history) == 2
        assert response.data.history[0].date == "2024-01-01"
        assert response.data.history[0].close == 184.00

    async def test_returns_error_on_missing_values_key(
        self, adapter: TwelveDataAdapter
    ) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"message": "Invalid API key"}

        with patch("adapters.twelvedata.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            response = await adapter.get_price_history("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_when_circuit_is_open(
        self, adapter: TwelveDataAdapter
    ) -> None:
        adapter._circuit._failures = adapter._circuit.failure_threshold
        adapter._circuit._opened_at = time.monotonic()

        response = await adapter.get_price_history("AAPL")

        assert response.data is None
        assert response.error is not None


class TestUnsupportedMethods:
    async def test_get_financials_returns_error(
        self, adapter: TwelveDataAdapter
    ) -> None:
        response = await adapter.get_financials("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_get_profile_returns_error(self, adapter: TwelveDataAdapter) -> None:
        response = await adapter.get_profile("AAPL")

        assert response.data is None
        assert response.error is not None
