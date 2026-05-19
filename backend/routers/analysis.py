from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/api/analysis/{ticker}")
def trigger_analysis(ticker: str) -> dict:
    raise HTTPException(status_code=501, detail="Research pipeline not yet implemented")


@router.get("/api/analysis/{ticker}")
def fetch_analysis(ticker: str) -> dict:
    raise HTTPException(status_code=501, detail="Research pipeline not yet implemented")
