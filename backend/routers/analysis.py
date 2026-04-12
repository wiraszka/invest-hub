from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from services.db import get_analysis, upsert_analysis
from services.llm import classify_and_extract, generate_snapshot
from services.price import get_current_price
from services.sec import get_filing_sections, get_xbrl_facts

router = APIRouter()


def _enrich_chart_data(
    chart_data: dict, xbrl_data: dict, company_type: str, ticker: str
) -> tuple[dict, float | None]:
    """
    Populate chart fields derivable from XBRL + live price.
    Returns (enriched_chart_data, market_cap_usd).
    market_cap_usd is also stored at the top level of the analysis document.
    """
    chart_data = dict(chart_data)

    # Market cap = shares_outstanding × live price
    shares = xbrl_data.get("shares_outstanding")
    if shares is not None:
        try:
            price_data = get_current_price(ticker)
            market_cap: float | None = shares * price_data["price"]
        except Exception:
            market_cap = None
    else:
        market_cap = None

    # Net debt from XBRL is more reliable than LLM extraction
    net_debt = xbrl_data.get("net_debt")

    if market_cap is not None or net_debt is not None:
        chart_data["capital_structure"] = {
            "market_cap_usd": market_cap,
            "net_debt_usd": net_debt,
        }

    # Cash burn: derive from operating cash flow for pre-revenue companies
    if company_type == "pre-revenue":
        ocf = xbrl_data.get("operating_cash_flow")
        if ocf is not None:
            chart_data["cash_burn"] = {"annual_burn_usd": abs(ocf)}

    return chart_data, market_cap


@router.post("/api/analysis/{ticker}")
def trigger_analysis(ticker: str = Path(...)) -> dict:
    ticker = ticker.upper()

    try:
        filing_text = get_filing_sections(ticker)
        xbrl_data = get_xbrl_facts(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch SEC data: {e}")

    try:
        extraction = classify_and_extract(filing_text)
        company_type = extraction["company_type"]
        chart_data = extraction.get("charts", {})
        chart_data, market_cap_usd = _enrich_chart_data(chart_data, xbrl_data, company_type, ticker)
        snapshot = generate_snapshot(ticker, company_type, filing_text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM analysis failed: {e}")

    try:
        upsert_analysis(ticker, company_type, snapshot, chart_data, xbrl_data, market_cap_usd)
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
