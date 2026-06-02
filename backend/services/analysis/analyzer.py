"""Phase 2.5 analyzer: independence detection + chart data extraction.

Template classification lives in context_builder._classify_template() (pure Python).
This module focuses only on:
  1. Independence detection (regex first, Groq fallback when inconclusive)
  2. Chart data extraction (keyword-targeted filing excerpt, scoped to template)
"""

from __future__ import annotations

import json
import logging
import re

from services.analysis.context_builder import StructuredContext
from services.llm import CLASSIFY_MODEL_GROQ, get_groq_client

logger = logging.getLogger(__name__)

_VALID_INDEPENDENCE = frozenset(
    {"independent", "possibly_acquired", "confirmed_inactive"}
)

_INACTIVE_RE = re.compile(
    r"\b(acquired\s+by|been\s+acquired|completed\s+(?:the\s+)?acquisition|"
    r"delisted|ceased\s+operations|dissolved|liquidat|wound\s+up|"
    r"no\s+longer\s+(?:operates|trading))\b",
    re.IGNORECASE,
)
_PENDING_RE = re.compile(
    r"\b(pending\s+acquisition|proposed\s+merger|going[\s\-]concern|"
    r"SPAC\s+(?:combination|merger)|definitive\s+agreement|"
    r"plan\s+of\s+arrangement|subject\s+to\s+(?:a\s+)?(?:merger|acquisition))\b",
    re.IGNORECASE,
)

# Chart data fields available per template
_CHART_FIELDS: dict[str, list[str]] = {
    "mining": [
        "revenue_by_segment",
        "reserves_by_asset",
        "production_mix",
        "nav_vs_ev",
    ],
    "pre_revenue_mining": ["reserves_by_asset", "production_mix", "nav_vs_ev"],
    "energy": ["revenue_by_segment", "production_mix"],
    "general": ["revenue_by_segment"],
    "tech": ["revenue_by_segment"],
    "financial": ["revenue_by_segment"],
    "biotech": ["revenue_by_segment"],
    "pre_revenue": [],
    "pre_revenue_biotech": [],
    "etf": [],
}

# Filing excerpt search keywords per template (searched in order; first match wins)
_SEARCH_KEYWORDS: dict[str, list[str]] = {
    "mining": [
        "segment",
        "reserves",
        "mineral resource",
        "production by",
        "net asset value",
        "nav",
    ],
    "pre_revenue_mining": [
        "reserves",
        "mineral resource",
        "net asset value",
        "nav",
        "exploration",
    ],
    "energy": ["segment", "production", "reserves", "barrels"],
    "general": ["segment", "business unit", "product line", "revenue breakdown"],
    "tech": ["segment", "product line", "cloud", "subscription revenue"],
    "financial": ["segment", "business line", "geographic"],
    "biotech": ["segment", "pipeline", "product revenue"],
}

_FIELD_DESCRIPTIONS = {
    "revenue_by_segment": (
        '"revenue_by_segment": {"Segment Name": <revenue_usd>}'
        " if segment revenue is explicitly disclosed; null otherwise"
    ),
    "reserves_by_asset": (
        '"reserves_by_asset": {"Asset Name": <reserves_oz_or_tonnes>}'
        " if mineral reserves by asset are disclosed; null otherwise"
    ),
    "production_mix": (
        '"production_mix": {"Commodity": <production_value>}'
        " if production breakdown by commodity is disclosed; null otherwise"
    ),
    "nav_vs_ev": (
        '"nav_vs_ev": {"nav_usd": <number>, "ev_usd": <number or null>}'
        " if a NAV estimate is disclosed; null otherwise"
    ),
}


def _detect_independence_regex(text: str) -> str | None:
    """Return independence classification from regex, or None if inconclusive."""
    if _INACTIVE_RE.search(text):
        return "confirmed_inactive"
    if _PENDING_RE.search(text):
        return "possibly_acquired"
    return None


def _extract_targeted_window(
    filing_text: str, template_key: str, window: int = 1_500
) -> str:
    """Find the first keyword match and return a surrounding window of text."""
    keywords = _SEARCH_KEYWORDS.get(template_key, [])
    for kw in keywords:
        idx = filing_text.lower().find(kw.lower())
        if idx != -1:
            start = max(0, idx - 100)
            return filing_text[start : start + window]
    return filing_text[:window]


async def analyze(context: StructuredContext) -> dict:
    """Detect independence and extract chart data for a company.

    Returns a dict with keys: independence (str), chart_data (dict).
    Falls back to safe defaults on LLM errors.
    """
    filing_text = context.filing_excerpt
    chart_fields = _CHART_FIELDS.get(context.template_key, [])

    independence: str | None = None
    if filing_text:
        independence = _detect_independence_regex(filing_text)

    if not chart_fields and independence is not None:
        logger.info(
            "skipping LLM — regex resolved independence, no chart fields for template",
            extra={"ticker": context.ticker, "template": context.template_key},
        )
        return {"independence": independence, "chart_data": {}}

    filing_window = (
        _extract_targeted_window(filing_text, context.template_key)
        if filing_text
        else ""
    )

    independence_rule = (
        f'independence: must be exactly "{independence}" (already determined)'
        if independence is not None
        else 'independence: one of "independent", "possibly_acquired", "confirmed_inactive"'
    )

    chart_schema_lines = "\n".join(
        f"    {_FIELD_DESCRIPTIONS[f]}"
        for f in chart_fields
        if f in _FIELD_DESCRIPTIONS
    )
    chart_block = (
        f'"chart_data": {{\n{chart_schema_lines}\n  }}'
        if chart_fields
        else '"chart_data": {}'
    )

    system_prompt = (
        "You are a financial analyst extracting structured data from company filings.\n\n"
        "Return a JSON object with this exact structure:\n"
        "{\n"
        f'  "{independence_rule}",\n'
        f"  {chart_block}\n"
        "}\n\n"
        "Extract only values explicitly stated in the filing excerpt. "
        "Use null for any field not found. "
        "Respond with only the JSON object. No explanation, no markdown."
    )

    user_content = (
        f"Company: {context.ticker} (template: {context.template_key})\n\n"
        f"Financial summary:\n{context.metrics_block[:800]}\n\n"
        f"Filing excerpt:\n{filing_window}"
    )

    client = get_groq_client()
    result: dict = {}
    try:
        response = await client.chat.completions.create(
            model=CLASSIFY_MODEL_GROQ,
            max_tokens=512,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        result = _parse_json(
            response.choices[0].message.content.strip(), context.ticker
        )
    except Exception as exc:
        logger.warning(
            "analyzer LLM call failed",
            extra={"ticker": context.ticker, "error": str(exc)},
        )

    final_independence = result.get("independence") or independence or "independent"
    if final_independence not in _VALID_INDEPENDENCE:
        final_independence = independence or "independent"

    chart_data = result.get("chart_data") or {}

    logger.info(
        "analysis complete",
        extra={
            "ticker": context.ticker,
            "template": context.template_key,
            "independence": final_independence,
        },
    )
    return {"independence": final_independence, "chart_data": chart_data}


def _parse_json(text: str, ticker: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        logger.warning("no JSON in analyzer response", extra={"ticker": ticker})
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        logger.warning(
            "JSON parse failed in analyzer response", extra={"ticker": ticker}
        )
        return {}
