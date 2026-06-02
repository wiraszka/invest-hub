"""SEC filing fetch-and-cache service.

Phase 2 of the research pipeline.  Fetches the most recent annual filing
(10-K / 20-F / 40-F) from SEC EDGAR, parses it into separate item sections,
and persists the result in the ``sec_filings`` table with a one-row-per-ticker
upsert.

TTLs
----
- Normal filing:   ~18 months (driven by ``is_filing_stale()`` in sec.py).
- NOT_FOUND sentinel: 7 days — if EDGAR has no record for a ticker (e.g. a
  Canadian company that doesn't file with the SEC), a sentinel row is stored
  so the pipeline doesn't hammer EDGAR on every run.  After 7 days the
  sentinel expires and one retry is attempted.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.pg_models import SecFilingRow
from models.market_data import FilingContext
from services import sec

logger = logging.getLogger(__name__)

# Sentinel form_type written when EDGAR cannot find the ticker
_NOT_FOUND = "NOT_FOUND"
_NOT_FOUND_TTL_DAYS = 7


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def fetch_and_store(ticker: str, session: AsyncSession) -> FilingContext:
    """Fetch the most recent annual filing from EDGAR and persist it.

    Always re-fetches from EDGAR (force semantics).  The caller is responsible
    for checking ``get_cached`` first when a cached result is acceptable.

    If EDGAR has no record for the ticker (e.g. a non-US company that doesn't
    file with the SEC), a NOT_FOUND sentinel row is stored so subsequent calls
    within the TTL skip EDGAR automatically.  The returned ``FilingContext``
    will have ``form_type == "NOT_FOUND"`` and empty item sections in that case.

    Raises:
        requests.HTTPError: on unrecoverable network / EDGAR errors.
    """
    try:
        cik, accession, primary_doc, form_type, filing_date = await _fetch_from_edgar(
            ticker
        )
    except ValueError as exc:
        # Ticker not in EDGAR or no annual filing found — store sentinel
        logger.info(
            "SEC EDGAR: no filing found — storing NOT_FOUND sentinel",
            extra={"ticker": ticker, "reason": str(exc)},
        )
        ctx = await _store_not_found(ticker, session)
        return ctx

    ctx = FilingContext(
        ticker=ticker,
        form_type=form_type,
        accession_number=accession,
        filing_date=filing_date,
        item_1="",
        item_1a="",
        item_7="",
        fetched_at=datetime.now(timezone.utc),
    )

    if form_type in ("10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"):
        text = await asyncio.to_thread(
            sec.fetch_filing_text, cik, accession, primary_doc
        )
        item_1, item_1a, item_7 = sec.extract_10k_items(text)
        ctx = ctx.model_copy(
            update={"item_1": item_1, "item_1a": item_1a, "item_7": item_7}
        )
    else:
        logger.warning(
            "Unsupported form type — skipping section extraction",
            extra={"ticker": ticker, "form_type": form_type},
        )

    await _upsert(session, ctx)
    logger.info(
        "SEC filing stored",
        extra={
            "ticker": ticker,
            "form_type": form_type,
            "filing_date": filing_date,
        },
    )
    return ctx


async def get_cached(ticker: str, session: AsyncSession) -> FilingContext | None:
    """Return the cached filing for ``ticker``, or None if not yet stored.

    - Returns a ``FilingContext`` with ``form_type == "NOT_FOUND"`` if a
      fresh (≤ 7 days) sentinel is stored — the caller should treat this as
      "no filing available, don't retry yet."
    - Returns ``None`` if no row exists *or* a stale NOT_FOUND sentinel is
      found — the caller should re-fetch from EDGAR.
    """
    result = await session.execute(
        select(SecFilingRow).where(SecFilingRow.ticker == ticker)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    if row.form_type == _NOT_FOUND:
        age = datetime.now(timezone.utc) - row.fetched_at
        if age <= timedelta(days=_NOT_FOUND_TTL_DAYS):
            # Fresh sentinel — skip EDGAR, return sentinel as context
            return _row_to_model(row)
        # Stale sentinel — allow one more attempt
        return None

    return _row_to_model(row)


def is_not_found(filing: FilingContext | None) -> bool:
    """Return True if ``filing`` is a NOT_FOUND sentinel (no items available)."""
    return filing is not None and filing.form_type == _NOT_FOUND


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _fetch_from_edgar(
    ticker: str,
) -> tuple[str, str, str, str, str]:
    """Return (cik, accession, primary_doc, form_type, filing_date).

    Raises ValueError if the ticker is not in EDGAR or has no annual filing.
    """
    cik = await asyncio.to_thread(sec.resolve_cik, ticker)
    submissions = await asyncio.to_thread(sec.get_submissions, cik)
    accession, primary_doc, form_type, filing_date = sec.find_recent_annual(submissions)
    return cik, accession, primary_doc, form_type, filing_date


async def _store_not_found(ticker: str, session: AsyncSession) -> FilingContext:
    """Write a NOT_FOUND sentinel row and return the corresponding FilingContext."""
    now = datetime.now(timezone.utc)
    ctx = FilingContext(
        ticker=ticker,
        form_type=_NOT_FOUND,
        accession_number="",
        filing_date=str(date.today()),
        item_1="",
        item_1a="",
        item_7="",
        fetched_at=now,
    )
    await _upsert(session, ctx)
    return ctx


async def _upsert(session: AsyncSession, ctx: FilingContext) -> None:
    filing_date = date.fromisoformat(ctx.filing_date)
    stmt = (
        pg_insert(SecFilingRow)
        .values(
            ticker=ctx.ticker,
            form_type=ctx.form_type,
            accession_number=ctx.accession_number,
            filing_date=filing_date,
            item_1=ctx.item_1,
            item_1a=ctx.item_1a,
            item_7=ctx.item_7,
            fetched_at=ctx.fetched_at,
        )
        .on_conflict_do_update(
            index_elements=["ticker"],
            set_={
                "form_type": ctx.form_type,
                "accession_number": ctx.accession_number,
                "filing_date": filing_date,
                "item_1": ctx.item_1,
                "item_1a": ctx.item_1a,
                "item_7": ctx.item_7,
                "fetched_at": ctx.fetched_at,
            },
        )
    )
    await session.execute(stmt)
    await session.commit()


def _row_to_model(row: SecFilingRow) -> FilingContext:
    return FilingContext(
        ticker=row.ticker,
        form_type=row.form_type,
        accession_number=row.accession_number,
        filing_date=str(row.filing_date),
        item_1=row.item_1 or "",
        item_1a=row.item_1a or "",
        item_7=row.item_7 or "",
        fetched_at=row.fetched_at,
    )
