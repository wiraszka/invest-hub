from unittest.mock import patch

from fastapi.testclient import TestClient

from api.index import app
from services.investments import build_positions, parse_csv

client = TestClient(app)

# ---------------------------------------------------------------------------
# CSV fixtures
# ---------------------------------------------------------------------------

MINIMAL_CSV = """\
transaction_date,settlement_date,account_id,account_type,activity_type,activity_sub_type,direction,symbol,name,currency,quantity,unit_price,commission,net_cash_amount
2025-08-13,2025-08-13,HQ8GXMMK0CAD,TFSA,Trade,BUY,LONG,VFV,Vanguard S&P 500 Index ETF,CAD,10,100.00,0,-1000.00
2025-09-01,2025-09-01,HQ8GXMMK0CAD,TFSA,Trade,SELL,LONG,VFV,Vanguard S&P 500 Index ETF,CAD,-3,110.00,0,330.00
2025-08-16,,HQ8GXMMK0CAD,TFSA,MoneyMovement,EFT,,,,CAD,5000,,,5000
2025-09-15,,HQ8GXMMK0CAD,TFSA,Interest,,,,,CAD,0.05,,,0.05
2025-09-26,,HQ8GXMMK0CAD,TFSA,Dividend,,,,,CAD,10.00,,,10.00
2025-09-26,,HQ8GXMMK0CAD,TFSA,CorporateAction,CONSOLIDATION,LONG,OLD,Old Corp,,-100,,,
2025-09-26,,HQ8GXMMK0CAD,TFSA,CorporateAction,CONSOLIDATION,LONG,OLD,Old Corp,,10,,,
"As of 2026-04-21 00:50 GMT-04:00"
"""

CORPORATE_ACTION_CSV = """\
transaction_date,settlement_date,account_id,account_type,activity_type,activity_sub_type,direction,symbol,name,currency,quantity,unit_price,commission,net_cash_amount
2025-08-01,2025-08-01,HQ8GXMMK0CAD,TFSA,Trade,BUY,LONG,ELE,Elemental Corp,CAD,300,2.31,0,-693.00
2025-09-16,,HQ8GXMMK0CAD,TFSA,CorporateAction,CONSOLIDATION,LONG,ELE,Elemental Corp,,-300,,,
2025-09-16,,HQ8GXMMK0CAD,TFSA,CorporateAction,CONSOLIDATION,LONG,ELE,Elemental Corp,,30,,,
"""

OPTION_CSV = """\
transaction_date,settlement_date,account_id,account_type,activity_type,activity_sub_type,direction,symbol,name,currency,quantity,unit_price,commission,net_cash_amount
2026-01-10,2026-01-10,HQ8GXMMK0CAD,TFSA,Trade,BUY,LONG,QQQ   260930P00460000,,USD,1,2.50,0,-250.00
"""

HOLDINGS_CSV = """\
Account Name,Account Type,Account Classification,Account Number,Symbol,Exchange,MIC,Name,Security Type,Quantity,Position Direction,Market Price,Market Price Currency,Book Value (CAD),Book Value Currency (CAD),Book Value (Market),Book Value Currency (Market),Market Value,Market Value Currency,Market Unrealized Returns,Market Unrealized Returns Currency
"TFSA","TFSA","Trade","HQ8GXMMK0CAD","VFV","TSX","XTSE","Vanguard S&P 500 Index ETF","EXCHANGE_TRADED_FUND","7","LONG","105.00","CAD","700.00","CAD","700.00","CAD","735.00","CAD","35.00","CAD"
"TFSA","TFSA","Trade","HQ8GXMMK0CAD","QQQ   260930P00460000","NASDAQ","XNAS","","OPTION","1","LONG","2.25","USD","490.97","CAD","352.00","USD","225.00","USD","-127.00","USD"

"As of 2026-05-11 10:11 GMT-04:00"
"""


# ---------------------------------------------------------------------------
# parse_csv
# ---------------------------------------------------------------------------


def test_parse_csv_returns_trades():
    result = parse_csv(MINIMAL_CSV)

    trade_types = [r["activity_type"] for r in result]
    assert "Trade" in trade_types


def test_parse_csv_skips_money_movements():
    result = parse_csv(MINIMAL_CSV)

    assert not any(r["activity_type"] == "MoneyMovement" for r in result)


