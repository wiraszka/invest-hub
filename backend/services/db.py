from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection

load_dotenv()

_mongo_client: MongoClient | None = None


def _db():
    global _mongo_client
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise RuntimeError("MONGODB_URI is not set")
    if _mongo_client is None:
        _mongo_client = MongoClient(uri)
    return _mongo_client["invest-hub"]


def _collection() -> Collection:
    return _db()["analyses"]


def _trends_collection() -> Collection:
    return _db()["trends_cache"]


def _positions_collection() -> Collection:
    return _db()["positions_cache"]


def _holdings_collection() -> Collection:
    return _db()["holdings_cache"]


# ---------------------------------------------------------------------------
# Analyses
# ---------------------------------------------------------------------------


def upsert_analysis(
    ticker: str,
    company_type: str,
    snapshot: str,
    chart_data: dict,
    xbrl_data: dict,
    market_cap_usd: float | None,
    data_integrity: dict | None = None,
) -> None:
    _collection().update_one(
        {"ticker": ticker},
        {
            "$set": {
                "ticker": ticker,
                "company_type": company_type,
                "market_cap_usd": market_cap_usd,
                "snapshot": snapshot,
                "chart_data": chart_data,
                "xbrl_data": xbrl_data,
                "data_integrity": data_integrity or {},
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


# ---------------------------------------------------------------------------
# Trends cache
# ---------------------------------------------------------------------------


def get_trends_cache(cache_key: str) -> dict | None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
    doc = _trends_collection().find_one(
        {"cache_key": cache_key, "cached_at": {"$gte": cutoff}},
        {"_id": 0},
    )
    return doc["data"] if doc else None


def upsert_trends_cache(cache_key: str, data: dict) -> None:
    _trends_collection().update_one(
        {"cache_key": cache_key},
        {
            "$set": {
                "cache_key": cache_key,
                "data": data,
                "cached_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


def _transactions_collection() -> Collection:
    return _db()["transactions"]


# ---------------------------------------------------------------------------
# Positions cache
# ---------------------------------------------------------------------------


def get_positions_cache(user_id: str) -> list[dict] | None:
    doc = _positions_collection().find_one({"user_id": user_id}, {"_id": 0})
    return doc["positions"] if doc else None


def set_positions_cache(user_id: str, positions: list[dict]) -> None:
    _positions_collection().replace_one(
        {"user_id": user_id},
        {"user_id": user_id, "positions": positions},
        upsert=True,
    )


def invalidate_positions_cache(user_id: str) -> None:
    _positions_collection().delete_one({"user_id": user_id})


# ---------------------------------------------------------------------------
# Holdings cache
# ---------------------------------------------------------------------------


def get_holdings_cache(user_id: str) -> list[dict] | None:
    doc = _holdings_collection().find_one({"user_id": user_id}, {"_id": 0})
    return doc.get("holdings") if doc else None


def set_holdings_cache(user_id: str, holdings: list[dict]) -> None:
    _holdings_collection().replace_one(
        {"user_id": user_id},
        {"user_id": user_id, "holdings": holdings},
        upsert=True,
    )


def invalidate_holdings_cache(user_id: str) -> None:
    _holdings_collection().delete_one({"user_id": user_id})


# ---------------------------------------------------------------------------
# User preferences
# ---------------------------------------------------------------------------


def _preferences_collection() -> Collection:
    return _db()["user_preferences"]


_DEFAULT_PREFERENCES: dict = {
    "grouping_labels": [],
    "grouping_assignments": {},
    "sector_overrides": {},
}


def get_user_preferences(user_id: str) -> dict:
    doc = _preferences_collection().find_one(
        {"user_id": user_id}, {"_id": 0, "user_id": 0}
    )
    return doc if doc else dict(_DEFAULT_PREFERENCES)


def upsert_user_preferences(user_id: str, prefs: dict) -> None:
    _preferences_collection().replace_one(
        {"user_id": user_id},
        {"user_id": user_id, **prefs},
        upsert=True,
    )


def _symbol_metadata_collection() -> Collection:
    return _db()["symbol_metadata"]


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


def replace_transactions(user_id: str, transactions: list[dict]) -> None:
    col = _transactions_collection()
    col.delete_many({"user_id": user_id})
    if transactions:
        col.insert_many([{"user_id": user_id, **t} for t in transactions])


def get_transactions(user_id: str) -> list[dict]:
    return list(
        _transactions_collection()
        .find(
            {"user_id": user_id},
            {"_id": 0, "user_id": 0},
        )
        .sort("transaction_date", -1)
    )



# ---------------------------------------------------------------------------
# Symbol metadata
# ---------------------------------------------------------------------------

_METADATA_TTL_DAYS = 30


def get_symbol_metadata(ticker: str) -> dict | None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=_METADATA_TTL_DAYS)
    doc = _symbol_metadata_collection().find_one(
        {"ticker": ticker, "fetched_at": {"$gte": cutoff}},
        {"_id": 0},
    )
    if doc and "fetched_at" in doc:
        doc["fetched_at"] = doc["fetched_at"].isoformat()
    return doc


def upsert_symbol_metadata(ticker: str, data: dict) -> None:
    _symbol_metadata_collection().update_one(
        {"ticker": ticker},
        {"$set": {"ticker": ticker, **data, "fetched_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


def get_symbol_metadata_batch(tickers: list[str]) -> dict[str, dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=_METADATA_TTL_DAYS)
    docs = _symbol_metadata_collection().find(
        {"ticker": {"$in": tickers}, "fetched_at": {"$gte": cutoff}},
        {"_id": 0},
    )
    result: dict[str, dict] = {}
    for doc in docs:
        if "fetched_at" in doc:
            doc["fetched_at"] = doc["fetched_at"].isoformat()
        result[doc["ticker"]] = doc
    return result


def get_analysis(ticker: str) -> dict | None:
    doc = _collection().find_one({"ticker": ticker}, {"_id": 0})
    if doc and "updated_at" in doc:
        doc["updated_at"] = doc["updated_at"].isoformat()
    return doc
