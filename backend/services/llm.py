from __future__ import annotations

import json
import os
import re

import anthropic
from dotenv import load_dotenv

load_dotenv()

CLASSIFY_MODEL = "claude-haiku-4-5-20251001"
SNAPSHOT_MODEL = "claude-sonnet-4-6"
LLM_KNOWLEDGE_CUTOFF = "August 2025"

COMPANY_TYPES = frozenset(
    {"pre-revenue", "revenue-generating", "mining-company", "oil-gas-stock"}
)
INDEPENDENCE_VALUES = frozenset(
    {"independent", "possibly_acquired", "confirmed_inactive"}
)

_CLASSIFY_PROMPT = """You are a financial analyst. Given a company narrative excerpt and structured financial data, return a JSON object with exactly this structure:

{
  "company_type": "<one of: pre-revenue, revenue-generating, mining-company, oil-gas-stock>",
  "company_independence": "<one of: independent, possibly_acquired, confirmed_inactive>",
  "charts": {
    "revenue_by_segment": null,
    "reserves_by_asset": null,
    "production_mix": null,
    "nav_vs_ev": null
  }
}

Rules:
- company_type: classify as "mining-company" only for companies primarily engaged in mineral extraction or exploration. Classify as "oil-gas-stock" only for companies primarily engaged in oil or natural gas production. Use "pre-revenue" for companies with no meaningful revenue. Use "revenue-generating" for all others.
- company_independence: set to "confirmed_inactive" if the filing explicitly states the company has been acquired, merged into another entity, ceased operations, or been delisted. Set to "possibly_acquired" if the filing contains language suggesting a pending acquisition, merger agreement, going-concern doubt, or SPAC pre-combination status. Set to "independent" otherwise.
- revenue_by_segment: populate only if the narrative discloses revenue broken down by named business segment. Format: {"Segment Name": <revenue_usd>, ...}. Set to null if not disclosed or not applicable.
- reserves_by_asset: populate only for mining-company if the narrative discloses mineral reserves by named asset or mine. Format: {"Asset Name": <reserves_oz_or_tonnes>, ...}. Set to null otherwise.
- production_mix: populate only for mining-company or oil-gas-stock if the narrative discloses production by commodity or asset type. Format: {"Commodity": <production_value>, ...}. Set to null otherwise.
- nav_vs_ev: populate only for mining-company if the narrative discloses a net asset value (NAV) estimate. Format: {"nav_usd": <number>, "ev_usd": <number or null>}. Set to null otherwise.

Note: standard financial metrics (capital structure, margins, cash burn) are sourced directly from the structured financial data — do not attempt to extract them from the narrative.
If the narrative is brief or absent, classify using the financial data alone and leave all chart fields null.

Respond with only the JSON object. No explanation, no markdown."""

_SNAPSHOT_PROMPT = """You are a financial analyst writing a Company Snapshot for an investment research platform.

Based on the company narrative and structured financial data provided, write a concise Company Snapshot of 5–7 bullet points. Each bullet must be a single, factual sentence.

Cover the following where relevant:
- What the company does and its primary business
- Where it operates (geography, markets, or key assets)
- Key products, services, commodities, or projects
- Financial position — reference specific figures from the financial data (e.g. revenue, margins, net debt, market cap) where meaningful
- Notable risks, competitive position, or recent developments

Rules:
- Use present tense
- Be factual and concise — no opinions, target prices, or buy/sell recommendations
- Start each bullet with "- "
- Do not include headers, section titles, or introductory text
- Do not repeat information across bullets
- Prefer figures from the structured financial data over estimates in the narrative"""

_MERGER_NOTICE = (
    "\n\n---\n**Note:** Filing content suggests this company may have been acquired, "
    "merged, or is no longer independent — verify current status before acting on this analysis."
)


_anthropic_client: anthropic.Anthropic | None = None


def _client() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _anthropic_client = anthropic.Anthropic(api_key=key, timeout=300.0)
    return _anthropic_client


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from a response string."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in LLM response: {text[:200]}")
    return json.loads(match.group())


