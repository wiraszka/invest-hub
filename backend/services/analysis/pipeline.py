from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.pg_models import (
    AnalysisReportRow,
    NormalizedFinancials,
    NormalizedProfile,
    NormalizedQuote,
    Security,
)
from models.market_data import (
    AnalysisData,
    AnalysisReport,
    AnalysisResult,
    FilingContext,
)
from services.analysis import (
    analyzer,
    context_builder,
    filing_service,
    prompt_loader,
    report_generator,
)
from services.analysis.context_builder import StructuredContext
from services.identity import resolve_identity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 1 — providers
# ---------------------------------------------------------------------------


async def run_providers(
    ticker: str, session: AsyncSession, force: bool = False
) -> AnalysisData:
    """Phase 1: fetch all market-data provider sources.

    Fetches financials, quote, profile, leadership, and market intelligence.
    No SEC filing is fetched here — that is Phase 2 (``run_filing``).
    No template classification — that is Phase 3 (``run_format``).

    Data freshness is handled by per-table TTL checks inside fetch_providers().
    Returns immediately if all data is within TTL; makes provider API calls
    only for cache misses.
    """
    t0 = time.monotonic()
    logger.info("phase 1 — starting data collection", extra={"ticker": ticker})

    context = await context_builder.fetch_providers(ticker, session)

    elapsed = time.monotonic() - t0
    logger.info(
        "phase 1 — complete",
        extra={
            "ticker": ticker,
            "has_leadership": bool(context.leadership_block),
            "has_market_intel": bool(context.market_intelligence_block),
            "elapsed": f"{elapsed:.1f}s",
        },
    )
    return AnalysisData(
        ticker=ticker,
        company_name=context.company_name,
        exchange=context.exchange,
        currency=context.currency,
        sector=context.sector,
        industry=context.industry,
        logo_url=context.logo_url,
        template_key="",  # classified in Phase 3
        generated_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Phase 2 — SEC filing
# ---------------------------------------------------------------------------


async def run_filing(
    ticker: str, session: AsyncSession, force: bool = False
) -> FilingContext:
    """Phase 2: fetch the most recent annual filing from SEC EDGAR.

    Stores parsed item sections (1, 1A, 7) in the ``sec_filings`` table.
    Returns cached filing unless force=True or no cached record exists.
    """
    if not force:
        cached = await filing_service.get_cached(ticker, session)
        if cached is not None:
            logger.info("phase 2 — returning cached filing", extra={"ticker": ticker})
            return cached

    t0 = time.monotonic()
    logger.info("phase 2 — fetching SEC filing", extra={"ticker": ticker})
    ctx = await filing_service.fetch_and_store(ticker, session)
    elapsed = time.monotonic() - t0
    logger.info(
        "phase 2 — complete",
        extra={
            "ticker": ticker,
            "form_type": ctx.form_type,
            "filing_date": ctx.filing_date,
            "elapsed": f"{elapsed:.1f}s",
        },
    )
    return ctx


# ---------------------------------------------------------------------------
# Phase 3 — format (classify + assemble LLM input)
# ---------------------------------------------------------------------------


async def run_format(
    ticker: str, session: AsyncSession, force: bool = False
) -> StructuredContext:
    """Phase 3: classify template + format full LLM input context.

    Calls run_providers() first (no-op if data is fresh), then assembles the
    full StructuredContext including metrics_block, leadership_block,
    market_intelligence_block, business_summary, and filing_excerpt.

    Stateless — no DB writes.  Fast: pure DB reads + Python formatting.
    """
    t0 = time.monotonic()
    logger.info("phase 3 — starting format", extra={"ticker": ticker})

    await run_providers(ticker, session, force=force)
    filing = await filing_service.get_cached(ticker, session)
    context = await context_builder.build_context(ticker, session, filing=filing)

    elapsed = time.monotonic() - t0
    logger.info(
        "phase 3 — complete",
        extra={
            "ticker": ticker,
            "template_key": context.template_key,
            "has_leadership": bool(context.leadership_block),
            "has_market_intel": bool(context.market_intelligence_block),
            "has_filing": bool(context.filing_excerpt),
            "elapsed": f"{elapsed:.1f}s",
        },
    )
    return context


# ---------------------------------------------------------------------------
# Phase 4 — analyze (Groq / Llama 3.1 8B)
# ---------------------------------------------------------------------------


async def run_analyze(
    ticker: str, session: AsyncSession, force: bool = False
) -> AnalysisResult:
    """Phase 4: independence detection + chart data extraction via Groq.

    Calls run_format() to get the full StructuredContext (Phase 3), then runs
    the Groq analysis.  Returns cached AnalysisResult within TTL unless
    force=True.
    """
    if not force:
        cached = await _load_cached_analyze(ticker, session)
        if cached is not None:
            logger.info(
                "phase 4 — returning cached result",
                extra={"ticker": ticker, "independence": cached.independence},
            )
            return cached

    t0 = time.monotonic()
    logger.info("phase 4 — starting (Groq / Llama 3.1 8B)", extra={"ticker": ticker})

    context = await run_format(ticker, session, force=False)

    result_dict = await analyzer.analyze(context)
    analyzed_at = datetime.now(timezone.utc)

    result = AnalysisResult(
        ticker=ticker,
        independence=result_dict["independence"],
        chart_data=result_dict["chart_data"],
        analyzed_at=analyzed_at,
    )
    await _upsert_analyze(result, context.security_id, session)
    elapsed = time.monotonic() - t0
    logger.info(
        "phase 4 — complete",
        extra={
            "ticker": ticker,
            "independence": result.independence,
            "chart_fields": len(result.chart_data),
            "elapsed": f"{elapsed:.1f}s",
        },
    )
    return result


# ---------------------------------------------------------------------------
# Phase 5 — report (Sonnet)
# ---------------------------------------------------------------------------


async def run_report(
    ticker: str, session: AsyncSession, force: bool = False
) -> AnalysisReport:
    """Phase 5: generate the written report via Sonnet (~30–90 s).

    Calls run_format() to get the full StructuredContext (Phase 3).
    Independence defaults to "independent" if Phase 4 has not been run.
    Returns cached AnalysisReport within TTL unless force=True.
    """
    if not force:
        cached = await _load_cached_report(ticker, session)
        if cached is not None:
            logger.info("phase 5 — returning cached report", extra={"ticker": ticker})
            return cached

    t0 = time.monotonic()
    logger.info("phase 5 — starting report generation", extra={"ticker": ticker})

    context = await run_format(ticker, session, force=False)
    independence = await _load_independence(ticker, session)

    prompt_text, _ = prompt_loader.load(context.template_key)
    report_markdown = await report_generator.generate(
        context=context,
        prompt_template=prompt_text,
        report_template_key=context.template_key,
        independence=independence,
    )

    report = AnalysisReport(
        ticker=ticker,
        report_template=context.template_key,
        independence=independence,
        report_markdown=report_markdown,
        generated_at=datetime.now(timezone.utc),
    )
    await _upsert_report(report, session)
    elapsed = time.monotonic() - t0
    logger.info(
        "phase 5 — complete",
        extra={
            "ticker": ticker,
            "template_key": context.template_key,
            "independence": independence,
            "elapsed": f"{elapsed:.1f}s",
        },
    )
    return report


# ---------------------------------------------------------------------------
# Full pipeline orchestration
# ---------------------------------------------------------------------------


async def run_research_pipeline(
    ticker: str,
    session: AsyncSession,
    force: bool = False,
) -> AnalysisReport:
    """Run all phases sequentially: providers → filing → format → analyze → report.

    Each phase respects its own cache unless force=True.
    """
    await run_providers(ticker, session, force=force)
    try:
        await run_filing(ticker, session, force=force)
    except Exception as exc:
        logger.warning(
            "pipeline — filing phase failed, continuing without SEC data",
            extra={"ticker": ticker, "error": str(exc)},
        )
    await run_format(ticker, session, force=False)
    await run_analyze(ticker, session, force=force)
    return await run_report(ticker, session, force=force)


# ---------------------------------------------------------------------------
# Cache read helpers (public — used by router GET endpoints)
# ---------------------------------------------------------------------------


async def get_cached_data(ticker: str, session: AsyncSession) -> AnalysisData | None:
    """Return Phase 1 data if it exists in DB, else None.

    Reads from securities + profiles — Phase 1 no longer writes to
    analysis_reports.  Returns None if no market data has been fetched yet.
    """
    try:
        identity = await resolve_identity(ticker, "fmp", session)
    except Exception:
        return None

    sid = identity.security_id
    if not sid:
        return None

    # Check if any market data exists as indicator Phase 1 has run
    quote_result = await session.execute(
        select(NormalizedQuote).where(NormalizedQuote.security_id == sid)
    )
    financials_result = await session.execute(
        select(NormalizedFinancials)
        .where(NormalizedFinancials.security_id == sid)
        .limit(1)
    )
    has_data = (
        quote_result.scalars().first() is not None
        or financials_result.scalars().first() is not None
    )
    if not has_data:
        return None

    security_result = await session.execute(select(Security).where(Security.id == sid))
    security = security_result.scalar_one_or_none()

    profile_result = await session.execute(
        select(NormalizedProfile).where(NormalizedProfile.security_id == sid)
    )
    profile = profile_result.scalar_one_or_none()

    # template_key from most recent report (written by Phase 5), or ""
    report_result = await session.execute(
        select(AnalysisReportRow).where(AnalysisReportRow.ticker == ticker)
    )
    report_row = report_result.scalars().first()
    template_key = (report_row.report_template or "") if report_row else ""

    return AnalysisData(
        ticker=ticker,
        company_name=(security.name if security else None) or ticker,
        exchange=security.exchange if security else None,
        currency=security.currency if security else "USD",
        sector=profile.sector if profile else None,
        industry=profile.industry if profile else None,
        logo_url=profile.logo_url if profile else None,
        template_key=template_key,
        generated_at=datetime.now(timezone.utc),
    )


async def get_cached_analyze(
    ticker: str, session: AsyncSession
) -> AnalysisResult | None:
    return await _load_cached_analyze(ticker, session, ignore_ttl=True)


async def get_cached_report(
    ticker: str, session: AsyncSession
) -> AnalysisReport | None:
    return await _load_cached_report(ticker, session, ignore_ttl=True)


# ---------------------------------------------------------------------------
# Backward-compat shim
# ---------------------------------------------------------------------------


async def run_data(
    ticker: str, session: AsyncSession, force: bool = False
) -> AnalysisData:
    """Backward-compatible alias for ``run_providers()``."""
    return await run_providers(ticker, session, force=force)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _load_cached_analyze(
    ticker: str,
    session: AsyncSession,
    ignore_ttl: bool = False,
) -> AnalysisResult | None:
    result = await session.execute(
        select(AnalysisReportRow).where(AnalysisReportRow.ticker == ticker)
    )
    row = result.scalars().first()
    if row is None or not row.analyzed_at:
        return None

    if not ignore_ttl:
        ttl = timedelta(days=settings.analysis_report_ttl_days)
        age = datetime.now(timezone.utc) - row.analyzed_at
        if age > ttl:
            logger.info(
                "cached analyze result is stale",
                extra={"ticker": ticker, "age_days": age.days},
            )
            return None

    return AnalysisResult(
        ticker=row.ticker,
        independence=row.independence or "independent",
        chart_data=row.chart_data or {},
        analyzed_at=row.analyzed_at,
    )


async def _load_cached_report(
    ticker: str,
    session: AsyncSession,
    ignore_ttl: bool = False,
) -> AnalysisReport | None:
    result = await session.execute(
        select(AnalysisReportRow).where(AnalysisReportRow.ticker == ticker)
    )
    row = result.scalars().first()
    if row is None or not row.report_markdown or not row.report_generated_at:
        return None

    if not ignore_ttl:
        ttl = timedelta(days=settings.analysis_report_ttl_days)
        age = datetime.now(timezone.utc) - row.report_generated_at
        if age > ttl:
            logger.info(
                "cached report is stale", extra={"ticker": ticker, "age_days": age.days}
            )
            return None

    return AnalysisReport(
        ticker=row.ticker,
        report_template=row.report_template or "",
        independence=row.independence or "independent",
        report_markdown=row.report_markdown,
        generated_at=row.report_generated_at,
    )


async def _load_independence(ticker: str, session: AsyncSession) -> str:
    """Load independence from the analyze phase, defaulting to 'independent'."""
    result = await session.execute(
        select(AnalysisReportRow).where(AnalysisReportRow.ticker == ticker)
    )
    row = result.scalars().first()
    return row.independence if row and row.independence else "independent"


async def _upsert_analyze(
    result: AnalysisResult,
    security_id: str | None,
    session: AsyncSession,
) -> None:
    """Phase 4 owns analysis_reports row creation via INSERT ON CONFLICT."""
    await session.execute(
        insert(AnalysisReportRow)
        .values(
            ticker=result.ticker,
            security_id=security_id,
            independence=result.independence,
            chart_data=result.chart_data,
            analyzed_at=result.analyzed_at,
        )
        .on_conflict_do_update(
            index_elements=["ticker"],
            set_={
                "security_id": security_id,
                "independence": result.independence,
                "chart_data": result.chart_data,
                "analyzed_at": result.analyzed_at,
            },
        )
    )
    await session.commit()


async def _upsert_report(report: AnalysisReport, session: AsyncSession) -> None:
    await session.execute(
        update(AnalysisReportRow)
        .where(AnalysisReportRow.ticker == report.ticker)
        .values(
            report_template=report.report_template,
            independence=report.independence,
            report_markdown=report.report_markdown,
            report_generated_at=report.generated_at,
        )
    )
    await session.commit()
