from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()

TD_BASE = "https://api.twelvedata.com"


def _api_key() -> str:
    key = os.environ.get("TD_API_KEY", "")
    if not key:
        raise RuntimeError("TD_API_KEY is not set")
    return key


def get_current_price(ticker: str) -> dict:
    """Return current price in USD for the given ticker."""
    response = requests.get(
        f"{TD_BASE}/price",
        params={"symbol": ticker, "apikey": _api_key()},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    if "price" not in data:
        raise ValueError(data.get("message", "Unexpected response from TwelveData"))
    return {"ticker": ticker, "price": float(data["price"])}


def get_price_history(ticker: str, days: int = 365) -> dict:
    """Return daily closing prices for the past `days` days."""
    response = requests.get(
        f"{TD_BASE}/time_series",
        params={
            "symbol": ticker,
            "interval": "1day",
            "outputsize": days,
            "apikey": _api_key(),
        },
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if "values" not in data:
        raise ValueError(data.get("message", "Unexpected response from TwelveData"))

    history = [
        {"date": entry["datetime"], "close": float(entry["close"])}
        for entry in reversed(data["values"])
    ]
    return {"ticker": ticker, "history": history}
