from unittest.mock import patch

from fastapi.testclient import TestClient

from api.index import app

client = TestClient(app)

MOCK_TRENDS_DATA = {
    "series": [{"date": "2025-01-01", "Gold": 75, "Silver": 50}],
    "latest": [
        {"commodity": "Gold", "interest": 75, "momentum": 2.5},
        {"commodity": "Silver", "interest": 50, "momentum": -1.0},
    ],
}


def test_trends_requires_commodities():
    response = client.get("/api/trends")

    assert response.status_code == 422


def test_trends_rejects_unknown_commodity():
    response = client.get("/api/trends?commodities=Unobtanium")

    assert response.status_code == 400


def test_trends_rejects_unknown_timeframe():
    response = client.get("/api/trends?commodities=Gold&timeframe=Invalid")

    assert response.status_code == 400


def test_trends_returns_cached_result():
    with (
        patch(
            "routers.trends.get_trends_cache", return_value=MOCK_TRENDS_DATA
        ) as mock_cache,
        patch("routers.trends.fetch_trends_data") as mock_fetch,
    ):
        response = client.get("/api/trends?commodities=Gold&commodities=Silver")

    assert response.status_code == 200
    assert response.json() == MOCK_TRENDS_DATA
    mock_cache.assert_called_once()
    mock_fetch.assert_not_called()


def test_trends_fetches_and_caches_on_miss():
    with (
        patch("routers.trends.get_trends_cache", return_value=None),
        patch(
            "routers.trends.fetch_trends_data", return_value=MOCK_TRENDS_DATA
        ) as mock_fetch,
        patch("routers.trends.upsert_trends_cache") as mock_upsert,
    ):
        response = client.get("/api/trends?commodities=Gold&commodities=Silver")

    assert response.status_code == 200
    assert response.json() == MOCK_TRENDS_DATA
    mock_fetch.assert_called_once()
    mock_upsert.assert_called_once()


def test_trends_raises_502_on_fetch_error():
    with (
        patch("routers.trends.get_trends_cache", return_value=None),
        patch(
            "routers.trends.fetch_trends_data",
            side_effect=Exception("Google rate limit"),
        ),
    ):
        response = client.get("/api/trends?commodities=Gold")

    assert response.status_code == 502