def test_parse_csv_skips_interest():
    result = parse_csv(MINIMAL_CSV)

    assert not any(r["activity_type"] == "Interest" for r in result)


def test_parse_csv_skips_trailing_as_of_line():
    result = parse_csv(MINIMAL_CSV)

    assert all(r["transaction_date"] for r in result)


def test_parse_csv_strips_account_id():
    result = parse_csv(MINIMAL_CSV)

    assert not any("account_id" in r for r in result)


def test_parse_csv_includes_dividend():
    result = parse_csv(MINIMAL_CSV)

    assert any(r["activity_type"] == "Dividend" for r in result)


def test_parse_csv_cleans_option_symbol():
    result = parse_csv(OPTION_CSV)

    trade = next(r for r in result if r["activity_type"] == "Trade")
    assert trade["symbol"] == "QQQ"
    assert trade["raw_symbol"] == "QQQ   260930P00460000"


# ---------------------------------------------------------------------------
# build_positions
# ---------------------------------------------------------------------------


def test_build_positions_buy_creates_position():
    txns = parse_csv(MINIMAL_CSV)

    positions = build_positions(txns)

    vfv = next(p for p in positions if p["symbol"] == "VFV")
    assert vfv["shares_held"] == 7.0  # 10 bought - 3 sold
    assert vfv["account"] == "TFSA"


def test_build_positions_cost_basis_after_partial_sell():
    txns = parse_csv(MINIMAL_CSV)

    positions = build_positions(txns)

    vfv = next(p for p in positions if p["symbol"] == "VFV")
    # bought 10 @ $100 = $1000 cost basis; sold 3 → cost basis = $700
    assert abs(vfv["cost_basis"] - 700.0) < 0.01


def test_build_positions_realized_pl_on_sell():
    txns = parse_csv(MINIMAL_CSV)

    positions = build_positions(txns)

    vfv = next(p for p in positions if p["symbol"] == "VFV")
    # sold 3 shares: proceeds $330 - cost $300 = $30 realized P/L
    assert abs(vfv["realized_pl"] - 30.0) < 0.01


def test_build_positions_full_sell_excludes_position():
    csv = """\
transaction_date,settlement_date,account_id,account_type,activity_type,activity_sub_type,direction,symbol,name,currency,quantity,unit_price,commission,net_cash_amount
2025-08-01,2025-08-01,HQ8GXMMK0CAD,TFSA,Trade,BUY,LONG,AAA,Alpha Corp,CAD,10,50.00,0,-500.00
2025-08-15,2025-08-15,HQ8GXMMK0CAD,TFSA,Trade,SELL,LONG,AAA,Alpha Corp,CAD,-10,55.00,0,550.00
"""

    txns = parse_csv(csv)
    positions = build_positions(txns)

    assert not any(p["symbol"] == "AAA" for p in positions)


def test_build_positions_corporate_action_consolidation():
    txns = parse_csv(CORPORATE_ACTION_CSV)

    positions = build_positions(txns)

    ele = next(p for p in positions if p["symbol"] == "ELE")
    assert ele["shares_held"] == 30.0


def test_build_positions_avg_cost_per_share():
    txns = parse_csv(MINIMAL_CSV)

    positions = build_positions(txns)

    vfv = next(p for p in positions if p["symbol"] == "VFV")
    expected_avg = vfv["cost_basis"] / vfv["shares_held"]
    assert abs(vfv["avg_cost_per_share"] - expected_avg) < 0.0001


def test_build_positions_cleans_option_symbol():
    txns = parse_csv(OPTION_CSV)

    positions = build_positions(txns)

    opt = next(p for p in positions if p["is_option"])
    assert opt["symbol"] == "QQQ"
    assert opt["raw_symbol"] == "QQQ   260930P00460000"
    assert opt["asset_type"] == "Option"
    assert "Put" in opt["option_details"]
    assert "$460" in opt["option_details"]


# ---------------------------------------------------------------------------
# Router endpoints
# ---------------------------------------------------------------------------


