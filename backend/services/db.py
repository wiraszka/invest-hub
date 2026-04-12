from __future__ import annotations

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection

load_dotenv()

_mongo_client: MongoClient | None = None


def _collection() -> Collection:
    global _mongo_client
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise RuntimeError("MONGODB_URI is not set")
    if _mongo_client is None:
        _mongo_client = MongoClient(uri)
    return _mongo_client["invest-hub"]["analyses"]


def get_prompt(company_type: str) -> str | None:
    col = _collection().database["prompts"]
    doc = col.find_one({"type": company_type}, {"_id": 0, "content": 1})
    return doc["content"] if doc else None


def upsert_prompt(company_type: str, content: str) -> None:
    col = _collection().database["prompts"]
    col.update_one(
        {"type": company_type},
        {"$set": {"type": company_type, "content": content}},
        upsert=True,
    )


def upsert_analysis(ticker: str, company_type: str, markdown: str) -> None:
    _collection().update_one(
        {"ticker": ticker},
        {
            "$set": {
                "ticker": ticker,
                "company_type": company_type,
                "markdown": markdown,
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
