from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.exceptions import ProviderUnavailableError
from db.pg_models import AnalysisReportRow
from models.market_data import AnalysisData, AnalysisReport, AnalysisResult
from services.analysis import analyzer, context_builder, prompt_loader, report_generator

logger = logging.getLogger(__name__)


async def run_data(ticker: str, session: AsyncSession, force: bool = False) -> AnalysisData:
    """Run Phase 1: fetch provider data and classify via Python classifier.

    Template classification is deterministic (sector + revenue check) — no LLM.
    Returns cached AnalysisData within TTL unless force=True.
    """
    if not force:
        cached = await _load_cached_data(ticker, session)
        if cached is not None:
            logger.info("returning cached analysis data", extra={"ticker": ticker})
            return cached

    logger.info("running analysis phase 1", extra={"ticker": ticker, "force": force})

    context = await context_builder.build(ticker, session)

    data = AnalysisData(
        ticker=ticker,
        company_name=context.company_name,
        exchange=context.exchange,
        currency=context.currency,
        sector=context.sector,
        industry=context.industry,
        logo_url=context.logo_url,
        financials=context.raw_snapshot,
        template_key=context.template_key,
        generated_at=datetime.now(timezone.utc),
    )
    await _upsert_data(data, context, session)
    logger.info(
        "analysis phase 1 complete",
        extra={"ticker": ticker, "template_key": context.template_key},
    )
    return data


async def run_analyze(ticker: str, session: AsyncSession, force: bool = False) -> AnalysisResult:
    """Run Phase 2.5: independence detection + chart data extraction via Haiku.

    Uses cached Phase 1 data if available; runs Phase 1 first if needed.
    Returns cached AnalysisResult within TTL unless force=True.
    """
    if not force:
        cached = await _load_cached_analyze(ticker, session)
        if cached is not None:
            logger.info("returning cached analyze result", extra={"ticker": ticker})
            return cached

    logger.info("running analysis phase 2.5", extra={"ticker": ticker, "force": force})

    data = await _load_cached_data(ticker, session)
    if data is None:
        data = await run_data(ticker, session, force=False)

    sc = data.financials
    context = context_builder.StructuredContext(
        ticker=ticker,
        company_name=data.company_name,
        exchange=data.exchange,
        currency=data.currency,
        canonical_id=None,
        template_key=data.template_key,
        sector=data.sector,
        industry=data.industry,
        metrics_block=sc.get("metrics_block", ""),
        filing_excerpt=sc.get("filing_excerpt", ""),
        raw_snapshot=sc,
    )

    result_dict = await analyzer.analyze(context)
    analyzed_at = datetime.now(timezone.utc)

    result = AnalysisResult(
        ticker=ticker,
        independence=result_dict["independence"],
        chart_data=result_dict["chart_data"],
        analyzed_at=analyzed_at,
    )
    await _upsert_analyze(result, session)
    logger.info("analysis phase 2.5 complete", extra={"ticker": ticker})
    return result


async def run_report(ticker: str, session: AsyncSession, force: bool = False) -> AnalysisReport:
    """Run Phase 2: generate the written report via Sonnet (~30-90s).

    Uses cached Phase 1 data if available; otherwise runs Phase 1 first.
    Independence defaults to "independent" if Phase 2.5 has not been run.
    Returns cached AnalysisReport within TTL unless force=True.
    Raises ProviderUnavailableError if Phase 1 data is unavailable.
    """
    if not force:
        cached = await _load_cached_report(ticker, session)
        if cached is not None:
            logger.info("returning cached report", extra={"ticker": ticker})
            return cached

    logger.info("running analysis phase 2", extra={"ticker": ticker, "force": force})

    data = await _load_cached_data(ticker, session)
    if data is None:
        data = await run_data(ticker, session, force=False)

    independence = await _load_independence(ticker, session)

    sc = data.financials
    context = context_builder.StructuredContext(
        ticker=ticker,
        company_name=data.company_name,
        exchange=data.exchange,
        currency=data.currency,
        canonical_id=None,
        template_key=data.template_key,
        sector=data.sector,
        industry=data.industry,
        metrics_block=sc.get("metrics_block", ""),
        filing_excerpt=sc.get("filing_excerpt", ""),
        raw_snapshot=sc,
    )

    prompt_text, _ = prompt_loader.load(data.template_key)
    report_markdown = await report_generator.generate(
        context=context,
        prompt_template=prompt_text,
        report_template_key=data.template_key,
        independence=independence,
    )

    report = AnalysisReport(
        ticker=ticker,
        report_template=data.template_key,
        independence=independence,
        report_markdown=report_markdown,
        generated_at=datetime.now(timezone.utc),
    )
    await _upsert_report(report, session)
    logger.info("analysis phase 2 complete", extra={"ticker": ticker})
    return report


