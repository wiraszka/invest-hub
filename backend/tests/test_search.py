from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.index import app

client = TestClient(app)

MOCK_TICKERS = {
    "0": {"ticker": "AAPL", "title": "Apple Inc.", "cik_str": 320193},
    "1": {"ticker": "AMZN", "title": "Amazon.com Inc.", "cik_str": 1018724},
    "2": {"ticker": "AU", "title": "AngloGold Ashanti PLC", "cik_str": 1138118},
    "3": {"ticker": "NNE", "title": "Nano Nuclear Energy Inc.", "cik_str": 1978313},
    "4": {"ticker": "AAP", "title": "Advance Auto Parts Inc.", "cik_str": 1158449},
}


@pytest.fixture(autouse=True)
def mock_sec_tickers():
    with patch("services.search._cache", MOCK_TICKERS):
        yield


def test_search_returns_results():
    response = client.get("/api/search?q=AAPL")

    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1
    assert results[0]["ticker"] == "AAPL"


def test_search_exact_ticker_ranked_first():
    response = client.get("/api/search?q=AU")

    assert response.status_code == 200
    results = response.json()
    assert results[0]["ticker"] == "AU"


def test_search_by_name():
    response = client.get("/api/search?q=nano")

    assert response.status_code == 200
    results = response.json()
    tickers = [r["ticker"] for r in results]
    assert "NNE" in tickers


def test_search_returns_at_most_five_results():
    response = client.get("/api/search?q=A")

    assert response.status_code == 200
    assert len(response.json()) <= 5


def test_search_result_shape():
    response = client.get("/api/search?q=AAPL")

    assert response.status_code == 200
    result = response.json()[0]
    assert "ticker" in result
    assert "name" in result
    assert "cik" in result


def test_search_missing_query_returns_422():
    response = client.get("/api/search")

    assert response.status_code == 422
