from __future__ import annotations

import os

import anthropic
from dotenv import load_dotenv

from services.db import get_prompt

load_dotenv()

MODEL = "claude-opus-4-6"
MAX_TOKENS = 8000

COMPANY_TYPES = frozenset({"pre-revenue", "revenue-generating", "mining-company", "oil-gas-stock"})


def _client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=key)


def classify_company(filing_text: str) -> str:
    message = _client().messages.create(
        model=MODEL,
        max_tokens=16,
        messages=[
            {
                "role": "user",
                "content": (
                    "Classify this company into exactly one of these four categories based on its SEC filing:\n"
                    "- pre-revenue\n"
                    "- revenue-generating\n"
                    "- mining-company\n"
                    "- oil-gas-stock\n\n"
                    "Respond with only the category name, nothing else.\n\n"
                    f"Filing text (excerpt):\n{filing_text[:20_000]}"
                ),
            }
        ],
    )
    result = message.content[0].text.strip().lower()
    return result if result in COMPANY_TYPES else "revenue-generating"


def run_analysis(ticker: str, company_type: str, filing_text: str) -> str:
    system_prompt = get_prompt(company_type)
    if system_prompt is None:
        raise ValueError(f"No prompt found in database for company type: {company_type}")

    message = _client().messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Company ticker: {ticker}\n\n"
                    f"10-K Filing Text:\n\n{filing_text}"
                ),
            }
        ],
    )
    return message.content[0].text
