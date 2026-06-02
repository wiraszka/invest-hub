from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from services.search import search_companies

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


@router.get("/search")
def search(q: str = Query(..., min_length=1)) -> list[dict]:
    try:
        return search_companies(q, limit=10)
    except Exception:
        logger.exception("search error", extra={"q": q})
        raise HTTPException(
            status_code=502,
            detail={"code": "SEARCH_ERROR", "message": "Search unavailable"},
        )
