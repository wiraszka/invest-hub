from unittest.mock import patch

from fastapi.testclient import TestClient

from api.index import app

client = TestClient(app)

MOCK_FILING = "This is a 10-K filing excerpt for a revenue-generating company."
MOCK_XBRL = {
    "cash": 5_000_000,
    "total_debt": 1_000_000,
    "net_debt": -4_000_000,
    "revenue": 20_000_000,
    "net_income": None,
    "shares_outstanding": 10_000_000,
    "operating_cash_flow": None,
}
MOCK_EXTRACTION = {
    "company_type": "revenue-generating",
    "company_independence": "independent",
    "charts": {
        "capital_structure": None,
        "revenue_by_segment": None,
        "cash_burn": None,
    },
}
MOCK_SNAPSHOT = "- A revenue-generating software company operating globally.\n- Core product is a SaaS platform."
MOCK_PRICE = {"ticker": "AAPL", "price": 5.00}
MOCK_DOC = {
    "ticker": "AAPL",
    "company_type": "revenue-generating",
    "snapshot": MOCK_SNAPSHOT,
    "chart_data": {
        "capital_structure": {"market_cap_usd": 50_000_000, "net_debt_usd": -4_000_000},
        "revenue_by_segment": None,
        "cash_burn": None,
    },
    "xbrl_data": MOCK_XBRL,
    "updated_at": "2026-04-12T00:00:00+00:00",
}

_MOCK_ANNUAL = ("0001234567-25-000001", "form10k.htm", "10-K", "2025-01-01")


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
    assert data["snapshot"] == MOCK_SNAPSHOT


def test_fetch_analysis_uppercases_ticker():
    with patch("routers.analysis.get_analysis", return_value=MOCK_DOC) as mock:
        client.get("/api/analysis/aapl")

    mock.assert_called_once_with("AAPL")


def test_trigger_analysis_success():
    with (
        patch("routers.analysis.resolve_cik", return_value="0000320193"),
        patch("routers.analysis.get_submissions", return_value={}),
        patch("routers.analysis.find_recent_annual", return_value=_MOCK_ANNUAL),
        patch("routers.analysis.is_filing_stale", return_value=False),
        patch("routers.analysis.fetch_filing_text", return_value=MOCK_FILING),
        patch("routers.analysis.extract_10k_sections", return_value=MOCK_FILING),
        patch("routers.analysis.get_xbrl_facts", return_value=(MOCK_XBRL, "USD")),
        patch("routers.analysis.classify_and_extract", return_value=MOCK_EXTRACTION),
        patch("routers.analysis.get_current_price", return_value=MOCK_PRICE),
        patch("routers.analysis.generate_snapshot", return_value=MOCK_SNAPSHOT),
        patch("routers.analysis.upsert_analysis"),
    ):
        response = client.post("/api/analysis/AAPL")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["company_type"] == "revenue-generating"
    assert data["snapshot"] == MOCK_SNAPSHOT
    assert "data_integrity" in data
    assert "updated_at" in data


def test_trigger_analysis_enriches_market_cap():
    with (
        patch("routers.analysis.resolve_cik", return_value="0000320193"),
        patch("routers.analysis.get_submissions", return_value={}),
        patch("routers.analysis.find_recent_annual", return_value=_MOCK_ANNUAL),
        patch("routers.analysis.is_filing_stale", return_value=False),
        patch("routers.analysis.fetch_filing_text", return_value=MOCK_FILING),
        patch("routers.analysis.extract_10k_sections", return_value=MOCK_FILING),
        patch("routers.analysis.get_xbrl_facts", return_value=(MOCK_XBRL, "USD")),
        patch("routers.analysis.classify_and_extract", return_value=MOCK_EXTRACTION),
        patch("routers.analysis.get_current_price", return_value=MOCK_PRICE),
        patch("routers.analysis.generate_snapshot", return_value=MOCK_SNAPSHOT),
        patch("routers.analysis.upsert_analysis") as mock_upsert,
    ):
        client.post("/api/analysis/AAPL")

    _, _, _, chart_data, _, market_cap_usd, _ = mock_upsert.call_args.args
    assert market_cap_usd == 50_000_000  # 10M shares × $5
    assert chart_data["capital_structure"]["market_cap_usd"] == 50_000_000
    assert chart_data["capital_structure"]["net_debt_usd"] == -4_000_000


