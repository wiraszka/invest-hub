from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query

from services.price import get_current_price, get_price_history

router = APIRouter(prefix="/api/v1")


@router.get("/price/{ticker}")
async def current_price(ticker: str = Path(..., min_length=1)) -> dict:
    try:
        return await get_current_price(ticker.upper())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/price/{ticker}/history")
async def price_history(
    ticker: str = Path(..., min_length=1),
    days: int = Query(default=365, ge=1, le=7300),
    interval: str = Query(default="1day"),
) -> dict:
    try:
        return await get_price_history(ticker.upper(), days=days, interval=interval)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
