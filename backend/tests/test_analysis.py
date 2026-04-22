from unittest.mock import patch

from fastapi.testclient import TestClient

from api.index import app

client = TestClient(app)

MOCK_FILING = "This is a 10-K filing excerpt for a revenue-generating company."
MOCK_FMP = {
    "fmp_ticker": "AAPL",
    "currency": "USD",
    "income": [{"year": 2024, "revenue": 20_000_000, "gross_profit": 8_000_000, "net_income": 2_000_000, "ebitda": 4_000_000, "operating_income": 3_000_000}],
    "balance_sheet": {"cash": 5_000_000, "total_debt": 1_000_000, "net_debt": -4_000_000, "total_equity": 20_000_000, "total_assets": 25_000_000},
    "cash_flow": [{"year": 2024, "operating_cash_flow": 3_000_000, "capex": -500_000, "free_cash_flow": 2_500_000}],
    "metrics": {"market_cap": 50_000_000, "enterprise_value": 46_000_000, "pe_ratio": 25.0, "ev_ebitda": 11.5},
}
MOCK_EXTRACTION = {
    "company_type": "revenue-generating",
    "company_independence": "independent",
    "charts": {
        "revenue_by_segment": None,
        "reserves_by_asset": None,
        "production_mix": None,
        "nav_vs_ev": None,
    },
}
MOCK_SNAPSHOT = "- A revenue-generating software company operating globally.\n- Core product is a SaaS platform."
MOCK_DOC = {
    "ticker": "AAPL",
    "company_type": "revenue-generating",
    "snapshot": MOCK_SNAPSHOT,
    "chart_data": {"capital_structure": {"market_cap_usd": 50_000_000, "net_debt_usd": -4_000_000}},
    "fmp_data": MOCK_FMP,
    "updated_at": "2026-04-22T00:00:00+00:00",
}

_MOCK_ANNUAL = ("0001234567-25-000001", "form10k.htm", "10-K", "2025-01-01")

_SEC_PATCHES = {
    "routers.analysis.resolve_cik": "0000320193",
    "routers.analysis.get_submissions": {},
    "routers.analysis.find_recent_annual": _MOCK_ANNUAL,
    "routers.analysis.is_filing_stale": False,
    "routers.analysis.fetch_filing_text": MOCK_FILING,
    "routers.analysis.extract_10k_sections": MOCK_FILING,
}


def _full_pipeline_patches(extraction=None, snapshot=None, fmp=None):
    return {
        **_SEC_PATCHES,
        "routers.analysis.get_financials": fmp or MOCK_FMP,
        "routers.analysis.classify_and_extract": extraction or MOCK_EXTRACTION,
        "routers.analysis.generate_snapshot": snapshot or MOCK_SNAPSHOT,
    }


# ---------------------------------------------------------------------------
# GET /api/analysis/{ticker}
# ---------------------------------------------------------------------------


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
    assert data["snapshot"] == MOCK_SNAPSHOT


def test_fetch_analysis_uppercases_ticker():
    with patch("routers.analysis.get_analysis", return_value=MOCK_DOC) as mock:
        client.get("/api/analysis/aapl")

    mock.assert_called_once_with("AAPL")


# ---------------------------------------------------------------------------
# POST /api/analysis/{ticker} — happy path
# ---------------------------------------------------------------------------


