from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Path, Query

from services.price import get_current_price, get_price_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

_TICKER_PATH = Path(..., min_length=1, max_length=10, pattern=r"^[A-Z0-9.\-]+$")


@router.get("/price/{ticker}")
async def current_price(ticker: str = _TICKER_PATH) -> dict:
    try:
        return await get_current_price(ticker.upper())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        logger.exception("price fetch error", extra={"ticker": ticker})
        raise HTTPException(
            status_code=502,
            detail={"code": "PROVIDER_ERROR", "message": "Price data unavailable"},
        )


@router.get("/price/{ticker}/history")
async def price_history(
    ticker: str = _TICKER_PATH,
    days: int = Query(default=365, ge=1, le=7300),
    interval: str = Query(default="1day"),
) -> dict:
    try:
        return await get_price_history(ticker.upper(), days=days, interval=interval)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        logger.exception("price history fetch error", extra={"ticker": ticker})
        raise HTTPException(
            status_code=502,
            detail={
                "code": "PROVIDER_ERROR",
                "message": "Price history unavailable",
            },
        )
