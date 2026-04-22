from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path

from services.db import get_analysis, upsert_analysis
from services.fmp import get_financials, get_profile_description
from services.llm import (
    SNAPSHOT_MODEL,
    classify_and_extract,
    generate_snapshot,
)
from services.sec import (
    extract_10k_sections,
    fetch_filing_text,
    find_recent_annual,
    get_submissions,
    is_filing_stale,
    resolve_cik,
)
from services.sec_20f import extract_20f_sections
from services.sec_40f import fetch_40f_sections

router = APIRouter()


def _build_standard_charts(fmp_data: dict, company_type: str) -> tuple[dict, float | None]:
    chart_data: dict = {}
    metrics = fmp_data.get("metrics") or {}
    balance = fmp_data.get("balance_sheet") or {}

    market_cap = metrics.get("market_cap")
    net_debt = balance.get("net_debt")

    if market_cap is not None or net_debt is not None:
        chart_data["capital_structure"] = {
            "market_cap_usd": market_cap,
            "net_debt_usd": net_debt,
        }

    if company_type == "pre-revenue":
        cash_flow = fmp_data.get("cash_flow") or []
        if cash_flow:
            ocf = cash_flow[0].get("operating_cash_flow")
            if ocf is not None:
                chart_data["cash_burn"] = {"annual_burn_usd": abs(ocf)}

    return chart_data, market_cap


@router.post("/api/analysis/{ticker}")
def trigger_analysis(ticker: str = Path(...)) -> dict:
    ticker = ticker.upper()

    # ------------------------------------------------------------------
    # Step 1 — Resolve CIK (soft failure — pipeline continues without SEC)
    # ------------------------------------------------------------------
    has_sec = True
    cik_10: str | None = None
    form_type = "none"
    filing_date = "none"
    filing_recency = "none"
    sections_extracted = False
    filing_text = ""
    accession: str | None = None
    primary_doc: str | None = None

    try:
        cik_10 = resolve_cik(ticker)
    except Exception:
        has_sec = False

    # ------------------------------------------------------------------
    # Step 2 — Fetch submissions + detect annual filing type
    # ------------------------------------------------------------------
    if has_sec:
        try:
            submissions = get_submissions(cik_10)
            accession, primary_doc, form_type, filing_date = find_recent_annual(submissions)
        except Exception:
            has_sec = False

    # ------------------------------------------------------------------
    # Step 3 — Filing recency check
    # ------------------------------------------------------------------
    if has_sec:
        filing_recency = "stale" if is_filing_stale(filing_date) else "fresh"

    # ------------------------------------------------------------------
    # Step 4 — Extract filing sections (partial failure tolerated)
    # ------------------------------------------------------------------
    if has_sec:
        try:
            if form_type in ("40-F", "40-F/A"):
                filing_text = fetch_40f_sections(cik_10, accession)
            else:
                raw_text = fetch_filing_text(cik_10, accession, primary_doc)
                if form_type in ("20-F", "20-F/A"):
                    filing_text = extract_20f_sections(raw_text)
                else:
                    filing_text = extract_10k_sections(raw_text)
            sections_extracted = bool(filing_text.strip())
        except Exception:
            sections_extracted = False

    # ------------------------------------------------------------------
    # Step 5 — Fetch FMP financials (total failure tolerated)
    # ------------------------------------------------------------------
    fmp_data: dict = {}
    fmp_quality = "none"
    reporting_currency = "USD"
    try:
        result = get_financials(ticker)
        if result:
            fmp_data = result
            reporting_currency = fmp_data.get("currency", "USD")
            income = fmp_data.get("income") or []
            metrics_dict = fmp_data.get("metrics") or {}
            fmp_quality = "full" if (income and metrics_dict) else "partial"
    except Exception:
        fmp_quality = "none"

    # When no SEC filing, use FMP profile description as thin narrative fallback
    if not has_sec and not filing_text:
        try:
            desc = get_profile_description(ticker)
            if desc:
                filing_text = desc
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Step 6 — LLM Call 1: classify + industry-specific chart extraction
    # ------------------------------------------------------------------
    try:
        extraction = classify_and_extract(filing_text, fmp_data)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM classification failed: {e}")

    company_type = extraction["company_type"]
    company_independence = extraction["company_independence"]
    llm_charts = extraction.get("charts", {})

    standard_charts, market_cap_usd = _build_standard_charts(fmp_data, company_type)
    chart_data = {**llm_charts, **standard_charts}

    # ------------------------------------------------------------------
    # Step 7 — LLM Call 2: Company Snapshot
    # ------------------------------------------------------------------
    try:
        snapshot = generate_snapshot(
            ticker, company_type, filing_text, fmp_data, company_independence
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
        "sections_extracted": sections_extracted,
        "data_source": "SEC + FMP" if has_sec else "FMP only",
        "fmp_financials": fmp_quality,
        "reporting_currency": reporting_currency,
        "company_independence": company_independence,
        "llm_model": SNAPSHOT_MODEL,
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
            fmp_data,
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
        "fmp_data": fmp_data,
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
