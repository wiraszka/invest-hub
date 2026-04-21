from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from services.db import get_trends_cache, upsert_trends_cache
from services.trends import TIMEFRAME_OPTIONS, fetch_trends_data

COMMODITIES: dict[str, str] = {
    "Gold": "gold",
    "Silver": "silver",
    "Platinum": "platinum",
    "Copper": "copper",
    "Uranium": "uranium",
    "Lithium": "lithium",
    "Nickel": "nickel",
    "Phosphate": "phosphate",
    "Graphite": "graphite",
    "Zinc": "zinc",
    "Antimony": "antimony",
}

router = APIRouter()


@router.get("/api/trends")
def trends(
    commodities: list[str] = Query(...),
    timeframe: str = Query("Past 1 month"),
    geo: str = Query(""),
) -> dict:
    if not commodities:
        raise HTTPException(
            status_code=400, detail="At least one commodity is required"
        )

    unknown = [c for c in commodities if c not in COMMODITIES]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown commodities: {unknown}")

    if timeframe not in TIMEFRAME_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown timeframe: {timeframe}")

    cache_key = f"{','.join(sorted(commodities))}|{timeframe}|{geo.strip().upper()}"
    cached = get_trends_cache(cache_key)
    if cached is not None:
        return cached

    try:
        result = fetch_trends_data(
            commodities=commodities,
            keyword_map=COMMODITIES,
            timeframe_label=timeframe,
            geo=geo.strip().upper(),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    upsert_trends_cache(cache_key, result)
    return result