def test_trigger_analysis_success():
    patches = _full_pipeline_patches()
    with (
        patch("routers.analysis.resolve_cik", return_value=patches.pop("routers.analysis.resolve_cik")),
        patch("routers.analysis.get_submissions", return_value=patches.pop("routers.analysis.get_submissions")),
        patch("routers.analysis.find_recent_annual", return_value=patches.pop("routers.analysis.find_recent_annual")),
        patch("routers.analysis.is_filing_stale", return_value=patches.pop("routers.analysis.is_filing_stale")),
        patch("routers.analysis.fetch_filing_text", return_value=patches.pop("routers.analysis.fetch_filing_text")),
        patch("routers.analysis.extract_10k_sections", return_value=patches.pop("routers.analysis.extract_10k_sections")),
        patch("routers.analysis.get_financials", return_value=patches["routers.analysis.get_financials"]),
        patch("routers.analysis.classify_and_extract", return_value=patches["routers.analysis.classify_and_extract"]),
        patch("routers.analysis.generate_snapshot", return_value=patches["routers.analysis.generate_snapshot"]),
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


def test_trigger_analysis_uppercases_ticker():
    with (
        patch("routers.analysis.resolve_cik", return_value="0000320193") as mock_cik,
        patch("routers.analysis.get_submissions", return_value={}),
        patch("routers.analysis.find_recent_annual", return_value=_MOCK_ANNUAL),
        patch("routers.analysis.is_filing_stale", return_value=False),
        patch("routers.analysis.fetch_filing_text", return_value=MOCK_FILING),
        patch("routers.analysis.extract_10k_sections", return_value=MOCK_FILING),
        patch("routers.analysis.get_financials", return_value=MOCK_FMP),
        patch("routers.analysis.classify_and_extract", return_value=MOCK_EXTRACTION),
        patch("routers.analysis.generate_snapshot", return_value=MOCK_SNAPSHOT),
        patch("routers.analysis.upsert_analysis"),
    ):
        client.post("/api/analysis/aapl")

    mock_cik.assert_called_once_with("AAPL")


# ---------------------------------------------------------------------------
# Standard charts computed from FMP data
# ---------------------------------------------------------------------------


def test_trigger_analysis_capital_structure_from_fmp():
    with (
        patch("routers.analysis.resolve_cik", return_value="0000320193"),
        patch("routers.analysis.get_submissions", return_value={}),
        patch("routers.analysis.find_recent_annual", return_value=_MOCK_ANNUAL),
        patch("routers.analysis.is_filing_stale", return_value=False),
        patch("routers.analysis.fetch_filing_text", return_value=MOCK_FILING),
        patch("routers.analysis.extract_10k_sections", return_value=MOCK_FILING),
        patch("routers.analysis.get_financials", return_value=MOCK_FMP),
        patch("routers.analysis.classify_and_extract", return_value=MOCK_EXTRACTION),
        patch("routers.analysis.generate_snapshot", return_value=MOCK_SNAPSHOT),
        patch("routers.analysis.upsert_analysis") as mock_upsert,
    ):
        client.post("/api/analysis/AAPL")

    _, _, _, chart_data, _, market_cap_usd, _ = mock_upsert.call_args.args
    assert market_cap_usd == 50_000_000
    assert chart_data["capital_structure"]["market_cap_usd"] == 50_000_000
    assert chart_data["capital_structure"]["net_debt_usd"] == -4_000_000


def test_trigger_analysis_cash_burn_for_pre_revenue():
    pre_revenue_extraction = {**MOCK_EXTRACTION, "company_type": "pre-revenue"}
    fmp_with_negative_ocf = {
        **MOCK_FMP,
        "cash_flow": [{"year": 2024, "operating_cash_flow": -8_000_000, "capex": -500_000, "free_cash_flow": -8_500_000}],
    }

    with (
        patch("routers.analysis.resolve_cik", return_value="0000320193"),
        patch("routers.analysis.get_submissions", return_value={}),
        patch("routers.analysis.find_recent_annual", return_value=_MOCK_ANNUAL),
        patch("routers.analysis.is_filing_stale", return_value=False),
        patch("routers.analysis.fetch_filing_text", return_value=MOCK_FILING),
        patch("routers.analysis.extract_10k_sections", return_value=MOCK_FILING),
        patch("routers.analysis.get_financials", return_value=fmp_with_negative_ocf),
        patch("routers.analysis.classify_and_extract", return_value=pre_revenue_extraction),
        patch("routers.analysis.generate_snapshot", return_value=MOCK_SNAPSHOT),
        patch("routers.analysis.upsert_analysis") as mock_upsert,
    ):
        client.post("/api/analysis/AAPL")

    _, _, _, chart_data, _, _, _ = mock_upsert.call_args.args
    assert chart_data["cash_burn"]["annual_burn_usd"] == 8_000_000


# ---------------------------------------------------------------------------
# Soft SEC failure — falls back to FMP description as narrative
# ---------------------------------------------------------------------------


def test_trigger_analysis_continues_when_sec_cik_not_found():
    with (
        patch("routers.analysis.resolve_cik", side_effect=ValueError("Ticker not found")),
        patch("routers.analysis.get_financials", return_value=MOCK_FMP),
        patch("routers.analysis.get_profile_description", return_value="A software company."),
        patch("routers.analysis.classify_and_extract", return_value=MOCK_EXTRACTION),
        patch("routers.analysis.generate_snapshot", return_value=MOCK_SNAPSHOT),
        patch("routers.analysis.upsert_analysis"),
    ):
        response = client.post("/api/analysis/AAPL")

    assert response.status_code == 200
    data = response.json()
    assert data["data_integrity"]["data_source"] == "FMP only"
    assert data["data_integrity"]["filing_type"] == "none"


def test_trigger_analysis_data_source_sec_and_fmp_when_both_succeed():
    with (
        patch("routers.analysis.resolve_cik", return_value="0000320193"),
        patch("routers.analysis.get_submissions", return_value={}),
        patch("routers.analysis.find_recent_annual", return_value=_MOCK_ANNUAL),
        patch("routers.analysis.is_filing_stale", return_value=False),
        patch("routers.analysis.fetch_filing_text", return_value=MOCK_FILING),
        patch("routers.analysis.extract_10k_sections", return_value=MOCK_FILING),
        patch("routers.analysis.get_financials", return_value=MOCK_FMP),
        patch("routers.analysis.classify_and_extract", return_value=MOCK_EXTRACTION),
        patch("routers.analysis.generate_snapshot", return_value=MOCK_SNAPSHOT),
        patch("routers.analysis.upsert_analysis"),
    ):
        response = client.post("/api/analysis/AAPL")

    assert response.status_code == 200
    assert response.json()["data_integrity"]["data_source"] == "SEC + FMP"


# ---------------------------------------------------------------------------
# data_integrity schema
# ---------------------------------------------------------------------------


def test_trigger_analysis_data_integrity_fields():
    with (
        patch("routers.analysis.resolve_cik", return_value="0000320193"),
        patch("routers.analysis.get_submissions", return_value={}),
        patch("routers.analysis.find_recent_annual", return_value=_MOCK_ANNUAL),
        patch("routers.analysis.is_filing_stale", return_value=False),
        patch("routers.analysis.fetch_filing_text", return_value=MOCK_FILING),
        patch("routers.analysis.extract_10k_sections", return_value=MOCK_FILING),
        patch("routers.analysis.get_financials", return_value=MOCK_FMP),
        patch("routers.analysis.classify_and_extract", return_value=MOCK_EXTRACTION),
        patch("routers.analysis.generate_snapshot", return_value=MOCK_SNAPSHOT),
        patch("routers.analysis.upsert_analysis"),
    ):
        response = client.post("/api/analysis/AAPL")

    di = response.json()["data_integrity"]
    assert "filing_type" in di
    assert "filing_date" in di
    assert "filing_recency" in di
    assert "sections_extracted" in di
    assert "data_source" in di
    assert "fmp_financials" in di
    assert "reporting_currency" in di
    assert "company_independence" in di
    assert "llm_model" in di
    assert "analysis_timestamp" in di
    assert "xbrl_quality" not in di


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_trigger_analysis_fmp_failure_proceeds_with_empty_financials():
    """FMP failure is tolerated — analysis runs with empty financials."""
    with (
        patch("routers.analysis.resolve_cik", return_value="0000320193"),
        patch("routers.analysis.get_submissions", return_value={}),
        patch("routers.analysis.find_recent_annual", return_value=_MOCK_ANNUAL),
        patch("routers.analysis.is_filing_stale", return_value=False),
        patch("routers.analysis.fetch_filing_text", return_value=MOCK_FILING),
        patch("routers.analysis.extract_10k_sections", return_value=MOCK_FILING),
        patch("routers.analysis.get_financials", return_value=None),
        patch("routers.analysis.classify_and_extract", return_value=MOCK_EXTRACTION),
        patch("routers.analysis.generate_snapshot", return_value=MOCK_SNAPSHOT),
        patch("routers.analysis.upsert_analysis"),
    ):
        response = client.post("/api/analysis/AAPL")

    assert response.status_code == 200
    assert response.json()["data_integrity"]["fmp_financials"] == "none"


def test_trigger_analysis_llm_classify_error_returns_502():
    with (
        patch("routers.analysis.resolve_cik", return_value="0000320193"),
        patch("routers.analysis.get_submissions", return_value={}),
        patch("routers.analysis.find_recent_annual", return_value=_MOCK_ANNUAL),
        patch("routers.analysis.is_filing_stale", return_value=False),
        patch("routers.analysis.fetch_filing_text", return_value=MOCK_FILING),
        patch("routers.analysis.extract_10k_sections", return_value=MOCK_FILING),
        patch("routers.analysis.get_financials", return_value=MOCK_FMP),
        patch("routers.analysis.classify_and_extract", side_effect=Exception("LLM error")),
    ):
        response = client.post("/api/analysis/AAPL")

    assert response.status_code == 502
