from unittest.mock import MagicMock, patch

import pytest

from services.fmp import get_financials, get_profile_description, get_quote_price


def _mock_response(data: list | dict, ok: bool = True) -> MagicMock:
    mock = MagicMock()
    mock.ok = ok
    mock.json.return_value = data
    return mock


MOCK_PROFILE = [
    {
        "symbol": "NNE",
        "isEtf": False,
        "isFund": False,
        "sector": "Utilities",
        "country": "United States",
        "description": "NuScale Power Corporation designs nuclear reactors.",
    }
]

MOCK_INCOME = [
    {
        "date": "2024-01-31",
        "calendarYear": "2024",
        "reportedCurrency": "USD",
        "revenue": 10_000_000,
        "grossProfit": 4_000_000,
        "operatingIncome": 2_000_000,
        "netIncome": 1_500_000,
        "ebitda": 2_500_000,
    },
    {
        "date": "2023-01-31",
        "calendarYear": "2023",
        "reportedCurrency": "USD",
        "revenue": 8_000_000,
        "grossProfit": 3_200_000,
        "operatingIncome": 1_500_000,
        "netIncome": 1_000_000,
        "ebitda": 2_000_000,
    },
]

MOCK_BALANCE = [
    {
        "date": "2024-01-31",
        "cashAndCashEquivalents": 50_000_000,
        "totalDebt": 20_000_000,
        "netDebt": -30_000_000,
        "totalStockholdersEquity": 200_000_000,
        "totalAssets": 300_000_000,
    }
]

MOCK_CASHFLOW = [
    {
        "date": "2024-01-31",
        "calendarYear": "2024",
        "operatingCashFlow": 5_000_000,
        "capitalExpenditure": -1_000_000,
        "freeCashFlow": 4_000_000,
    }
]

MOCK_METRICS = [
    {
        "date": "2024-01-31",
        "marketCap": 500_000_000,
        "enterpriseValue": 470_000_000,
        "peRatio": 25.0,
        "evToEbitda": 18.8,
        "pbRatio": 2.5,
        "roe": 0.075,
    }
]

MOCK_QUOTE = [{"symbol": "NNE", "price": 42.50}]

_FULL_RESPONSES = [
    _mock_response(MOCK_PROFILE),
    _mock_response(MOCK_INCOME),
    _mock_response(MOCK_BALANCE),
    _mock_response(MOCK_CASHFLOW),
    _mock_response(MOCK_METRICS),
]


# ---------------------------------------------------------------------------
# get_financials
# ---------------------------------------------------------------------------


def test_get_financials_returns_structured_data():
    with patch("services.fmp.requests.get", side_effect=list(_FULL_RESPONSES)):
        result = get_financials("NNE")

    assert result is not None
    assert result["fmp_ticker"] == "NNE"
    assert result["currency"] == "USD"


def test_get_financials_income_parsed_correctly():
    with patch("services.fmp.requests.get", side_effect=list(_FULL_RESPONSES)):
        result = get_financials("NNE")

    assert len(result["income"]) == 2
    assert result["income"][0]["year"] == 2024
    assert result["income"][0]["revenue"] == 10_000_000
    assert result["income"][0]["gross_profit"] == 4_000_000
    assert result["income"][0]["net_income"] == 1_500_000
    assert result["income"][0]["ebitda"] == 2_500_000


def test_get_financials_balance_sheet_parsed_correctly():
    with patch("services.fmp.requests.get", side_effect=list(_FULL_RESPONSES)):
        result = get_financials("NNE")

    bs = result["balance_sheet"]
    assert bs["cash"] == 50_000_000
    assert bs["total_debt"] == 20_000_000
    assert bs["net_debt"] == -30_000_000
    assert bs["total_equity"] == 200_000_000


def test_get_financials_cash_flow_parsed_correctly():
    with patch("services.fmp.requests.get", side_effect=list(_FULL_RESPONSES)):
        result = get_financials("NNE")

    cf = result["cash_flow"][0]
    assert cf["year"] == 2024
    assert cf["operating_cash_flow"] == 5_000_000
    assert cf["capex"] == -1_000_000
    assert cf["free_cash_flow"] == 4_000_000


