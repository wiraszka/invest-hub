from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from services.price import get_current_price, get_price_history

router = APIRouter()


@router.get("/api/price/{ticker}")
def current_price(ticker: str = Path(..., min_length=1)) -> dict:
    try:
        return get_current_price(ticker.upper())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/api/price/{ticker}/history")
def price_history(ticker: str = Path(..., min_length=1)) -> dict:
    try:
        return get_price_history(ticker.upper())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
