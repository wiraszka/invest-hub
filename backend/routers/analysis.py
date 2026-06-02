from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ProviderUnavailableError
from core.rate_limit import limiter
from db.pg import get_db_session
from models.market_data import (
    AnalysisData,
    AnalysisReport,
    AnalysisResult,
    FilingContext,
    FormattedContext,
)
from services import analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analysis"])

_TICKER_PATH = Path(..., min_length=1, max_length=10, pattern=r"^[A-Z0-9.\-]+$")


# ---------------------------------------------------------------------------
# Phase 1 — providers (data)
# ---------------------------------------------------------------------------


@router.get("/analysis/{ticker}/data", response_model=AnalysisData)
async def get_analysis_data(
    ticker: str = _TICKER_PATH,
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisData:
    """Return the most recent cached Phase 1 data (financials + profile) for a ticker.

    Returns 404 if no data has been generated yet. Does not trigger generation.
    """
    data = await analysis.get_cached_data(ticker.upper(), session)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "DATA_NOT_FOUND",
                "message": "No data found for this ticker — use POST to generate",
            },
        )
    return data


@router.post("/analysis/{ticker}/data", response_model=AnalysisData)
@limiter.limit("20/minute")
async def generate_analysis_data(
    request: Request,
    ticker: str = _TICKER_PATH,
    force: bool = Query(default=False, description="Bypass cache and regenerate"),
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisData:
    """Fetch provider data for a ticker (~5–8 s).

    Returns cached data if within TTL. Pass force=true to bypass the cache.
    No SEC filing is fetched here — use POST /filing for that.
    """
    try:
        return await analysis.run_providers(ticker.upper(), session, force=force)
    except ProviderUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "PROVIDER_UNAVAILABLE", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception("analysis data pipeline error", extra={"ticker": ticker})
        raise HTTPException(
            status_code=502,
            detail={
                "code": "PIPELINE_ERROR",
                "message": "Data pipeline failed — see server logs",
            },
        ) from exc


# ---------------------------------------------------------------------------
# Phase 2 — SEC filing
# ---------------------------------------------------------------------------


@router.get("/analysis/{ticker}/filing", response_model=FilingContext)
async def get_analysis_filing(
    ticker: str = _TICKER_PATH,
    session: AsyncSession = Depends(get_db_session),
) -> FilingContext:
    """Return the cached SEC filing sections for a ticker.

    Returns 404 if no filing has been fetched yet. Does not trigger a fetch.
    """
    filing = await analysis.filing_service.get_cached(ticker.upper(), session)
    if filing is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "FILING_NOT_FOUND",
                "message": "No filing found for this ticker — use POST to fetch",
            },
        )
    return filing


@router.post("/analysis/{ticker}/filing", response_model=FilingContext)
@limiter.limit("10/minute")
async def fetch_analysis_filing(
    request: Request,
    ticker: str = _TICKER_PATH,
    force: bool = Query(
        default=False, description="Bypass cache and re-fetch from EDGAR"
    ),
    session: AsyncSession = Depends(get_db_session),
) -> FilingContext:
    """Fetch and store the most recent annual filing from SEC EDGAR (~5–15 s).

    Returns cached filing if within TTL. Pass force=true to bypass the cache.
    """
    try:
        return await analysis.run_filing(ticker.upper(), session, force=force)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "TICKER_NOT_FOUND", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception("analysis filing pipeline error", extra={"ticker": ticker})
        raise HTTPException(
            status_code=502,
            detail={
                "code": "PIPELINE_ERROR",
                "message": "Filing pipeline failed — see server logs",
            },
        ) from exc


# ---------------------------------------------------------------------------
# Phase 3 — format (classify template + assemble LLM input)
# ---------------------------------------------------------------------------


