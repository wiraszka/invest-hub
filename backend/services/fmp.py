from __future__ import annotations

import os

import requests

_BASE = "https://financialmodelingprep.com/api/v3"


def _api_key() -> str:
    key = os.environ.get("FMP_API_KEY", "")
    if not key:
        raise RuntimeError("FMP_API_KEY is not set")
    return key


def _get(path: str) -> list | dict | None:
    try:
        res = requests.get(
            f"{_BASE}{path}",
            params={"apikey": _api_key()},
            timeout=10,
        )
        if not res.ok:
            return None
        data = res.json()
        return data if data else None
    except Exception:
        return None


def _parse_weight(raw: str | float | None) -> float:
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    return float(str(raw).rstrip("%").strip() or 0)


def _resolve_ticker(symbol: str) -> tuple[str, list | None]:
    """Try symbol as-is, then with .TO suffix for Canadian listings."""
    for candidate in [symbol, f"{symbol}.TO"]:
        data = _get(f"/profile/{candidate}")
        if data and isinstance(data, list) and len(data) > 0:
            return candidate, data
    return symbol, None


def _etf_sector_weights(fmp_ticker: str) -> list[dict] | None:
    data = _get(f"/etf-sector-weightings/{fmp_ticker}")
    if not data or not isinstance(data, list):
        return None
    result = []
    for item in data:
        sector = item.get("sector")
        weight = _parse_weight(item.get("weightPercentage"))
        if sector and weight > 0:
            result.append({"sector": sector, "weight": weight})
    return result or None


def _etf_country_weights(fmp_ticker: str) -> list[dict] | None:
    data = _get(f"/etf-country-weightings/{fmp_ticker}")
    if not data or not isinstance(data, list):
        return None
    result = []
    for item in data:
        country = item.get("country")
        weight = _parse_weight(item.get("weightPercentage"))
        if country and weight > 0:
            result.append({"country": country, "weight": weight})
    return result or None


def get_financials(symbol: str) -> dict | None:
    """
    Fetch structured financial data for a stock from FMP.
    Returns income statement (3yr), balance sheet (latest), cash flow (3yr),
    and key metrics (latest). Returns None if symbol cannot be resolved.
    """
    fmp_ticker, profile_data = _resolve_ticker(symbol)
    if not profile_data:
        return None

    income_raw = _get(f"/income-statement/{fmp_ticker}?limit=3")
    if not income_raw or not isinstance(income_raw, list):
        return None

    currency = income_raw[0].get("reportedCurrency", "USD")

    income = []
    for entry in income_raw:
        year_raw = entry.get("calendarYear") or entry.get("date", "")[:4]
        income.append({
            "year": int(year_raw) if year_raw else None,
            "revenue": entry.get("revenue"),
            "gross_profit": entry.get("grossProfit"),
            "operating_income": entry.get("operatingIncome"),
            "net_income": entry.get("netIncome"),
            "ebitda": entry.get("ebitda"),
        })

    balance: dict = {}
    balance_raw = _get(f"/balance-sheet-statement/{fmp_ticker}?limit=1")
    if balance_raw and isinstance(balance_raw, list) and len(balance_raw) > 0:
        b = balance_raw[0]
        balance = {
            "cash": b.get("cashAndCashEquivalents"),
            "total_debt": b.get("totalDebt"),
            "net_debt": b.get("netDebt"),
            "total_equity": b.get("totalStockholdersEquity"),
            "total_assets": b.get("totalAssets"),
        }

    cash_flow: list = []
    cashflow_raw = _get(f"/cash-flow-statement/{fmp_ticker}?limit=3")
    if cashflow_raw and isinstance(cashflow_raw, list):
        for entry in cashflow_raw:
            year_raw = entry.get("calendarYear") or entry.get("date", "")[:4]
            cash_flow.append({
                "year": int(year_raw) if year_raw else None,
                "operating_cash_flow": entry.get("operatingCashFlow"),
                "capex": entry.get("capitalExpenditure"),
                "free_cash_flow": entry.get("freeCashFlow"),
            })

    metrics: dict = {}
    metrics_raw = _get(f"/key-metrics/{fmp_ticker}?limit=1")
    if metrics_raw and isinstance(metrics_raw, list) and len(metrics_raw) > 0:
        m = metrics_raw[0]
        metrics = {
            "market_cap": m.get("marketCap"),
            "enterprise_value": m.get("enterpriseValue"),
            "pe_ratio": m.get("peRatio"),
            "ev_ebitda": m.get("evToEbitda"),
            "price_to_book": m.get("pbRatio"),
            "roe": m.get("roe"),
        }

    return {
        "fmp_ticker": fmp_ticker,
        "currency": currency,
        "income": income,
        "balance_sheet": balance,
        "cash_flow": cash_flow,
        "metrics": metrics,
    }


def get_profile_description(symbol: str) -> str | None:
    """Return FMP company description — used as thin narrative fallback when no SEC filing exists."""
    fmp_ticker, profile_data = _resolve_ticker(symbol)
    if not profile_data:
        return None
    return profile_data[0].get("description") or None


def get_quote_price(symbol: str) -> float | None:
    """Return current price from FMP quote endpoint. Used as TwelveData failover."""
    for candidate in [symbol, f"{symbol}.TO"]:
        data = _get(f"/quote/{candidate}")
        if data and isinstance(data, list) and len(data) > 0:
            price = data[0].get("price")
            if price is not None:
                return float(price)
    return None


def get_symbol_metadata(symbol: str) -> dict | None:
    """
    Fetch sector/country metadata for a stock or ETF from FMP.
    Returns None if the symbol cannot be resolved.
    """
    fmp_ticker, profile_data = _resolve_ticker(symbol)
    if not profile_data:
        return None

    profile = profile_data[0]
    is_etf = bool(profile.get("isEtf")) or bool(profile.get("isFund"))

    if is_etf:
        return {
            "fmp_ticker": fmp_ticker,
            "asset_type": "ETF",
            "sector": None,
            "country": None,
            "sector_weights": _etf_sector_weights(fmp_ticker),
            "country_weights": _etf_country_weights(fmp_ticker),
        }

    return {
        "fmp_ticker": fmp_ticker,
        "asset_type": "Equity",
        "sector": profile.get("sector") or None,
        "country": profile.get("country") or None,
        "sector_weights": None,
        "country_weights": None,
    }
