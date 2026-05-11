from __future__ import annotations

import csv
import io

from services.symbols import clean_symbol, is_option, option_details, parse_float

_SKIP_ACTIVITY_TYPES = {"MoneyMovement", "Interest"}


def _infer_asset_type(name: str | None) -> str:
    if not name:
        return "Equity"
    name_lower = name.lower()
    if "etf" in name_lower:
        return "ETF"
    if "trust" in name_lower:
        return "Trust"
    if "fund" in name_lower:
        return "Fund"
    return "Equity"


def parse_csv(content: str) -> list[dict]:
    """Parse a Wealthsimple activities export CSV into normalized transaction records.

    Strips account_id to avoid persisting sensitive identifiers.
    Skips MoneyMovement and Interest rows, and the trailing 'As of...' line.
    """
    reader = csv.DictReader(io.StringIO(content))
    transactions = []

    for row in reader:
        transaction_date = (row.get("transaction_date") or "").strip()
        # Skip blank rows and the trailing "As of..." footer line
        if not transaction_date or not transaction_date[:4].isdigit():
            continue

        activity_type = (row.get("activity_type") or "").strip()
        if activity_type in _SKIP_ACTIVITY_TYPES:
            continue

        symbol_raw = (row.get("symbol") or "").strip() or None

        transactions.append(
            {
                "transaction_date": transaction_date,
                "account_type": (row.get("account_type") or "").strip(),
                "activity_type": activity_type,
                "activity_sub_type": (row.get("activity_sub_type") or "").strip(),
                "symbol": clean_symbol(symbol_raw) if symbol_raw else None,
                "raw_symbol": symbol_raw,
                "name": (row.get("name") or "").strip() or None,
                "currency": (row.get("currency") or "CAD").strip(),
                "quantity": parse_float(row.get("quantity") or ""),
                "unit_price": parse_float(row.get("unit_price") or ""),
                "commission": parse_float(row.get("commission") or "") or 0.0,
                "net_cash_amount": parse_float(row.get("net_cash_amount") or ""),
            }
        )

    return transactions


def build_positions(transactions: list[dict]) -> list[dict]:
    """Aggregate transaction history into current open positions.

    Handles Trade (BUY/SELL) and CorporateAction rows; skips Dividend rows
    (no symbol in the activities export format).
    """
    sorted_txns = sorted(transactions, key=lambda t: t["transaction_date"])

    positions: dict[tuple[str, str], dict] = {}

    for t in sorted_txns:
        symbol = t.get("symbol")
        if not symbol:
            continue

        # Use raw_symbol as the uniqueness key so option contracts remain distinct
        raw_symbol = t.get("raw_symbol") or symbol
        activity_type = t["activity_type"]
        sub_type = t.get("activity_sub_type", "")
        account_type = t["account_type"]
        quantity = t.get("quantity") or 0.0
        net_cash = t.get("net_cash_amount") or 0.0

        key = (account_type, raw_symbol)
        if key not in positions:
            is_opt = is_option(raw_symbol)
            positions[key] = {
                "account": account_type,
                "symbol": symbol,
                "raw_symbol": raw_symbol,
                "name": t.get("name") or symbol,
                "asset_type": "Option" if is_opt else _infer_asset_type(t.get("name")),
                "currency": t.get("currency", "CAD"),
                "shares_held": 0.0,
                "cost_basis": 0.0,
                "realized_pl": 0.0,
                "dividends": 0.0,
                "is_option": is_opt,
                "option_details": option_details(raw_symbol) if is_opt else None,
            }

        pos = positions[key]

        if activity_type == "Trade":
            if sub_type == "BUY":
                pos["shares_held"] += quantity
                pos["cost_basis"] += abs(net_cash)
            elif sub_type == "SELL":
                shares_sold = abs(quantity)
                current_shares = pos["shares_held"]
                avg_cost = pos["cost_basis"] / current_shares if current_shares > 0 else 0.0
                cost_removed = avg_cost * shares_sold
                pos["shares_held"] -= shares_sold
                pos["cost_basis"] -= cost_removed
                pos["realized_pl"] += abs(net_cash) - cost_removed

        elif activity_type == "CorporateAction":
            if quantity > 0:
                pos["shares_held"] += quantity
            elif quantity < 0:
                shares_removed = abs(quantity)
                current_shares = pos["shares_held"]
                if current_shares > 0:
                    avg_cost = pos["cost_basis"] / current_shares
                    pos["cost_basis"] -= avg_cost * shares_removed
                pos["shares_held"] -= shares_removed

        elif activity_type == "Dividend":
            pos["dividends"] += net_cash

    result = []
    for pos in positions.values():
        shares = pos["shares_held"]
        cost_basis = pos["cost_basis"]

        if abs(shares) < 1e-10:
            shares = 0.0
        if abs(cost_basis) < 1e-10:
            cost_basis = 0.0

        if shares <= 1e-10:
            continue

        pos["shares_held"] = round(shares, 6)
        pos["cost_basis"] = round(cost_basis, 2)
        pos["avg_cost_per_share"] = round(cost_basis / shares, 4) if shares > 0 else 0.0
        pos["realized_pl"] = round(pos["realized_pl"], 2)
        pos["dividends"] = round(pos["dividends"], 2)
        result.append(pos)

    result.sort(key=lambda p: (p["account"], p["symbol"]))
    return result
