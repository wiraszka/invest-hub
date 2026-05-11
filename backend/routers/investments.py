from fastapi import (
    APIRouter,
    Body,
    File,
    Header,
    HTTPException,
    Path,
    Query,
    UploadFile,
)

from services.db import (
    get_analysis,
    get_holdings_cache,
    get_positions_cache,
    get_symbol_metadata,
    get_symbol_metadata_batch,
    get_transactions,
    get_user_preferences,
    invalidate_positions_cache,
    replace_transactions,
    set_holdings_cache,
    set_positions_cache,
    upsert_symbol_metadata,
    upsert_user_preferences,
)
from services.fmp import get_symbol_metadata as fetch_from_fmp
from services.holdings import parse_holdings_csv
from services.investments import build_positions, parse_csv
from services.sec import get_sic_metadata as fetch_from_sec

router = APIRouter()


def _require_user(x_user_id: str | None) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    return x_user_id


def _detect_format(content: str) -> str:
    """Detect CSV format by inspecting the header row."""
    first_line = content.split("\n")[0]
    if "Market Price" in first_line or "Book Value (CAD)" in first_line:
        return "holdings"
    return "activities"


@router.post("/api/investments/upload")
async def upload_csv(
    file: UploadFile = File(...),
    x_user_id: str | None = Header(default=None),
) -> dict:
    user_id = _require_user(x_user_id)
    content = (await file.read()).decode("utf-8")

    fmt = _detect_format(content)

    if fmt == "holdings":
        data = parse_holdings_csv(content)
        set_holdings_cache(user_id, data)
        return {"type": "holdings", "count": len(data)}

    transactions = parse_csv(content)
    replace_transactions(user_id, transactions)
    invalidate_positions_cache(user_id)
    return {"type": "activities", "count": len(transactions)}


@router.get("/api/investments/positions")
def get_positions(
    x_user_id: str | None = Header(default=None),
) -> list[dict]:
    user_id = _require_user(x_user_id)
    cached = get_positions_cache(user_id)
    if cached is not None:
        return cached
    transactions = get_transactions(user_id)
    positions = build_positions(transactions)
    set_positions_cache(user_id, positions)
    return positions


@router.get("/api/investments/holdings")
def get_holdings(
    x_user_id: str | None = Header(default=None),
) -> list[dict]:
    user_id = _require_user(x_user_id)
    cached = get_holdings_cache(user_id)
    return cached if cached is not None else []


@router.get("/api/investments/preferences")
def get_preferences(
    x_user_id: str | None = Header(default=None),
) -> dict:
    user_id = _require_user(x_user_id)
    return get_user_preferences(user_id)


@router.put("/api/investments/preferences")
def put_preferences(
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
    upsert_user_preferences(user_id, prefs)
    return prefs


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
    if fmp_data:
        upsert_symbol_metadata(ticker, fmp_data)
        result = get_symbol_metadata(ticker) or {**fmp_data, "ticker": ticker}
        result["has_analysis"] = get_analysis(ticker) is not None
        return result

    sec_data = fetch_from_sec(ticker)
    if not sec_data:
        raise HTTPException(status_code=404, detail=f"No metadata found for {ticker}")

    upsert_symbol_metadata(ticker, sec_data)
    result = get_symbol_metadata(ticker) or {**sec_data, "ticker": ticker}
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
