from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path

from services.db import get_analysis, upsert_analysis
from services.llm import (
    LLM_KNOWLEDGE_CUTOFF,
    SNAPSHOT_MODEL,
    classify_and_extract,
    generate_snapshot,
)
from services.price import get_current_price
from services.sec import (
    extract_10k_sections,
    fetch_filing_text,
    find_recent_annual,
    get_submissions,
    get_xbrl_facts,
    is_filing_stale,
    resolve_cik,
)
from services.sec_20f import extract_20f_sections
from services.sec_40f import fetch_40f_sections

router = APIRouter()


def _enrich_chart_data(
    chart_data: dict, xbrl_data: dict, company_type: str, ticker: str
) -> tuple[dict, float | None]:
    chart_data = dict(chart_data)

    shares = xbrl_data.get("shares_outstanding")
    if shares is not None:
        try:
            price_data = get_current_price(ticker)
            market_cap: float | None = shares * price_data["price"]
        except Exception:
            market_cap = None
    else:
        market_cap = None

    net_debt = xbrl_data.get("net_debt")

    if market_cap is not None or net_debt is not None:
        chart_data["capital_structure"] = {
            "market_cap_usd": market_cap,
            "net_debt_usd": net_debt,
        }

    if company_type == "pre-revenue":
        ocf = xbrl_data.get("operating_cash_flow")
        if ocf is not None:
            chart_data["cash_burn"] = {"annual_burn_usd": abs(ocf)}

    return chart_data, market_cap


@router.post("/api/analysis/{ticker}")
def trigger_analysis(ticker: str = Path(...)) -> dict:
    ticker = ticker.upper()

    # ------------------------------------------------------------------
    # Step 1 — Resolve CIK
    # ------------------------------------------------------------------
    try:
        cik_10 = resolve_cik(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to resolve CIK: {e}")

    # ------------------------------------------------------------------
    # Step 2 — Fetch submissions + detect annual filing type
    # ------------------------------------------------------------------
    try:
        submissions = get_submissions(cik_10)
        accession, primary_doc, form_type, filing_date = find_recent_annual(submissions)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch SEC submissions: {e}"
        )

    # ------------------------------------------------------------------
    # Step 3 — Filing recency check (warning only, does not abort)
    # ------------------------------------------------------------------
    filing_recency = "stale" if is_filing_stale(filing_date) else "fresh"

    # ------------------------------------------------------------------
    # Step 4 — Extract filing sections (partial failure tolerated)
    # ------------------------------------------------------------------
    sections_extracted = False
    filing_text = ""
    try:
        if form_type in ("40-F", "40-F/A"):
            # Primary doc is a thin cover; actual content is in EX-99.1 (AIF)
            filing_text = fetch_40f_sections(cik_10, accession)
        else:
            raw_text = fetch_filing_text(cik_10, accession, primary_doc)
            if form_type in ("20-F", "20-F/A"):
                filing_text = extract_20f_sections(raw_text)
            else:
                filing_text = extract_10k_sections(raw_text)
        sections_extracted = bool(filing_text.strip())
    except Exception:
        # Proceed with empty text — LLM will do its best with no filing context
        sections_extracted = False

    # ------------------------------------------------------------------
    # Step 5 — Fetch XBRL facts (total failure tolerated)
    # ------------------------------------------------------------------
    xbrl_data: dict = {
        "cash": None,
        "total_debt": None,
        "revenue": None,
        "net_income": None,
        "operating_cash_flow": None,
        "shares_outstanding": None,
        "net_debt": None,
    }
    xbrl_quality = "none"
    reporting_currency = "USD"
    try:
        xbrl_data, reporting_currency = get_xbrl_facts(cik_10, form_type)
        populated = sum(1 for v in xbrl_data.values() if v is not None)
        if populated == len(xbrl_data):
            xbrl_quality = "full"
        elif populated > 0:
            xbrl_quality = "partial"
        else:
            xbrl_quality = "none"
    except Exception:
        xbrl_quality = "none"

    # ------------------------------------------------------------------
    # Step 6 — LLM Call 1: classify + chart data extraction
    # ------------------------------------------------------------------
    try:
        extraction = classify_and_extract(filing_text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM classification failed: {e}")

    company_type = extraction["company_type"]
    company_independence = extraction["company_independence"]
    chart_data = extraction.get("charts", {})
    chart_data, market_cap_usd = _enrich_chart_data(
        chart_data, xbrl_data, company_type, ticker
    )

    # ------------------------------------------------------------------
    # Step 7 — LLM Call 2: Company Snapshot
    # ------------------------------------------------------------------
    try:
        snapshot = generate_snapshot(
            ticker, company_type, filing_text, company_independence
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM snapshot failed: {e}")

    # ------------------------------------------------------------------
    # Step 8 — Assemble data_integrity object
    # ------------------------------------------------------------------
    analysis_timestamp = datetime.now(timezone.utc)
    data_integrity = {
        "filing_type": form_type,
        "filing_date": filing_date,
        "filing_recency": filing_recency,
        "reporting_currency": reporting_currency,
        "xbrl_quality": xbrl_quality,
        "sections_extracted": sections_extracted,
        "company_independence": company_independence,
        "llm_model": SNAPSHOT_MODEL,
        "llm_knowledge_cutoff": LLM_KNOWLEDGE_CUTOFF,
        "analysis_timestamp": analysis_timestamp.isoformat(),
    }

    # ------------------------------------------------------------------
    # Step 9 — Store + return
    # ------------------------------------------------------------------
    try:
        upsert_analysis(
            ticker,
            company_type,
            snapshot,
            chart_data,
            xbrl_data,
            market_cap_usd,
            data_integrity,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to store analysis: {e}")

    return {
        "ticker": ticker,
        "company_type": company_type,
        "snapshot": snapshot,
        "chart_data": chart_data,
        "xbrl_data": xbrl_data,
        "market_cap_usd": market_cap_usd,
        "data_integrity": data_integrity,
        "updated_at": analysis_timestamp.isoformat(),
    }


@router.get("/api/analysis/{ticker}")
def fetch_analysis(ticker: str = Path(...)) -> dict:
    ticker = ticker.upper()
    doc = get_analysis(ticker)
    if doc is None:
        raise HTTPException(status_code=404, detail="No analysis found for this ticker")
    return doc
