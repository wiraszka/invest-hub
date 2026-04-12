from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from services.db import get_analysis, upsert_analysis
from services.llm import classify_company, run_analysis
from services.sec import get_recent_10k_text

router = APIRouter()


@router.post("/api/analysis/{ticker}")
def trigger_analysis(ticker: str = Path(...)) -> dict:
    ticker = ticker.upper()

    try:
        filing_text = get_recent_10k_text(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch SEC filing: {e}")

    try:
        company_type = classify_company(filing_text)
        markdown = run_analysis(ticker, company_type, filing_text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM analysis failed: {e}")

    try:
        upsert_analysis(ticker, company_type, markdown)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to store analysis: {e}")

    return {"ticker": ticker, "company_type": company_type, "status": "ok"}


@router.get("/api/analysis/{ticker}")
def fetch_analysis(ticker: str = Path(...)) -> dict:
    ticker = ticker.upper()
    doc = get_analysis(ticker)
    if doc is None:
        raise HTTPException(status_code=404, detail="No analysis found for this ticker")
    return doc
