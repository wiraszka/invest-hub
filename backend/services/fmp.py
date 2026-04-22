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