def _format_fmp_financials(fmp_data: dict) -> str:
    """Format FMP financial data as a concise text block for LLM context."""
    lines = [f"Reporting currency: {fmp_data.get('currency', 'USD')}"]

    income = fmp_data.get("income", [])
    if income:
        latest = income[0]
        year = latest.get("year", "")
        lines.append(f"\nLatest annual financials ({year}):")
        for label, key in [
            ("  Revenue", "revenue"),
            ("  Gross profit", "gross_profit"),
            ("  EBITDA", "ebitda"),
            ("  Net income", "net_income"),
        ]:
            val = latest.get(key)
            if val is not None:
                lines.append(f"{label}: {val:,.0f}")

    bs = fmp_data.get("balance_sheet", {})
    if bs:
        lines.append("\nBalance sheet (latest):")
        for label, key in [
            ("  Cash", "cash"),
            ("  Total debt", "total_debt"),
            ("  Net debt", "net_debt"),
            ("  Total equity", "total_equity"),
        ]:
            val = bs.get(key)
            if val is not None:
                lines.append(f"{label}: {val:,.0f}")

    cf = fmp_data.get("cash_flow", [])
    if cf:
        latest_cf = cf[0]
        lines.append(f"\nCash flow ({latest_cf.get('year', '')}):")
        for label, key in [
            ("  Operating cash flow", "operating_cash_flow"),
            ("  Free cash flow", "free_cash_flow"),
        ]:
            val = latest_cf.get(key)
            if val is not None:
                lines.append(f"{label}: {val:,.0f}")

    metrics = fmp_data.get("metrics", {})
    if metrics:
        lines.append("\nKey metrics:")
        for label, key in [
            ("  Market cap", "market_cap"),
            ("  Enterprise value", "enterprise_value"),
            ("  P/E ratio", "pe_ratio"),
            ("  EV/EBITDA", "ev_ebitda"),
        ]:
            val = metrics.get(key)
            if val is not None:
                lines.append(f"{label}: {val:,.1f}" if isinstance(val, float) else f"{label}: {val:,.0f}")

    return "\n".join(lines)


def classify_and_extract(filing_text: str, fmp_financials: dict) -> dict:
    """
    Call #1 — Haiku.
    Returns {"company_type": str, "company_independence": str, "charts": dict}.
    """
    client = _client()
    fmp_block = _format_fmp_financials(fmp_financials)
    user_content = (
        f"Structured financial data:\n{fmp_block}\n\n"
        f"Company narrative excerpt:\n{filing_text}"
    )
    message = client.messages.create(
        model=CLASSIFY_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": f"{_CLASSIFY_PROMPT}\n\n{user_content}"}],
    )
    raw = message.content[0].text.strip()
    result = _extract_json(raw)

    company_type = result.get("company_type", "revenue-generating").lower()
    if company_type not in COMPANY_TYPES:
        company_type = "revenue-generating"
    result["company_type"] = company_type

    independence = result.get("company_independence", "independent").lower()
    if independence not in INDEPENDENCE_VALUES:
        independence = "independent"
    result["company_independence"] = independence

    return result


def generate_snapshot(
    ticker: str,
    company_type: str,
    filing_text: str,
    fmp_financials: dict,
    company_independence: str = "independent",
) -> str:
    """
    Call #2 — Sonnet.
    Returns the Company Snapshot markdown string.
    Appends a merger/acquisition notice if company_independence is not "independent".
    """
    client = _client()
    fmp_block = _format_fmp_financials(fmp_financials)
    user_content = (
        f"Company ticker: {ticker}\n\n"
        f"Structured financial data:\n{fmp_block}\n\n"
        f"Company narrative (annual filing excerpt):\n{filing_text}"
    )
    message = client.messages.create(
        model=SNAPSHOT_MODEL,
        max_tokens=1024,
        system=_SNAPSHOT_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    snapshot = message.content[0].text

    if company_independence != "independent":
        snapshot += _MERGER_NOTICE

    return snapshot
