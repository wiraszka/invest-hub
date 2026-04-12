from unittest.mock import patch

from fastapi.testclient import TestClient

from api.index import app

client = TestClient(app)

MOCK_FILING = "This is a 10-K filing for a revenue-generating company..."
MOCK_MARKDOWN = "## Company Analysis\n\nSome analysis here."
MOCK_DOC = {
    "ticker": "AAPL",
    "company_type": "revenue-generating",
    "markdown": MOCK_MARKDOWN,
    "updated_at": "2026-04-12T00:00:00+00:00",
}


def test_fetch_analysis_not_found():
    with patch("routers.analysis.get_analysis", return_value=None):
        response = client.get("/api/analysis/AAPL")

    assert response.status_code == 404


def test_fetch_analysis_returns_stored_data():
    with patch("routers.analysis.get_analysis", return_value=MOCK_DOC):
        response = client.get("/api/analysis/AAPL")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["company_type"] == "revenue-generating"
    assert data["markdown"] == MOCK_MARKDOWN


def test_fetch_analysis_uppercases_ticker():
    with patch("routers.analysis.get_analysis", return_value=MOCK_DOC) as mock:
        client.get("/api/analysis/aapl")

    mock.assert_called_once_with("AAPL")


def test_trigger_analysis_success():
    with (
        patch("routers.analysis.get_recent_10k_text", return_value=MOCK_FILING),
        patch("routers.analysis.classify_company", return_value="revenue-generating"),
        patch("routers.analysis.run_analysis", return_value=MOCK_MARKDOWN),
        patch("routers.analysis.upsert_analysis"),
    ):
        response = client.post("/api/analysis/AAPL")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["company_type"] == "revenue-generating"
    assert data["status"] == "ok"


def test_trigger_analysis_uppercases_ticker():
    with (
        patch("routers.analysis.get_recent_10k_text", return_value=MOCK_FILING) as mock_sec,
        patch("routers.analysis.classify_company", return_value="revenue-generating"),
        patch("routers.analysis.run_analysis", return_value=MOCK_MARKDOWN),
        patch("routers.analysis.upsert_analysis"),
    ):
        client.post("/api/analysis/aapl")

    mock_sec.assert_called_once_with("AAPL")


def test_trigger_analysis_sec_not_found():
    with patch("routers.analysis.get_recent_10k_text", side_effect=ValueError("No 10-K found")):
        response = client.post("/api/analysis/INVALID")

    assert response.status_code == 404


def test_trigger_analysis_sec_error():
    with patch(
        "routers.analysis.get_recent_10k_text",
        side_effect=Exception("Connection error"),
    ):
        response = client.post("/api/analysis/AAPL")

    assert response.status_code == 502


def test_trigger_analysis_llm_error():
    with (
        patch("routers.analysis.get_recent_10k_text", return_value=MOCK_FILING),
        patch("routers.analysis.classify_company", side_effect=Exception("API error")),
    ):
        response = client.post("/api/analysis/AAPL")

    assert response.status_code == 502