def test_upload_activities_returns_count_and_type():
    with (
        patch("routers.investments.replace_transactions_for_source") as mock_replace,
        patch("routers.investments.invalidate_positions_cache"),
    ):
        response = client.post(
            "/api/investments/upload",
            files={"file": ("activities.csv", MINIMAL_CSV.encode(), "text/csv")},
            headers={"X-User-Id": "user_test123"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "activities"
    assert data["count"] > 0
    mock_replace.assert_called_once()


def test_upload_activities_tags_source_as_wealthsimple():
    with (
        patch("routers.investments.replace_transactions_for_source") as mock_replace,
        patch("routers.investments.invalidate_positions_cache"),
    ):
        client.post(
            "/api/investments/upload",
            files={"file": ("activities.csv", MINIMAL_CSV.encode(), "text/csv")},
            headers={"X-User-Id": "user_test123"},
        )

    _, call_kwargs = mock_replace.call_args
    # Third positional arg is source (user_id, source, min_date, max_date, transactions)
    call_args = mock_replace.call_args[0]
    assert call_args[1] == "wealthsimple"


def test_upload_holdings_returns_count_and_type():
    with patch("routers.investments.set_holdings_cache") as mock_set:
        response = client.post(
            "/api/investments/upload",
            files={"file": ("holdings.csv", HOLDINGS_CSV.encode(), "text/csv")},
            headers={"X-User-Id": "user_test123"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "holdings"
    assert data["count"] > 0
    mock_set.assert_called_once()


def test_upload_requires_user_id():
    response = client.post(
        "/api/investments/upload",
        files={"file": ("activities.csv", MINIMAL_CSV.encode(), "text/csv")},
    )

    assert response.status_code == 401


def test_get_positions_requires_user_id():
    response = client.get("/api/investments/positions")

    assert response.status_code == 401


def test_get_sources_requires_user_id():
    response = client.get("/api/investments/sources")

    assert response.status_code == 401


def test_get_sources_returns_list():
    mock_sources = [
        {"source": "wealthsimple", "count": 45, "min_date": "2024-01-15", "max_date": "2025-03-26"}
    ]

    with patch("routers.investments.get_transaction_sources", return_value=mock_sources):
        response = client.get(
            "/api/investments/sources",
            headers={"X-User-Id": "user_test123"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data[0]["source"] == "wealthsimple"
    assert data[0]["count"] == 45


def test_delete_source_requires_user_id():
    response = client.delete("/api/investments/sources/wealthsimple")

    assert response.status_code == 401


def test_delete_source_clears_and_invalidates():
    with (
        patch("routers.investments.clear_transactions_for_source") as mock_clear,
        patch("routers.investments.invalidate_positions_cache"),
    ):
        response = client.delete(
            "/api/investments/sources/wealthsimple",
            headers={"X-User-Id": "user_test123"},
        )

    assert response.status_code == 200
    mock_clear.assert_called_once_with("user_test123", "wealthsimple")


def test_delete_legacy_source_passes_none():
    with (
        patch("routers.investments.clear_transactions_for_source") as mock_clear,
        patch("routers.investments.invalidate_positions_cache"),
    ):
        client.delete(
            "/api/investments/sources/legacy",
            headers={"X-User-Id": "user_test123"},
        )

    mock_clear.assert_called_once_with("user_test123", None)


def test_get_transactions_requires_user_id():
    response = client.get("/api/investments/transactions")

    assert response.status_code == 401


def test_get_holdings_requires_user_id():
    response = client.get("/api/investments/holdings")

    assert response.status_code == 401


def test_get_holdings_returns_list():
    mock_holdings = [{"account": "TFSA", "symbol": "VFV", "market_value_cad": 735.0}]

    with patch("routers.investments.get_holdings_cache", return_value=mock_holdings):
        response = client.get(
            "/api/investments/holdings",
            headers={"X-User-Id": "user_test123"},
        )

    assert response.status_code == 200
    assert response.json()[0]["symbol"] == "VFV"


def test_get_holdings_returns_empty_list_when_none():
    with patch("routers.investments.get_holdings_cache", return_value=None):
        response = client.get(
            "/api/investments/holdings",
            headers={"X-User-Id": "user_test123"},
        )

    assert response.status_code == 200
    assert response.json() == []


def test_get_positions_returns_list():
    mock_txns = [
        {
            "transaction_date": "2025-08-13",
            "account_type": "TFSA",
            "activity_type": "Trade",
            "activity_sub_type": "BUY",
            "symbol": "VFV",
            "raw_symbol": "VFV",
            "name": "Vanguard S&P 500 Index ETF",
            "currency": "CAD",
            "quantity": 10.0,
            "unit_price": 100.0,
            "commission": 0.0,
            "net_cash_amount": -1000.0,
        }
    ]

    with (
        patch("routers.investments.get_positions_cache", return_value=None),
        patch("routers.investments.get_transactions", return_value=mock_txns),
        patch("routers.investments.set_positions_cache"),
    ):
        response = client.get(
            "/api/investments/positions",
            headers={"X-User-Id": "user_test123"},
        )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["symbol"] == "VFV"


def test_metadata_falls_back_to_sec_when_fmp_returns_none():
    sec_meta = {
        "asset_type": "Equity",
        "sector": "Crude Petroleum and Natural Gas",
        "country": "Canada",
        "sector_weights": None,
        "country_weights": None,
    }

    with (
        patch("routers.investments.get_symbol_metadata", return_value=None),
        patch("routers.investments.fetch_from_fmp", return_value=None),
        patch("routers.investments.fetch_from_sec", return_value=sec_meta),
        patch("routers.investments.upsert_symbol_metadata"),
        patch("routers.investments.get_analysis", return_value=None),
    ):
        response = client.post("/api/investments/metadata/AVN")

    assert response.status_code == 200
    data = response.json()
    assert data["sector"] == "Crude Petroleum and Natural Gas"
    assert data["country"] == "Canada"


def test_metadata_returns_404_when_both_fmp_and_sec_fail():
    with (
        patch("routers.investments.get_symbol_metadata", return_value=None),
        patch("routers.investments.fetch_from_fmp", return_value=None),
        patch("routers.investments.fetch_from_sec", return_value=None),
    ):
        response = client.post("/api/investments/metadata/ZZZZ")

    assert response.status_code == 404


def test_get_transactions_returns_list():
    mock_txns = [
        {
            "transaction_date": "2025-09-01",
            "account_type": "TFSA",
            "activity_type": "Trade",
            "activity_sub_type": "SELL",
            "symbol": "VFV",
            "name": "Vanguard S&P 500 Index ETF",
            "currency": "CAD",
            "quantity": -3.0,
            "unit_price": 110.0,
            "commission": 0.0,
            "net_cash_amount": 330.0,
        }
    ]

    with patch("routers.investments.get_transactions", return_value=mock_txns):
        response = client.get(
            "/api/investments/transactions",
            headers={"X-User-Id": "user_test123"},
        )

    assert response.status_code == 200
    assert response.json()[0]["symbol"] == "VFV"


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------


def test_get_preferences_requires_user_id():
    response = client.get("/api/investments/preferences")

    assert response.status_code == 401


def test_get_preferences_returns_defaults_when_none_stored():
    with patch(
        "routers.investments.get_user_preferences",
        return_value={
            "grouping_labels": [],
            "grouping_assignments": {},
            "sector_overrides": {},
        },
    ):
        response = client.get(
            "/api/investments/preferences",
            headers={"X-User-Id": "user_test123"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["grouping_labels"] == []
    assert data["grouping_assignments"] == {}
    assert data["sector_overrides"] == {}


def test_put_preferences_requires_user_id():
    response = client.put(
        "/api/investments/preferences",
        json={"grouping_labels": ["Tech"]},
    )

    assert response.status_code == 401


def test_put_preferences_persists_and_returns_prefs():
    prefs = {
        "grouping_labels": ["Tech", "Mining"],
        "grouping_assignments": {"TFSA::VFV": "Tech"},
        "sector_overrides": {"TFSA::ARX": "Oil & Gas"},
    }

    with patch("routers.investments.upsert_user_preferences") as mock_upsert:
        response = client.put(
            "/api/investments/preferences",
            json=prefs,
            headers={"X-User-Id": "user_test123"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["grouping_labels"] == ["Tech", "Mining"]
    assert data["grouping_assignments"] == {"TFSA::VFV": "Tech"}
    assert data["sector_overrides"] == {"TFSA::ARX": "Oil & Gas"}
    mock_upsert.assert_called_once()


def test_put_preferences_strips_unknown_keys():
    with patch("routers.investments.upsert_user_preferences"):
        response = client.put(
            "/api/investments/preferences",
            json={"grouping_labels": ["Tech"], "malicious_key": "bad"},
            headers={"X-User-Id": "user_test123"},
        )

    assert response.status_code == 200
    assert "malicious_key" not in response.json()
