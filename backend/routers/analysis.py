from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ProviderUnavailableError
from db.pg import get_db_session
from models.market_data import AnalysisData, AnalysisReport, AnalysisResult
from services import analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analysis"])

_TICKER_PATH = Path(..., min_length=1, max_length=10, pattern=r"^[A-Z0-9.\-]+$")


@router.get("/analysis/{ticker}/data", response_model=AnalysisData)
async def get_analysis_data(
    ticker: str = _TICKER_PATH,
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisData:
    """Return the most recent cached Phase 1 data (financials + chart data) for a ticker.

    Returns 404 if no data has been generated yet. Does not trigger generation.
    """
    data = await analysis.get_cached_data(ticker.upper(), session)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "DATA_NOT_FOUND", "message": "No data found for this ticker — use POST to generate"},
        )
    return data


@router.post("/analysis/{ticker}/data", response_model=AnalysisData)
async def generate_analysis_data(
    ticker: str = _TICKER_PATH,
    force: bool = Query(default=False, description="Bypass cache and regenerate"),
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisData:
    """Fetch provider data and run the analyzer for a ticker (~5-8s).

    Returns cached data if within TTL. Pass force=true to bypass the cache.
    Always returns financials; chart_data and template_key may be null if the
    analyzer (Haiku) failed.
    """
    try:
        return await analysis.run_data(ticker.upper(), session, force=force)
    except ProviderUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "PROVIDER_UNAVAILABLE", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception("analysis data pipeline error", extra={"ticker": ticker})
        raise HTTPException(
            status_code=502,
            detail={"code": "PIPELINE_ERROR", "message": "Data pipeline failed — see server logs"},
        ) from exc


@router.get("/analysis/{ticker}/report", response_model=AnalysisReport)
async def get_analysis_report(
    ticker: str = _TICKER_PATH,
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisReport:
    """Return the most recent cached written report for a ticker.

    Returns 404 if no report has been generated yet. Does not trigger generation.
    """
    report = await analysis.get_cached_report(ticker.upper(), session)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "REPORT_NOT_FOUND", "message": "No report found for this ticker — use POST to generate"},
        )
    return report


@router.post("/analysis/{ticker}/report", response_model=AnalysisReport)
async def generate_analysis_report(
    ticker: str = _TICKER_PATH,
    force: bool = Query(default=False, description="Bypass cache and regenerate"),
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisReport:
    """Generate the written report for a ticker via Sonnet (~30-90s).

    Uses cached Phase 1 data if available; otherwise runs Phase 1 first.
    Returns cached report if within TTL. Pass force=true to bypass the cache.
    """
    try:
        return await analysis.run_report(ticker.upper(), session, force=force)
    except ProviderUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "PROVIDER_UNAVAILABLE", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "CLASSIFICATION_ERROR", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception("analysis report pipeline error", extra={"ticker": ticker})
        raise HTTPException(
            status_code=502,
            detail={"code": "PIPELINE_ERROR", "message": "Report pipeline failed — see server logs"},
        ) from exc


@router.get("/analysis/{ticker}/analyze", response_model=AnalysisResult)
async def get_analysis_result(
    ticker: str = _TICKER_PATH,
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisResult:
    """Return the most recent cached analyze result (independence + chart data) for a ticker.

    Returns 404 if Phase 2.5 has not been run yet. Does not trigger generation.
    """
    result = await analysis.get_cached_analyze(ticker.upper(), session)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "ANALYZE_NOT_FOUND", "message": "No analyze result found for this ticker — use POST to generate"},
        )
    return result


@router.post("/analysis/{ticker}/analyze", response_model=AnalysisResult)
async def generate_analysis_result(
    ticker: str = _TICKER_PATH,
    force: bool = Query(default=False, description="Bypass cache and regenerate"),
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisResult:
    """Run independence detection and chart data extraction for a ticker via Haiku (~2-3s).

    Uses cached Phase 1 data if available; otherwise runs Phase 1 first.
    Returns cached result if within TTL. Pass force=true to bypass the cache.
    """
    try:
        return await analysis.run_analyze(ticker.upper(), session, force=force)
    except ProviderUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "PROVIDER_UNAVAILABLE", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception("analysis analyze pipeline error", extra={"ticker": ticker})
        raise HTTPException(
            status_code=502,
            detail={"code": "PIPELINE_ERROR", "message": "Analyze pipeline failed — see server logs"},
        ) from exc
