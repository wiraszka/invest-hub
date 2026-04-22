from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.index import app
from services.price import get_current_price

client = TestClient(app)

MOCK_PRICE = {"ticker": "NNE", "price": 18.42}
MOCK_HISTORY = {
    "ticker": "NNE",
    "history": [
        {"date": "2025-04-10", "close": 17.5},
        {"date": "2025-04-11", "close": 18.42},
    ],
}


def test_current_price_returns_ticker_and_price():
    with patch("routers.price.get_current_price", return_value=MOCK_PRICE):
        response = client.get("/api/price/NNE")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "NNE"
    assert data["price"] == 18.42


def test_current_price_uppercases_ticker():
    with patch("routers.price.get_current_price", return_value=MOCK_PRICE) as mock:
        client.get("/api/price/nne")

    mock.assert_called_once_with("NNE")


def test_current_price_returns_404_on_invalid_ticker():
    with patch("routers.price.get_current_price", side_effect=ValueError("Not found")):
        response = client.get("/api/price/INVALID")

    assert response.status_code == 404


def test_price_history_returns_ticker_and_history():
    with patch("routers.price.get_price_history", return_value=MOCK_HISTORY):
        response = client.get("/api/price/NNE/history")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "NNE"
    assert len(data["history"]) == 2
    assert data["history"][0]["date"] == "2025-04-10"


def test_price_history_returns_404_on_invalid_ticker():
    with patch("routers.price.get_price_history", side_effect=ValueError("Not found")):
        response = client.get("/api/price/INVALID/history")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# get_current_price failover (service-level)
# ---------------------------------------------------------------------------


def _td_ok_response(price: float) -> MagicMock:
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {"price": str(price)}
    return mock


def test_get_current_price_returns_twelvedata_price_when_available():
    with patch("services.price.requests.get", return_value=_td_ok_response(18.42)):
        result = get_current_price("NNE")

    assert result["ticker"] == "NNE"
    assert result["price"] == 18.42


def test_get_current_price_falls_back_to_fmp_when_twelvedata_raises():
    with patch("services.price.requests.get", side_effect=Exception("TD down")):
        with patch("services.price.get_quote_price", return_value=42.50):
            result = get_current_price("NNE")

    assert result["ticker"] == "NNE"
    assert result["price"] == 42.50


def test_get_current_price_falls_back_to_fmp_when_twelvedata_returns_error_body():
    bad_response = MagicMock()
    bad_response.raise_for_status = MagicMock()
    bad_response.json.return_value = {"message": "Invalid API key"}

    with patch("services.price.requests.get", return_value=bad_response):
        with patch("services.price.get_quote_price", return_value=42.50):
            result = get_current_price("NNE")

    assert result["price"] == 42.50


def test_get_current_price_raises_when_both_sources_fail():
    with patch("services.price.requests.get", side_effect=Exception("TD down")):
        with patch("services.price.get_quote_price", return_value=None):
            with pytest.raises(ValueError, match="price"):
                get_current_price("NNE")
