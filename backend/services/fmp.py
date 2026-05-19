from __future__ import annotations

import os

import requests

_BASE = "https://financialmodelingprep.com/stable"


def _api_key() -> str:
    key = os.environ.get("FMP_API_KEY", "")
    if not key:
        raise RuntimeError("FMP_API_KEY is not set")
    return key


def _get(path: str, **params) -> list | dict | None:
    try:
        res = requests.get(
            f"{_BASE}{path}",
            params={"apikey": _api_key(), **params},
            timeout=10,
        )
        if not res.ok:
            return None
        data = res.json()
        return data if data else None
    except Exception:
        return None



def _resolve_ticker(symbol: str) -> tuple[str, list | None]:
    """Try symbol as-is; if it ends with .TO also try without the suffix (US cross-listing)."""
    data = _get("/profile", symbol=symbol)
    if data and isinstance(data, list) and len(data) > 0:
        return symbol, data
    if symbol.endswith(".TO"):
        base = symbol[:-3]
        data = _get("/profile", symbol=base)
        if data and isinstance(data, list) and len(data) > 0:
            return base, data
    return symbol, None



def get_financials(symbol: str) -> dict | None:
    """
    Fetch structured financial data for a stock from FMP.
    Returns income statement (3yr), balance sheet (latest), cash flow (3yr),
    and key metrics (latest). Returns None if symbol cannot be resolved.
    """
    fmp_ticker, profile_data = _resolve_ticker(symbol)
    if not profile_data:
        return None

    income_raw = _get("/income-statement", symbol=fmp_ticker, limit=3)
    if not income_raw or not isinstance(income_raw, list):
        return None

    currency = income_raw[0].get("reportedCurrency", "USD")

    income = []
    for entry in income_raw:
        year_raw = entry.get("fiscalYear") or entry.get("date", "")[:4]
        income.append({
            "year": int(year_raw) if year_raw else None,
            "revenue": entry.get("revenue"),
            "gross_profit": entry.get("grossProfit"),
            "operating_income": entry.get("operatingIncome"),
            "net_income": entry.get("netIncome"),
            "ebitda": entry.get("ebitda"),
        })

    balance: dict = {}
    balance_raw = _get("/balance-sheet-statement", symbol=fmp_ticker, limit=1)
    if balance_raw and isinstance(balance_raw, list) and len(balance_raw) > 0:
        latest_balance = balance_raw[0]
        balance = {
            "cash": latest_balance.get("cashAndCashEquivalents"),
            "total_debt": latest_balance.get("totalDebt"),
            "net_debt": latest_balance.get("netDebt"),
            "total_equity": latest_balance.get("totalStockholdersEquity"),
            "total_assets": latest_balance.get("totalAssets"),
        }

    cash_flow: list = []
    cashflow_raw = _get("/cash-flow-statement", symbol=fmp_ticker, limit=3)
    if cashflow_raw and isinstance(cashflow_raw, list):
        for entry in cashflow_raw:
            year_raw = entry.get("fiscalYear") or entry.get("date", "")[:4]
            cash_flow.append({
                "year": int(year_raw) if year_raw else None,
                "operating_cash_flow": entry.get("operatingCashFlow"),
                "capex": entry.get("capitalExpenditure"),
                "free_cash_flow": entry.get("freeCashFlow"),
            })

    metrics: dict = {}
    metrics_raw = _get("/key-metrics", symbol=fmp_ticker, limit=1)
    if metrics_raw and isinstance(metrics_raw, list) and len(metrics_raw) > 0:
        latest_metrics = metrics_raw[0]
        metrics = {
            "market_cap": latest_metrics.get("marketCap"),
            "enterprise_value": latest_metrics.get("enterpriseValue"),
            "ev_ebitda": latest_metrics.get("evToEBITDA"),
            "roe": latest_metrics.get("returnOnEquity"),
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
    for candidate in [symbol, symbol[:-3] if symbol.endswith(".TO") else f"{symbol}.TO"]:
        data = _get("/quote", symbol=candidate)
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
            "sector_weights": None,
            "country_weights": None,
        }

    return {
        "fmp_ticker": fmp_ticker,
        "asset_type": "Equity",
        "sector": profile.get("sector") or None,
        "country": profile.get("country") or None,
        "sector_weights": None,
        "country_weights": None,
    }
