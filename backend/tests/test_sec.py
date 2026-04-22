from unittest.mock import patch

import pytest

from services.sec import (
    ANNUAL_FORM_TYPES,
    find_recent_annual,
    get_sic_metadata,
    get_xbrl_facts,
    resolve_cik,
)

MOCK_TICKER_JSON = {
    "0": {"ticker": "NNE", "cik_str": 1898848, "title": "Nano Nuclear Energy Inc."},
    "1": {"ticker": "AAPL", "cik_str": 320193, "title": "Apple Inc."},
}

MOCK_XBRL_FACTS = {
    "facts": {
        "us-gaap": {
            "CashAndCashEquivalentsAtCarryingValue": {
                "units": {
                    "USD": [
                        {"val": 10_000_000, "end": "2025-12-31", "form": "10-K"},
                        {"val": 8_000_000, "end": "2024-12-31", "form": "10-K"},
                    ]
                }
            },
            "LongTermDebt": {
                "units": {
                    "USD": [
                        {"val": 2_000_000, "end": "2025-12-31", "form": "10-K"},
                    ]
                }
            },
            "Revenues": {
                "units": {
                    "USD": [
                        {"val": 0, "end": "2025-12-31", "form": "10-K"},
                    ]
                }
            },
        }
    }
}

_SUBMISSIONS_40F = {
    "filings": {
        "recent": {
            "form": ["40-F", "6-K", "6-K"],
            "accessionNumber": [
                "0001234567-25-000001",
                "0001234567-25-000002",
                "0001234567-25-000003",
            ],
            "primaryDocument": ["form40f.htm", "form6k1.htm", "form6k2.htm"],
            "filingDate": ["2025-03-01", "2024-12-01", "2024-09-01"],
        }
    }
}

_SUBMISSIONS_NO_ANNUAL = {
    "filings": {
        "recent": {
            "form": ["10-Q", "8-K"],
            "accessionNumber": ["0001234567-25-000002", "0001234567-25-000003"],
            "primaryDocument": ["form10q.htm", "form8k.htm"],
            "filingDate": ["2025-02-01", "2025-01-01"],
        }
    }
}


def test_resolve_cik_returns_padded_string():
    with patch("services.sec.requests.get") as mock_get:
        mock_get.return_value.json.return_value = MOCK_TICKER_JSON
        mock_get.return_value.raise_for_status = lambda: None

        cik = resolve_cik("NNE")

    assert cik == "0001898848"


def test_resolve_cik_case_insensitive():
    with patch("services.sec.requests.get") as mock_get:
        mock_get.return_value.json.return_value = MOCK_TICKER_JSON
        mock_get.return_value.raise_for_status = lambda: None

        cik = resolve_cik("nne")

    assert cik == "0001898848"


def test_resolve_cik_raises_on_unknown_ticker():
    with patch("services.sec.requests.get") as mock_get:
        mock_get.return_value.json.return_value = MOCK_TICKER_JSON
        mock_get.return_value.raise_for_status = lambda: None

        with pytest.raises(ValueError, match="Ticker not found"):
            resolve_cik("ZZZZ")


def test_annual_form_types_includes_40f():
    assert "40-F" in ANNUAL_FORM_TYPES
    assert "40-F/A" in ANNUAL_FORM_TYPES


def test_find_recent_annual_returns_40f():
    accession, primary_doc, form_type, filing_date = find_recent_annual(_SUBMISSIONS_40F)

    assert form_type == "40-F"
    assert primary_doc == "form40f.htm"
    assert filing_date == "2025-03-01"


def test_find_recent_annual_raises_when_no_annual_filing():
    with pytest.raises(ValueError, match="No recent annual filing"):
        find_recent_annual(_SUBMISSIONS_NO_ANNUAL)


