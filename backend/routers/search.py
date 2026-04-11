from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from services.search import search_companies

router = APIRouter()


@router.get("/api/search")
def search(q: str = Query(..., min_length=1)) -> list[dict]:
    try:
        return search_companies(q, limit=5)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