def test_trigger_analysis_enriches_cash_burn_for_pre_revenue():
    pre_revenue_xbrl = {**MOCK_XBRL, "operating_cash_flow": -8_000_000}
    pre_revenue_extraction = {
        "company_type": "pre-revenue",
        "company_independence": "independent",
        "charts": {
            "capital_structure": None,
            "revenue_by_segment": None,
            "cash_burn": None,
        },
    }

    with (
        patch("routers.analysis.resolve_cik", return_value="0000320193"),
        patch("routers.analysis.get_submissions", return_value={}),
        patch("routers.analysis.find_recent_annual", return_value=_MOCK_ANNUAL),
        patch("routers.analysis.is_filing_stale", return_value=False),
        patch("routers.analysis.fetch_filing_text", return_value=MOCK_FILING),
        patch("routers.analysis.extract_10k_sections", return_value=MOCK_FILING),
        patch(
            "routers.analysis.get_xbrl_facts",
            return_value=(pre_revenue_xbrl, "USD"),
        ),
        patch(
            "routers.analysis.classify_and_extract", return_value=pre_revenue_extraction
        ),
        patch("routers.analysis.get_current_price", return_value=MOCK_PRICE),
        patch("routers.analysis.generate_snapshot", return_value=MOCK_SNAPSHOT),
        patch("routers.analysis.upsert_analysis") as mock_upsert,
    ):
        client.post("/api/analysis/AAPL")

    _, _, _, chart_data, _, _, _ = mock_upsert.call_args.args
    assert chart_data["cash_burn"]["annual_burn_usd"] == 8_000_000


def test_trigger_analysis_uppercases_ticker():
    with (
        patch("routers.analysis.resolve_cik", return_value="0000320193") as mock_cik,
        patch("routers.analysis.get_submissions", return_value={}),
        patch("routers.analysis.find_recent_annual", return_value=_MOCK_ANNUAL),
        patch("routers.analysis.is_filing_stale", return_value=False),
        patch("routers.analysis.fetch_filing_text", return_value=MOCK_FILING),
        patch("routers.analysis.extract_10k_sections", return_value=MOCK_FILING),
        patch("routers.analysis.get_xbrl_facts", return_value=(MOCK_XBRL, "USD")),
        patch("routers.analysis.classify_and_extract", return_value=MOCK_EXTRACTION),
        patch("routers.analysis.get_current_price", return_value=MOCK_PRICE),
        patch("routers.analysis.generate_snapshot", return_value=MOCK_SNAPSHOT),
        patch("routers.analysis.upsert_analysis"),
    ):
        client.post("/api/analysis/aapl")

    mock_cik.assert_called_once_with("AAPL")


def test_trigger_analysis_sec_not_found():
    with patch(
        "routers.analysis.resolve_cik", side_effect=ValueError("Ticker not found")
    ):
        response = client.post("/api/analysis/INVALID")

    assert response.status_code == 404


def test_trigger_analysis_sec_error():
    with patch(
        "routers.analysis.resolve_cik",
        side_effect=Exception("Connection error"),
    ):
        response = client.post("/api/analysis/AAPL")

    assert response.status_code == 502


def test_trigger_analysis_llm_error():
    with (
        patch("routers.analysis.resolve_cik", return_value="0000320193"),
        patch("routers.analysis.get_submissions", return_value={}),
        patch("routers.analysis.find_recent_annual", return_value=_MOCK_ANNUAL),
        patch("routers.analysis.is_filing_stale", return_value=False),
        patch("routers.analysis.fetch_filing_text", return_value=MOCK_FILING),
        patch("routers.analysis.extract_10k_sections", return_value=MOCK_FILING),
        patch("routers.analysis.get_xbrl_facts", return_value=(MOCK_XBRL, "USD")),
        patch(
            "routers.analysis.classify_and_extract", side_effect=Exception("API error")
        ),
    ):
        response = client.post("/api/analysis/AAPL")

    assert response.status_code == 502
