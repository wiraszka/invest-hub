from __future__ import annotations

import requests

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_HEADERS = {"User-Agent": "invest-hub contact@example.com"}

_cache: dict | None = None


def _load_tickers() -> dict:
    global _cache
    if _cache is None:
        response = requests.get(SEC_TICKERS_URL, headers=SEC_HEADERS, timeout=10)
        response.raise_for_status()
        _cache = response.json()
    return _cache


def search_companies(query: str, limit: int = 5) -> list[dict]:
    """
    Search SEC company tickers by ticker symbol or company name.
    Returns up to `limit` results, each with ticker, name, and cik.
    Ticker matches are ranked above name matches.
    """
    if not query or len(query.strip()) < 1:
        return []

    q = query.strip().upper()
    tickers = _load_tickers()

    ticker_matches: list[dict] = []
    name_matches: list[dict] = []

    for entry in tickers.values():
        ticker = entry.get("ticker", "")
        name = entry.get("title", "")
        cik = str(entry.get("cik_str", "")).zfill(10)

        if ticker.upper() == q:
            ticker_matches.append({"ticker": ticker, "name": name, "cik": cik})
        elif ticker.upper().startswith(q):
            ticker_matches.append({"ticker": ticker, "name": name, "cik": cik})
        elif q in name.upper():
            name_matches.append({"ticker": ticker, "name": name, "cik": cik})

    results = ticker_matches + name_matches
    return results[:limit]
