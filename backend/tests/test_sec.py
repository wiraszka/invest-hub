from unittest.mock import patch

import pytest

from services.sec import get_filing_sections, get_xbrl_facts, resolve_cik

MOCK_TICKER_JSON = {
    "0": {"ticker": "NNE", "cik_str": 1898848, "title": "Nano Nuclear Energy Inc."},
    "1": {"ticker": "AAPL", "cik_str": 320193, "title": "Apple Inc."},
}

MOCK_SUBMISSIONS = {
    "filings": {
        "recent": {
            "form": ["10-K", "10-Q", "8-K"],
            "accessionNumber": ["0001234567-25-000001", "0001234567-25-000002", "0001234567-25-000003"],
            "primaryDocument": ["form10k.htm", "form10q.htm", "form8k.htm"],
        }
    }
}

MOCK_10K_HTML = """
<html><body>
<p>Item 1. Business</p>
<p>We develop microreactors for clean energy production.</p>
<p>Item 1A. Risk Factors</p>
<p>We face significant regulatory and funding risks.</p>
<p>Item 2. Properties</p>
<p>We lease office space in New York.</p>
<p>Item 7. Management Discussion and Analysis</p>
<p>We had no revenue in fiscal 2025. Cash burn was $5M.</p>
<p>Item 8. Financial Statements</p>
</body></html>
"""

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


def test_get_filing_sections_extracts_text():
    with patch("services.sec.requests.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.side_effect = [MOCK_TICKER_JSON, MOCK_SUBMISSIONS]
        mock_get.return_value.text = MOCK_10K_HTML

        result = get_filing_sections("NNE")

    assert "microreactors" in result
    assert "regulatory" in result
    assert "Cash burn" in result
    # Item 2 (Properties) should not be included
    assert "office space" not in result


def test_get_filing_sections_raises_when_no_10k():
    submissions_no_10k = {
        "filings": {
            "recent": {
                "form": ["10-Q", "8-K"],
                "accessionNumber": ["0001234567-25-000002", "0001234567-25-000003"],
                "primaryDocument": ["form10q.htm", "form8k.htm"],
            }
        }
    }

    with patch("services.sec.requests.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.side_effect = [MOCK_TICKER_JSON, submissions_no_10k]

        with pytest.raises(ValueError, match="No 10-K found"):
            get_filing_sections("NNE")


def test_get_xbrl_facts_returns_structured_data():
    with patch("services.sec.requests.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.side_effect = [MOCK_TICKER_JSON, MOCK_XBRL_FACTS]

        result = get_xbrl_facts("NNE")

    assert result["cash"] == 10_000_000
    assert result["total_debt"] == 2_000_000
    assert result["net_debt"] == -8_000_000
    assert result["revenue"] == 0


def test_get_xbrl_facts_returns_none_for_missing_concepts():
    with patch("services.sec.requests.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.side_effect = [MOCK_TICKER_JSON, {"facts": {"us-gaap": {}}}]

        result = get_xbrl_facts("NNE")

    assert result["cash"] is None
    assert result["revenue"] is None
    assert result["net_debt"] is None
