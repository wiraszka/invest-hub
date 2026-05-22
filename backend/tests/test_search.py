from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.index import app

client = TestClient(app)

MOCK_SYMBOLS = [
    {"ticker": "AAPL", "name": "Apple Inc.", "cik": 320193},
    {"ticker": "AMZN", "name": "Amazon.com Inc.", "cik": 1018724},
    {"ticker": "AU", "name": "AngloGold Ashanti PLC", "cik": 1138118},
    {"ticker": "NNE", "name": "Nano Nuclear Energy Inc.", "cik": 1978313},
    {"ticker": "AAP", "name": "Advance Auto Parts Inc.", "cik": 1158449},
]


@pytest.fixture(autouse=True)
def mock_symbol_cache():
    with patch("services.search._cache", MOCK_SYMBOLS):
        yield


def test_search_returns_results():
    response = client.get("/api/v1/search?q=AAPL")

    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1
    assert results[0]["ticker"] == "AAPL"


def test_search_exact_ticker_ranked_first():
    response = client.get("/api/v1/search?q=AU")

    assert response.status_code == 200
    results = response.json()
    assert results[0]["ticker"] == "AU"


def test_search_by_name():
    response = client.get("/api/v1/search?q=nano")

    assert response.status_code == 200
    results = response.json()
    tickers = [r["ticker"] for r in results]
    assert "NNE" in tickers


def test_search_returns_at_most_ten_results():
    response = client.get("/api/v1/search?q=A")

    assert response.status_code == 200
    assert len(response.json()) <= 10


def test_search_result_shape():
    response = client.get("/api/v1/search?q=AAPL")

    assert response.status_code == 200
    result = response.json()[0]
    assert "ticker" in result
    assert "name" in result
    assert "cik" in result


def test_search_missing_query_returns_422():
    response = client.get("/api/v1/search")

    assert response.status_code == 422