async def get_cached_data(ticker: str, session: AsyncSession) -> AnalysisData | None:
    return await _load_cached_data(ticker, session, ignore_ttl=True)


async def get_cached_analyze(ticker: str, session: AsyncSession) -> AnalysisResult | None:
    return await _load_cached_analyze(ticker, session, ignore_ttl=True)


async def get_cached_report(ticker: str, session: AsyncSession) -> AnalysisReport | None:
    return await _load_cached_report(ticker, session, ignore_ttl=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _load_cached_data(
    ticker: str,
    session: AsyncSession,
    ignore_ttl: bool = False,
) -> AnalysisData | None:
    result = await session.execute(
        select(AnalysisReportRow).where(AnalysisReportRow.ticker == ticker)
    )
    row = result.scalars().first()
    if row is None or not row.report_template:
        return None

    if not ignore_ttl:
        ttl = timedelta(days=settings.analysis_report_ttl_days)
        age = datetime.now(timezone.utc) - row.generated_at
        if age > ttl:
            logger.info("cached data is stale", extra={"ticker": ticker, "age_days": age.days})
            return None

    sc = row.structured_context or {}
    profile = sc.get("profile") or {}
    financials_sc = sc.get("financials") or {}

    return AnalysisData(
        ticker=row.ticker,
        company_name=profile.get("name") or row.ticker,
        exchange=profile.get("exchange"),
        currency=financials_sc.get("currency") or "USD",
        sector=profile.get("sector"),
        industry=profile.get("industry"),
        logo_url=sc.get("logo_url"),
        financials=sc,
        template_key=row.report_template,
        generated_at=row.generated_at,
    )


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
            logger.info("cached analyze result is stale", extra={"ticker": ticker, "age_days": age.days})
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
            logger.info("cached report is stale", extra={"ticker": ticker, "age_days": age.days})
            return None

    return AnalysisReport(
        ticker=row.ticker,
        report_template=row.report_template,
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
    return (row.independence if row and row.independence else "independent")


async def _upsert_data(
    data: AnalysisData,
    context: context_builder.StructuredContext,
    session: AsyncSession,
) -> None:
    values = {
        "ticker": data.ticker,
        "canonical_id": context.canonical_id,
        "report_template": data.template_key,
        "independence": None,
        "report_markdown": None,
        "report_generated_at": None,
        "analyzed_at": None,
        "structured_context": context.raw_snapshot,
        "chart_data": {},
        "generated_at": data.generated_at,
    }

    await session.execute(
        insert(AnalysisReportRow)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["ticker"],
            set_={
                "canonical_id": values["canonical_id"],
                "report_template": values["report_template"],
                "structured_context": values["structured_context"],
                "generated_at": values["generated_at"],
                # independence, chart_data, analyzed_at, report_* are NOT reset
            },
        )
    )
    await session.commit()


async def _upsert_analyze(result: AnalysisResult, session: AsyncSession) -> None:
    await session.execute(
        update(AnalysisReportRow)
        .where(AnalysisReportRow.ticker == result.ticker)
        .values(
            independence=result.independence,
            chart_data=result.chart_data,
            analyzed_at=result.analyzed_at,
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
