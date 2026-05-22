from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.openfigi import OpenFIGIAdapter
from models.market_data import CompanyIdentity


@pytest.fixture
def adapter() -> OpenFIGIAdapter:
    return OpenFIGIAdapter()


class TestLookup:
    async def test_returns_identity_on_success(self, adapter: OpenFIGIAdapter) -> None:
        raw_data = [
            {
                "data": [
                    {
                        "figi": "BBG000B9XRY4",
                        "name": "APPLE INC",
                        "exchCode": "US",
                        "marketSector": "Equity",
                    }
                ]
            }
        ]
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = raw_data

        with patch("adapters.openfigi.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            response = await adapter.lookup("AAPL")

        assert response.data is not None
        assert isinstance(response.data, CompanyIdentity)
        assert response.data.figi == "BBG000B9XRY4"
        assert response.data.name == "APPLE INC"
        assert response.data.exchange == "US"
        assert response.provider == "openfigi"
        assert response.error is None

    async def test_passes_exchange_hint_in_payload(self, adapter: OpenFIGIAdapter) -> None:
        raw_data = [{"data": [{"figi": "BBG000B9XRY4", "name": "APPLE INC", "exchCode": "US"}]}]
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = raw_data

        with patch("adapters.openfigi.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await adapter.lookup("AAPL", exchange_hint="US")

        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload[0].get("exchCode") == "US"

    async def test_returns_error_on_http_failure(self, adapter: OpenFIGIAdapter) -> None:
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 401

        with patch("adapters.openfigi.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            response = await adapter.lookup("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_on_empty_data(self, adapter: OpenFIGIAdapter) -> None:
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = [{"data": []}]

        with patch("adapters.openfigi.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            response = await adapter.lookup("UNKNOWN")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_on_exception(self, adapter: OpenFIGIAdapter) -> None:
        with patch("adapters.openfigi.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=RuntimeError("timeout"))
            mock_client_cls.return_value = mock_client

            response = await adapter.lookup("AAPL")

        assert response.data is None
        assert response.error is not None
