from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.pg import _get_engine
from db.pg_models import Holding, Transaction, TrendsCache, UserPreferences


def _float(v: Any) -> float | None:
    return float(v) if v is not None else None


def _str_date(v: Any) -> str | None:
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _session() -> AsyncSession:
    factory = async_sessionmaker(_get_engine(), expire_on_commit=False, class_=AsyncSession)
    return factory()


def _row_to_dict(row: Transaction) -> dict:
    return {
        "source": row.source,
        "account_type": row.account_type,
        "symbol": row.symbol,
        "raw_symbol": row.raw_symbol,
        "name": row.name,
        "activity_type": row.activity_type,
        "activity_sub_type": row.activity_sub_type,
        "transaction_date": _str_date(row.transaction_date),
        "quantity": _float(row.quantity),
        "unit_price": _float(row.unit_price),
        "commission": _float(row.commission),
        "net_cash_amount": _float(row.net_cash_amount),
        "currency": row.currency,
    }


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


async def replace_transactions_for_source(
    user_id: str,
    source: str,
    min_date: str,
    max_date: str,
    transactions: list[dict],
) -> None:
    async with _session() as session:
        async with session.begin():
            await session.execute(
                delete(Transaction).where(
                    and_(
                        Transaction.user_id == user_id,
                        Transaction.source == source,
                        Transaction.transaction_date >= min_date,
                        Transaction.transaction_date <= max_date,
                    )
                )
            )
            if transactions:
                session.add_all([
                    Transaction(
                        user_id=user_id,
                        source=t.get("source"),
                        account_type=t.get("account_type"),
                        symbol=t.get("symbol"),
                        raw_symbol=t.get("raw_symbol"),
                        name=t.get("name"),
                        activity_type=t.get("activity_type"),
                        activity_sub_type=t.get("activity_sub_type"),
                        transaction_date=t.get("transaction_date"),
                        quantity=t.get("quantity"),
                        unit_price=t.get("unit_price"),
                        commission=t.get("commission"),
                        net_cash_amount=t.get("net_cash_amount"),
                        currency=t.get("currency"),
                    )
                    for t in transactions
                ])


async def get_transactions(user_id: str) -> list[dict]:
    async with _session() as session:
        result = await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.transaction_date.desc())
        )
        return [_row_to_dict(row) for row in result.scalars().all()]


async def get_transaction_sources(user_id: str) -> list[dict]:
    async with _session() as session:
        result = await session.execute(
            select(
                Transaction.source,
                func.count().label("count"),
                func.min(Transaction.transaction_date).label("min_date"),
                func.max(Transaction.transaction_date).label("max_date"),
            )
            .where(Transaction.user_id == user_id)
            .group_by(Transaction.source)
            .order_by(Transaction.source)
        )
        return [
            {
                "source": row.source,
                "count": row.count,
                "min_date": _str_date(row.min_date),
                "max_date": _str_date(row.max_date),
            }
            for row in result.all()
        ]


async def clear_transactions_for_source(user_id: str, source: str | None) -> None:
    async with _session() as session:
        async with session.begin():
            await session.execute(
                delete(Transaction).where(
                    and_(
                        Transaction.user_id == user_id,
                        Transaction.source == source,
                    )
                )
            )


# ---------------------------------------------------------------------------
# Holdings
# ---------------------------------------------------------------------------


async def get_holdings(user_id: str) -> list[dict]:
    async with _session() as session:
        result = await session.execute(
            select(Holding).where(Holding.user_id == user_id)
        )
        return [row.raw_data for row in result.scalars().all()]


async def set_holdings(user_id: str, holdings: list[dict]) -> None:
    async with _session() as session:
        async with session.begin():
            await session.execute(delete(Holding).where(Holding.user_id == user_id))
            if holdings:
                session.add_all([
                    Holding(
                        user_id=user_id,
                        symbol=h.get("symbol"),
                        name=h.get("name"),
                        quantity=h.get("quantity"),
                        currency=h.get("market_price_currency"),
                        raw_data=h,
                    )
                    for h in holdings
                ])


# ---------------------------------------------------------------------------
# User preferences
# ---------------------------------------------------------------------------

_DEFAULT_PREFERENCES: dict = {
    "grouping_labels": [],
    "grouping_assignments": {},
    "sector_overrides": {},
    "industry_overrides": {},
    "visible_columns": None,
    "middle_chart_column": None,
    "chart_value_mode": None,
}

_PREFERENCE_KEYS = set(_DEFAULT_PREFERENCES.keys())


async def get_user_preferences(user_id: str) -> dict:
    async with _session() as session:
        row = await session.get(UserPreferences, user_id)
        if row is None:
            return dict(_DEFAULT_PREFERENCES)
        return {
            "grouping_labels": row.grouping_labels or [],
            "grouping_assignments": row.grouping_assignments or {},
            "sector_overrides": row.sector_overrides or {},
            "industry_overrides": row.industry_overrides or {},
            "visible_columns": row.visible_columns,
            "middle_chart_column": row.middle_chart_column,
            "chart_value_mode": row.chart_value_mode,
        }


async def upsert_user_preferences(user_id: str, prefs: dict) -> None:
    async with _session() as session:
        async with session.begin():
            row = await session.get(UserPreferences, user_id)
            if row is None:
                session.add(UserPreferences(user_id=user_id, **prefs))
            else:
                for key, value in prefs.items():
                    if key in _PREFERENCE_KEYS:
                        setattr(row, key, value)


# ---------------------------------------------------------------------------
# Trends cache
# ---------------------------------------------------------------------------


async def get_trends_cache(cache_key: str) -> dict | None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
    async with _session() as session:
        result = await session.execute(
            select(TrendsCache).where(
                and_(
                    TrendsCache.cache_key == cache_key,
                    TrendsCache.fetched_at >= cutoff,
                )
            )
        )
        row = result.scalar_one_or_none()
        return row.data if row else None


async def upsert_trends_cache(cache_key: str, data: dict) -> None:
    async with _session() as session:
        async with session.begin():
            stmt = (
                pg_insert(TrendsCache)
                .values(cache_key=cache_key, data=data)
                .on_conflict_do_update(
                    index_elements=["cache_key"],
                    set_={"data": data, "fetched_at": func.now()},
                )
            )
            await session.execute(stmt)
