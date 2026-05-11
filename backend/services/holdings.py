from __future__ import annotations

import csv
import io

from services.symbols import clean_symbol, is_option, option_details, parse_float


def parse_holdings_csv(content: str) -> list[dict]:
    """Parse a Wealthsimple holdings export CSV into normalized position snapshots."""
    reader = csv.DictReader(io.StringIO(content))
    holdings = []

    for row in reader:
        symbol_raw = (row.get("Symbol") or "").strip()
        account_type = (row.get("Account Type") or "").strip()
        if not symbol_raw or not account_type:
            continue

        book_value_cad = parse_float(row.get("Book Value (CAD)") or "")
        book_value_market = parse_float(row.get("Book Value (Market)") or "")
        market_value_native = parse_float(row.get("Market Value") or "")
        market_value_currency = (row.get("Market Value Currency") or "CAD").strip()
        unrealized_native = parse_float(row.get("Market Unrealized Returns") or "")
        market_price = parse_float(row.get("Market Price") or "")
        market_price_currency = (row.get("Market Price Currency") or "CAD").strip()

        if market_value_currency == "CAD":
            market_value_cad = market_value_native
            unrealized_pl_cad = unrealized_native
        else:
            # Use implied FX rate derived from book values (purchase-time approximation)
            if book_value_market and book_value_cad:
                implied_fx = book_value_cad / book_value_market
            else:
                implied_fx = 1.0
            market_value_cad = (
                market_value_native * implied_fx
                if market_value_native is not None
                else None
            )
            unrealized_pl_cad = (
                market_value_cad - book_value_cad
                if market_value_cad is not None and book_value_cad is not None
                else unrealized_native
            )

        is_opt = is_option(symbol_raw)

        holdings.append(
            {
                "account": account_type,
                "raw_symbol": symbol_raw,
                "symbol": clean_symbol(symbol_raw),
                "name": (row.get("Name") or "").strip(),
                "security_type": (row.get("Security Type") or "EQUITY").strip(),
                "exchange": (row.get("Exchange") or "").strip(),
                "quantity": parse_float(row.get("Quantity") or ""),
                "market_price": market_price,
                "market_price_currency": market_price_currency,
                "book_value_cad": (
                    round(book_value_cad, 2) if book_value_cad is not None else None
                ),
                "market_value_cad": (
                    round(market_value_cad, 2)
                    if market_value_cad is not None
                    else None
                ),
                "unrealized_pl_cad": (
                    round(unrealized_pl_cad, 2)
                    if unrealized_pl_cad is not None
                    else None
                ),
                "is_option": is_opt,
                "option_details": option_details(symbol_raw) if is_opt else None,
            }
        )

    return holdings