def test_get_xbrl_facts_returns_structured_data():
    with patch("services.sec.requests.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = MOCK_XBRL_FACTS

        result, _ = get_xbrl_facts("0000320193", "10-K")

    assert result["cash"] == 10_000_000
    assert result["total_debt"] == 2_000_000
    assert result["net_debt"] == -8_000_000
    assert result["revenue"] == 0


_SUBMISSIONS_10K = {
    "sicDescription": "Gold and Silver Ores Mining",
    "filings": {
        "recent": {
            "form": ["10-K", "10-Q", "8-K"],
            "accessionNumber": [
                "0001234567-25-000001",
                "0001234567-25-000002",
                "0001234567-25-000003",
            ],
            "primaryDocument": ["form10k.htm", "form10q.htm", "form8k.htm"],
            "filingDate": ["2025-03-01", "2024-12-01", "2024-09-01"],
        }
    },
}

_SUBMISSIONS_40F_SIC = {
    "sicDescription": "Crude Petroleum and Natural Gas",
    "filings": {
        "recent": {
            "form": ["40-F", "6-K"],
            "accessionNumber": [
                "0001234567-25-000001",
                "0001234567-25-000002",
            ],
            "primaryDocument": ["form40f.htm", "form6k.htm"],
            "filingDate": ["2025-03-01", "2024-12-01"],
        }
    },
}

_SUBMISSIONS_20F_SIC = {
    "sicDescription": "Services-Computer Programming",
    "filings": {
        "recent": {
            "form": ["20-F", "6-K"],
            "accessionNumber": [
                "0001234567-25-000001",
                "0001234567-25-000002",
            ],
            "primaryDocument": ["form20f.htm", "form6k.htm"],
            "filingDate": ["2025-03-01", "2024-12-01"],
        }
    },
}


def test_get_sic_metadata_returns_sector_and_country_for_10k():
    with patch("services.sec.requests.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.side_effect = [MOCK_TICKER_JSON, _SUBMISSIONS_10K]

        result = get_sic_metadata("NNE")

    assert result is not None
    assert result["sector"] == "Gold and Silver Ores Mining"
    assert result["country"] == "United States"
    assert result["asset_type"] == "Equity"


def test_get_sic_metadata_returns_none_when_ticker_not_found():
    with patch("services.sec.requests.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = MOCK_TICKER_JSON

        result = get_sic_metadata("ZZZZ")

    assert result is None


def test_get_sic_metadata_infers_canada_from_40f():
    with patch("services.sec.requests.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.side_effect = [MOCK_TICKER_JSON, _SUBMISSIONS_40F_SIC]

        result = get_sic_metadata("NNE")

    assert result is not None
    assert result["country"] == "Canada"


def test_get_sic_metadata_rejects_to_ticker_when_sec_match_is_10k():
    with patch("services.sec.requests.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.side_effect = [MOCK_TICKER_JSON, _SUBMISSIONS_10K]

        result = get_sic_metadata("NNE.TO")

    assert result is None


def test_get_sic_metadata_accepts_to_ticker_when_sec_match_is_40f():
    with patch("services.sec.requests.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.side_effect = [MOCK_TICKER_JSON, _SUBMISSIONS_40F_SIC]

        result = get_sic_metadata("NNE.TO")

    assert result is not None
    assert result["country"] == "Canada"
    assert result["sector"] == "Crude Petroleum and Natural Gas"


def test_get_sic_metadata_infers_international_from_20f():
    with patch("services.sec.requests.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.side_effect = [MOCK_TICKER_JSON, _SUBMISSIONS_20F_SIC]

        result = get_sic_metadata("NNE")

    assert result is not None
    assert result["country"] == "International"


def test_get_xbrl_facts_returns_none_for_missing_concepts():
    with patch("services.sec.requests.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = {"facts": {"us-gaap": {}}}

        result, _ = get_xbrl_facts("0000320193", "10-K")

    assert result["cash"] is None
    assert result["revenue"] is None
    assert result["net_debt"] is None