@router.post("/analysis/{ticker}/format", response_model=FormattedContext)
@limiter.limit("20/minute")
async def generate_analysis_format(
    request: Request,
    ticker: str = _TICKER_PATH,
    force: bool = Query(default=False, description="Bypass cache and re-run Phase 1"),
    session: AsyncSession = Depends(get_db_session),
) -> FormattedContext:
    """Classify the template and assemble the full LLM input context (~1 s).

    Runs Phase 1 first if needed (no-op if data is fresh).  Returns the
    complete formatted context: metrics block, leadership block, market
    intelligence block, business summary, and filing excerpt.
    No LLM calls — pure DB reads + Python formatting.
    """
    try:
        ctx = await analysis.run_format(ticker.upper(), session, force=force)
        return FormattedContext(
            ticker=ctx.ticker,
            company_name=ctx.company_name,
            exchange=ctx.exchange,
            currency=ctx.currency,
            template_key=ctx.template_key,
            sector=ctx.sector,
            industry=ctx.industry,
            metrics_block=ctx.metrics_block,
            business_summary=ctx.business_summary,
            leadership_block=ctx.leadership_block,
            market_intelligence_block=ctx.market_intelligence_block,
            filing_excerpt=ctx.filing_excerpt,
        )
    except ProviderUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "PROVIDER_UNAVAILABLE", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception("analysis format pipeline error", extra={"ticker": ticker})
        raise HTTPException(
            status_code=502,
            detail={
                "code": "PIPELINE_ERROR",
                "message": "Format pipeline failed — see server logs",
            },
        ) from exc


# ---------------------------------------------------------------------------
# Phase 4 — analyze (Groq)
# ---------------------------------------------------------------------------


@router.get("/analysis/{ticker}/analyze", response_model=AnalysisResult)
async def get_analysis_result(
    ticker: str = _TICKER_PATH,
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisResult:
    """Return the most recent cached analyze result (independence + chart data) for a ticker.

    Returns 404 if Phase 4 has not been run yet. Does not trigger generation.
    """
    result = await analysis.get_cached_analyze(ticker.upper(), session)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ANALYZE_NOT_FOUND",
                "message": "No analyze result found for this ticker — use POST to generate",
            },
        )
    return result


@router.post("/analysis/{ticker}/analyze", response_model=AnalysisResult)
@limiter.limit("15/minute")
async def generate_analysis_result(
    request: Request,
    ticker: str = _TICKER_PATH,
    force: bool = Query(default=False, description="Bypass cache and regenerate"),
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisResult:
    """Run independence detection and chart data extraction for a ticker via Groq (~2–3 s).

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
            detail={
                "code": "PIPELINE_ERROR",
                "message": "Analyze pipeline failed — see server logs",
            },
        ) from exc


# ---------------------------------------------------------------------------
# Phase 5 — report (Sonnet)
# ---------------------------------------------------------------------------


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
            detail={
                "code": "REPORT_NOT_FOUND",
                "message": "No report found for this ticker — use POST to generate",
            },
        )
    return report


@router.post("/analysis/{ticker}/report", response_model=AnalysisReport)
@limiter.limit("5/minute")
async def generate_analysis_report(
    request: Request,
    ticker: str = _TICKER_PATH,
    force: bool = Query(default=False, description="Bypass cache and regenerate"),
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisReport:
    """Generate the written report for a ticker via Sonnet (~30–90 s).

    Uses cached Phase 1 data (and Phase 2 filing if available); otherwise runs
    Phase 1 first.  Returns cached report if within TTL. Pass force=true to
    bypass the cache.
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
            detail={
                "code": "PIPELINE_ERROR",
                "message": "Report pipeline failed — see server logs",
            },
        ) from exc


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


@router.post("/analysis/{ticker}/pipeline", response_model=AnalysisReport)
@limiter.limit("3/minute")
async def run_full_pipeline(
    request: Request,
    ticker: str = _TICKER_PATH,
    force: bool = Query(
        default=False, description="Bypass cache and re-run all phases"
    ),
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisReport:
    """Run the full research pipeline: providers → filing → analyze → report.

    Each phase respects its own cache unless force=true.
    Returns the final AnalysisReport.
    """
    try:
        return await analysis.run_research_pipeline(
            ticker.upper(), session, force=force
        )
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
        logger.exception("full pipeline error", extra={"ticker": ticker})
        raise HTTPException(
            status_code=502,
            detail={
                "code": "PIPELINE_ERROR",
                "message": "Pipeline failed — see server logs",
            },
        ) from exc
