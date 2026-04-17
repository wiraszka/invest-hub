from __future__ import annotations

import os
from datetime import datetime, timezone

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


def get_analysis(ticker: str) -> dict | None:
    doc = _collection().find_one({"ticker": ticker}, {"_id": 0})
    if doc and "updated_at" in doc:
        doc["updated_at"] = doc["updated_at"].isoformat()
    return doc
