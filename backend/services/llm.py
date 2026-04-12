from __future__ import annotations

import json
import os
import re

import anthropic
from dotenv import load_dotenv

from services.db import get_prompt

load_dotenv()

CLASSIFY_MODEL = "claude-haiku-4-5-20251001"
SNAPSHOT_MODEL = "claude-sonnet-4-6"

COMPANY_TYPES = frozenset({"pre-revenue", "revenue-generating", "mining-company", "oil-gas-stock"})

_CLASSIFY_PROMPT = """You are a financial analyst. Given a 10-K filing excerpt, return a JSON object with exactly this structure:

{
  "company_type": "<one of: pre-revenue, revenue-generating, mining-company, oil-gas-stock>",
  "charts": {
    "capital_structure": null,
    "revenue_by_segment": null,
    "cash_burn": null
  }
}

Rules:
- company_type: classify as "mining-company" only for companies primarily engaged in mineral extraction or exploration. Classify as "oil-gas-stock" only for companies primarily engaged in oil or natural gas production. Use "pre-revenue" for companies with no meaningful revenue. Use "revenue-generating" for all others.
- capital_structure: always populate if market cap or share count is disclosed. Format: {"market_cap_usd": <number or null>, "net_debt_usd": <number or null>}. Use null for unknown values.
- revenue_by_segment: populate only if the filing discloses revenue broken down by named business segment. Format: {"Segment Name": <revenue_usd>, ...}. Set to null if not applicable or not disclosed.
- cash_burn: populate only for pre-revenue companies if quarterly or annual cash burn is disclosed. Format: {"annual_burn_usd": <number>}. Set to null otherwise.

Respond with only the JSON object. No explanation, no markdown."""


def _client(model: str) -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=key, timeout=300.0)


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from a response string."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in LLM response: {text[:200]}")
    return json.loads(match.group())


def classify_and_extract(filing_text: str) -> dict:
    """
    Call #1 — Haiku.
    Returns {"company_type": str, "charts": dict}.
    """
    client = _client(CLASSIFY_MODEL)
    message = client.messages.create(
        model=CLASSIFY_MODEL,
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": f"{_CLASSIFY_PROMPT}\n\nFiling excerpt:\n{filing_text}",
            }
        ],
    )
    raw = message.content[0].text.strip()
    result = _extract_json(raw)

    # Normalise company_type with a safe fallback
    company_type = result.get("company_type", "revenue-generating").lower()
    if company_type not in COMPANY_TYPES:
        company_type = "revenue-generating"
    result["company_type"] = company_type

    return result


def generate_snapshot(ticker: str, company_type: str, filing_text: str) -> str:
    """
    Call #2 — Sonnet.
    Returns the Company Snapshot markdown section.
    """
    system_prompt = get_prompt(company_type)
    if system_prompt is None:
        raise ValueError(f"No prompt found in database for company type: {company_type}")

    client = _client(SNAPSHOT_MODEL)
    message = client.messages.create(
        model=SNAPSHOT_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Company ticker: {ticker}\n\n"
                    f"10-K Filing Excerpt (Item 1 – Business, Item 7 – MD&A):\n\n{filing_text}"
                ),
            }
        ],
    )
    return message.content[0].text
