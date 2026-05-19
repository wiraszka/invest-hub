from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from adapters.finnhub import FinnhubAdapter
from models.market_data import Quote


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

    async def test_returns_error_when_price_is_zero(self, adapter: FinnhubAdapter) -> None:
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


class TestGetFinancials:
    async def test_always_returns_error(self, adapter: FinnhubAdapter) -> None:
        response = await adapter.get_financials("AAPL")

        assert response.data is None
        assert "free tier" in (response.error or "").lower()
