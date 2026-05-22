from __future__ import annotations

from fastapi import APIRouter, Body, Depends, File, Header, HTTPException, Path, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.pg import get_db_session
from db.pg_models import AnalysisReportRow
from services.holdings import parse_holdings_csv
from services.investments import build_positions, parse_csv, parse_questrade_xlsx
from services.pg import (
    clear_transactions_for_source,
    get_holdings,
    get_transaction_sources,
    get_transactions,
    get_user_preferences,
    replace_transactions_for_source,
    set_holdings,
    upsert_user_preferences,
)
from services.search import resolve_canonical

router = APIRouter(prefix="/api/v1")


def _require_user(x_user_id: str | None) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    return x_user_id


def _detect_format(content: str) -> str:
    first_line = content.split("\n")[0]
    if "Market Price" in first_line or "Book Value (CAD)" in first_line:
        return "holdings"
    return "activities"


@router.post("/investments/upload")
async def upload_csv(
    file: UploadFile = File(...),
    x_user_id: str | None = Header(default=None),
) -> dict:
    user_id = _require_user(x_user_id)
    raw = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".xlsx"):
        transactions = parse_questrade_xlsx(raw)
    else:
        content = raw.decode("utf-8")
        fmt = _detect_format(content)
        if fmt == "holdings":
            data = parse_holdings_csv(content)
            await set_holdings(user_id, data)
            return {"type": "holdings", "count": len(data)}
        transactions = parse_csv(content)

    if not transactions:
        return {"type": "activities", "count": 0}

    source = transactions[0]["source"]
    min_date = min(t["transaction_date"] for t in transactions)
    max_date = max(t["transaction_date"] for t in transactions)
    await replace_transactions_for_source(user_id, source, min_date, max_date, transactions)
    return {"type": "activities", "count": len(transactions)}


@router.get("/investments/positions")
async def get_positions(
    x_user_id: str | None = Header(default=None),
) -> list[dict]:
    user_id = _require_user(x_user_id)
    transactions = await get_transactions(user_id)
    return build_positions(transactions)


@router.get("/investments/holdings")
async def get_holdings_route(
    x_user_id: str | None = Header(default=None),
) -> list[dict]:
    user_id = _require_user(x_user_id)
    return await get_holdings(user_id)


@router.get("/investments/preferences")
async def get_preferences(
    x_user_id: str | None = Header(default=None),
) -> dict:
    user_id = _require_user(x_user_id)
    return await get_user_preferences(user_id)


@router.put("/investments/preferences")
async def put_preferences(
    x_user_id: str | None = Header(default=None),
    body: dict = Body(...),
) -> dict:
    user_id = _require_user(x_user_id)
    allowed = {
        "grouping_labels",
        "grouping_assignments",
        "sector_overrides",
        "industry_overrides",
        "visible_columns",
        "middle_chart_column",
        "chart_value_mode",
    }
    prefs = {k: v for k, v in body.items() if k in allowed}
    await upsert_user_preferences(user_id, prefs)
    return prefs


@router.get("/investments/sources")
async def list_sources(
    x_user_id: str | None = Header(default=None),
) -> list[dict]:
    user_id = _require_user(x_user_id)
    return await get_transaction_sources(user_id)


@router.delete("/investments/sources/{source}")
async def delete_source(
    source: str = Path(...),
    x_user_id: str | None = Header(default=None),
) -> dict:
    user_id = _require_user(x_user_id)
    actual_source = None if source == "legacy" else source
    await clear_transactions_for_source(user_id, actual_source)
    return {"deleted": source}


@router.get("/investments/transactions")
async def get_all_transactions(
    x_user_id: str | None = Header(default=None),
) -> list[dict]:
    user_id = _require_user(x_user_id)
    return await get_transactions(user_id)


# ---------------------------------------------------------------------------
# Ticker resolution
# ---------------------------------------------------------------------------


class _ResolveItem(BaseModel):
    symbol: str
    exchange: str | None = None


@router.post("/investments/resolve")
async def resolve_tickers(items: list[_ResolveItem]) -> dict[str, str]:
    if len(items) > 500:
        raise HTTPException(status_code=422, detail={"code": "TOO_MANY_ITEMS", "message": "Maximum 500 symbols per request"})
    return {item.symbol: resolve_canonical(item.symbol, item.exchange) for item in items}


# ---------------------------------------------------------------------------
# Ticker metadata (from cached analysis)
# ---------------------------------------------------------------------------


def _analysis_row_to_metadata(row: AnalysisReportRow) -> dict:
    sc = row.structured_context or {}
    profile = sc.get("profile") or {}
    security_type = (profile.get("security_type") or "").lower()
    asset_type = "ETF" if security_type in ("etf", "mutualfund", "fund") else "Stock"
    return {
        "ticker": row.ticker,
        "asset_type": asset_type,
        "sector": profile.get("sector"),
        "industry": profile.get("industry"),
        "country": profile.get("country"),
        "sector_weights": None,
        "country_weights": None,
        "has_analysis": bool(row.report_template),
        "fetched_at": row.generated_at.isoformat(),
    }


@router.get("/investments/metadata")
async def get_symbols_metadata(
    tickers: str = Query(..., min_length=1, description="Comma-separated canonical tickers"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, dict]:
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        return {}
    result = await session.execute(
        select(AnalysisReportRow).where(AnalysisReportRow.ticker.in_(ticker_list))
    )
    rows = result.scalars().all()
    return {row.ticker: _analysis_row_to_metadata(row) for row in rows}
