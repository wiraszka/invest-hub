from fastapi import APIRouter, File, Header, HTTPException, Path, Query, UploadFile

from services.db import (
    get_analysis,
    get_symbol_metadata,
    get_symbol_metadata_batch,
    get_transactions,
    replace_transactions,
    upsert_symbol_metadata,
)
from services.fmp import get_symbol_metadata as fetch_from_fmp
from services.investments import build_positions, parse_csv

router = APIRouter()


def _require_user(x_user_id: str | None) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    return x_user_id


@router.post("/api/investments/upload")
async def upload_transactions(
    file: UploadFile = File(...),
    x_user_id: str | None = Header(default=None),
) -> dict:
    user_id = _require_user(x_user_id)
    content = (await file.read()).decode("utf-8")
    transactions = parse_csv(content)
    replace_transactions(user_id, transactions)
    return {"count": len(transactions)}


@router.get("/api/investments/positions")
def get_positions(
    x_user_id: str | None = Header(default=None),
) -> list[dict]:
    user_id = _require_user(x_user_id)
    transactions = get_transactions(user_id)
    return build_positions(transactions)


@router.get("/api/investments/transactions")
def get_all_transactions(
    x_user_id: str | None = Header(default=None),
) -> list[dict]:
    user_id = _require_user(x_user_id)
    return get_transactions(user_id)


@router.post("/api/investments/metadata/{ticker}")
def analyze_ticker_metadata(
    ticker: str = Path(...),
) -> dict:
    """
    Return cached symbol metadata for a ticker, fetching from FMP if missing or stale.
    Also reports whether a full LLM analysis exists for this ticker.
    """
    cached = get_symbol_metadata(ticker)
    if cached:
        cached["has_analysis"] = get_analysis(ticker) is not None
        return cached

    fmp_data = fetch_from_fmp(ticker)
    if not fmp_data:
        raise HTTPException(status_code=404, detail=f"No metadata found for {ticker}")

    upsert_symbol_metadata(ticker, fmp_data)
    result = get_symbol_metadata(ticker) or {**fmp_data, "ticker": ticker}
    result["has_analysis"] = get_analysis(ticker) is not None
    return result


@router.get("/api/investments/metadata")
def get_metadata_batch(
    tickers: str = Query(..., description="Comma-separated list of ticker symbols"),
) -> dict[str, dict]:
    """
    Return cached metadata for a batch of tickers (no FMP calls).
    Includes has_analysis flag for each ticker found in cache.
    """
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    metadata = get_symbol_metadata_batch(ticker_list)

    for ticker, doc in metadata.items():
        doc["has_analysis"] = get_analysis(ticker) is not None

    return metadata
