"""
Seed LLM prompts from backend/LLM-prompts/ into MongoDB.

Usage (from backend/ directory):
    python scripts/seed_prompts.py
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from services.db import upsert_prompt  # noqa: E402 — load_dotenv must run first

PROMPTS_DIR = Path(__file__).parent.parent / "LLM-prompts"
COMPANY_TYPES = ["pre-revenue", "revenue-generating", "mining-company", "oil-gas-stock"]


def main() -> None:
    for company_type in COMPANY_TYPES:
        path = PROMPTS_DIR / company_type
        if not path.exists():
            print(f"SKIP  {company_type} — file not found at {path}")
            continue
        content = path.read_text()
        upsert_prompt(company_type, content)
        print(f"OK    {company_type} ({len(content):,} chars)")


if __name__ == "__main__":
    main()