def test_get_financials_key_metrics_parsed_correctly():
    with patch("services.fmp.requests.get", side_effect=list(_FULL_RESPONSES)):
        result = get_financials("NNE")

    m = result["metrics"]
    assert m["market_cap"] == 500_000_000
    assert m["enterprise_value"] == 470_000_000
    assert m["pe_ratio"] == 25.0
    assert m["ev_ebitda"] == 18.8
    assert m["price_to_book"] == 2.5
    assert m["roe"] == 0.075


def test_get_financials_uses_to_suffix_for_canadian_tickers():
    responses = [
        _mock_response([]),
        _mock_response(MOCK_PROFILE),
        _mock_response(MOCK_INCOME),
        _mock_response(MOCK_BALANCE),
        _mock_response(MOCK_CASHFLOW),
        _mock_response(MOCK_METRICS),
    ]

    with patch("services.fmp.requests.get", side_effect=responses):
        result = get_financials("BNS")

    assert result is not None
    assert result["fmp_ticker"] == "BNS.TO"


def test_get_financials_returns_none_when_ticker_not_found():
    with patch("services.fmp.requests.get", side_effect=[
        _mock_response([]),
        _mock_response([]),
    ]):
        result = get_financials("XXXX")

    assert result is None


def test_get_financials_tolerates_missing_optional_statements():
    responses = [
        _mock_response(MOCK_PROFILE),
        _mock_response(MOCK_INCOME),
        _mock_response([]),
        _mock_response([]),
        _mock_response([]),
    ]

    with patch("services.fmp.requests.get", side_effect=responses):
        result = get_financials("NNE")

    assert result is not None
    assert result["income"][0]["revenue"] == 10_000_000
    assert result["balance_sheet"] == {}
    assert result["cash_flow"] == []
    assert result["metrics"] == {}


def test_get_financials_returns_none_on_request_error():
    with patch("services.fmp.requests.get", side_effect=Exception("Network error")):
        result = get_financials("NNE")

    assert result is None


# ---------------------------------------------------------------------------
# get_profile_description
# ---------------------------------------------------------------------------


def test_get_profile_description_returns_text():
    with patch("services.fmp.requests.get", return_value=_mock_response(MOCK_PROFILE)):
        result = get_profile_description("NNE")

    assert result == "NuScale Power Corporation designs nuclear reactors."


def test_get_profile_description_returns_none_when_not_found():
    with patch("services.fmp.requests.get", side_effect=[
        _mock_response([]),
        _mock_response([]),
    ]):
        result = get_profile_description("XXXX")

    assert result is None


def test_get_profile_description_returns_none_when_description_missing():
    profile_no_desc = [{**MOCK_PROFILE[0], "description": None}]

    with patch("services.fmp.requests.get", return_value=_mock_response(profile_no_desc)):
        result = get_profile_description("NNE")

    assert result is None


# ---------------------------------------------------------------------------
# get_quote_price
# ---------------------------------------------------------------------------


def test_get_quote_price_returns_float():
    with patch("services.fmp.requests.get", return_value=_mock_response(MOCK_QUOTE)):
        result = get_quote_price("NNE")

    assert result == 42.50


def test_get_quote_price_uses_to_suffix_when_first_attempt_empty():
    responses = [
        _mock_response([]),
        _mock_response(MOCK_QUOTE),
    ]

    with patch("services.fmp.requests.get", side_effect=responses):
        result = get_quote_price("BNS")

    assert result == 42.50


def test_get_quote_price_returns_none_when_not_found():
    with patch("services.fmp.requests.get", side_effect=[
        _mock_response([]),
        _mock_response([]),
    ]):
        result = get_quote_price("XXXX")

    assert result is None


def test_get_quote_price_returns_none_on_request_error():
    with patch("services.fmp.requests.get", side_effect=Exception("Network error")):
        result = get_quote_price("NNE")

    assert result is None
