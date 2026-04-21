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


# ---------------------------------------------------------------------------
# Router endpoints
# ---------------------------------------------------------------------------


def test_upload_returns_transaction_count():
    with patch("routers.investments.replace_transactions") as mock_replace:
        response = client.post(
            "/api/investments/upload",
            files={"file": ("activities.csv", MINIMAL_CSV.encode(), "text/csv")},
            headers={"X-User-Id": "user_test123"},
        )

    assert response.status_code == 200
    assert response.json()["count"] > 0
    mock_replace.assert_called_once()


def test_upload_requires_user_id():
    response = client.post(
        "/api/investments/upload",
        files={"file": ("activities.csv", MINIMAL_CSV.encode(), "text/csv")},
    )

    assert response.status_code == 401


def test_get_positions_requires_user_id():
    response = client.get("/api/investments/positions")

    assert response.status_code == 401


def test_get_transactions_requires_user_id():
    response = client.get("/api/investments/transactions")

    assert response.status_code == 401


def test_get_positions_returns_list():
    mock_txns = [
        {
            "transaction_date": "2025-08-13",
            "account_type": "TFSA",
            "activity_type": "Trade",
            "activity_sub_type": "BUY",
            "symbol": "VFV",
            "name": "Vanguard S&P 500 Index ETF",
            "currency": "CAD",
            "quantity": 10.0,
            "unit_price": 100.0,
            "commission": 0.0,
            "net_cash_amount": -1000.0,
        }
    ]

    with patch("routers.investments.get_transactions", return_value=mock_txns):
        response = client.get(
            "/api/investments/positions",
            headers={"X-User-Id": "user_test123"},
        )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["symbol"] == "VFV"


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
