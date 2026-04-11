from unittest.mock import patch

from fastapi.testclient import TestClient

from api.index import app

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
