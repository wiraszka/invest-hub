from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.index import app
from services.price import get_current_price

client = TestClient(app)

MOCK_PRICE = {"ticker": "NNE", "price": 18.42, "currency": "USD"}
MOCK_HISTORY = {
    "ticker": "NNE",
    "history": [
        {"date": "2025-04-10", "close": 17.5},
        {"date": "2025-04-11", "close": 18.42},
    ],
}


def test_current_price_returns_ticker_and_price():
    with patch(
        "routers.price.get_current_price", new=AsyncMock(return_value=MOCK_PRICE)
    ):
        response = client.get("/api/v1/price/NNE")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "NNE"
    assert data["price"] == 18.42


def test_current_price_uppercases_ticker():
    with patch(
        "routers.price.get_current_price", new=AsyncMock(return_value=MOCK_PRICE)
    ) as mock:
        client.get("/api/v1/price/NNE")

    mock.assert_called_once_with("NNE")


def test_current_price_returns_404_on_invalid_ticker():
    with patch(
        "routers.price.get_current_price",
        new=AsyncMock(side_effect=ValueError("Not found")),
    ):
        response = client.get("/api/v1/price/INVALID")

    assert response.status_code == 404


def test_price_history_returns_ticker_and_history():
    with patch(
        "routers.price.get_price_history", new=AsyncMock(return_value=MOCK_HISTORY)
    ):
        response = client.get("/api/v1/price/NNE/history")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "NNE"
    assert len(data["history"]) == 2
    assert data["history"][0]["date"] == "2025-04-10"


def test_price_history_returns_404_on_invalid_ticker():
    with patch(
        "routers.price.get_price_history",
        new=AsyncMock(side_effect=ValueError("Not found")),
    ):
        response = client.get("/api/v1/price/INVALID/history")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# get_current_price failover (service-level)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_price_returns_twelvedata_price_when_available():
    from datetime import datetime, timezone

    from models.market_data import Quote

    mock_quote = Quote(
        symbol="NNE",
        price=18.42,
        currency="USD",
        source="twelvedata",
        fetched_at=datetime.now(timezone.utc),
    )
    mock_adapter = MagicMock()
    mock_adapter.get_quote = AsyncMock(
        return_value=type("R", (), {"data": mock_quote, "error": None})()
    )

    with patch("services.price.registry") as mock_registry:
        mock_registry.for_capability.return_value = [mock_adapter]
        result = await get_current_price("NNE")

    assert result["ticker"] == "NNE"
    assert result["price"] == 18.42
    assert result["currency"] == "USD"


@pytest.mark.asyncio
async def test_get_current_price_falls_back_to_fmp_when_twelvedata_fails():
    from datetime import datetime, timezone

    from models.market_data import Quote

    mock_quote = Quote(
        symbol="NNE",
        price=42.50,
        currency="USD",
        source="fmp",
        fetched_at=datetime.now(timezone.utc),
    )
    mock_td = MagicMock()
    mock_td.get_quote = AsyncMock(
        return_value=type("R", (), {"data": None, "error": "TD down"})()
    )
    mock_fmp = MagicMock()
    mock_fmp.get_quote = AsyncMock(
        return_value=type("R", (), {"data": mock_quote, "error": None})()
    )

    with patch("services.price.registry") as mock_registry:
        mock_registry.for_capability.return_value = [mock_td, mock_fmp]
        result = await get_current_price("NNE")

    assert result["ticker"] == "NNE"
    assert result["price"] == 42.50
    assert result["currency"] == "USD"


@pytest.mark.asyncio
async def test_get_current_price_includes_currency_from_quote():
    from datetime import datetime, timezone

    from models.market_data import Quote

    mock_quote = Quote(
        symbol="SU.TO",
        price=55.10,
        currency="CAD",
        source="twelvedata",
        fetched_at=datetime.now(timezone.utc),
    )
    mock_adapter = MagicMock()
    mock_adapter.get_quote = AsyncMock(
        return_value=type("R", (), {"data": mock_quote, "error": None})()
    )

    with patch("services.price.registry") as mock_registry:
        mock_registry.for_capability.return_value = [mock_adapter]
        result = await get_current_price("SU.TO")

    assert result["currency"] == "CAD"


@pytest.mark.asyncio
async def test_get_current_price_raises_when_both_sources_fail():
    mock_td = MagicMock()
    mock_td.get_quote = AsyncMock(
        return_value=type("R", (), {"data": None, "error": "TD down"})()
    )
    mock_fmp = MagicMock()
    mock_fmp.get_quote = AsyncMock(
        return_value=type("R", (), {"data": None, "error": "FMP down"})()
    )

    with patch("services.price.registry") as mock_registry:
        mock_registry.for_capability.return_value = [mock_td, mock_fmp]
        with pytest.raises(ValueError, match="price"):
            await get_current_price("NNE")
