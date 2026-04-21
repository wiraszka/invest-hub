"""
20-F filing support: section extraction and IFRS XBRL fact retrieval.

20-F structure equivalent to 10-K sections:
  - Item 4  "Information on the Company"  ≈ 10-K Item 1  (Business)
  - Item 3D "Risk Factors"                ≈ 10-K Item 1A (Risk Factors)
  - Item 5  "Operating and Financial..."  ≈ 10-K Item 7  (MD&A)
"""

from __future__ import annotations

import re

from services.sec import _detect_currency, _extract_sections, _latest_value

_SECTION_PATTERNS_20F = [
    re.compile(r"item\s+4\.?\s+information\s+on\s+the\s+company", re.I),
    re.compile(r"item\s+3d\.?\s+risk\s+factors", re.I),
    re.compile(r"item\s+3\.?\s+[a-z\s]*risk\s+factors", re.I),
    re.compile(r"item\s+5\.?\s+operating\s+and\s+financial", re.I),
]

# IFRS concepts mapped to the same keys used in the us-gaap pipeline
IFRS_XBRL_FACTS: dict[str, list[str]] = {
    "cash": [
        "CashAndCashEquivalents",
        "CashAndBankBalancesAtCentralBanks",
    ],
    "total_debt": [
        "Borrowings",
        "LongtermBorrowings",
        "ShorttermBorrowingsAndCurrentPortionOfLongtermBorrowings",
    ],
    "revenue": [
        "Revenue",
        "RevenueFromContractsWithCustomers",
    ],
    "net_income": [
        "ProfitLoss",
        "ProfitLossAttributableToOwnersOfParent",
    ],
    "operating_cash_flow": [
        "CashFlowsFromUsedInOperatingActivities",
        "CashFlowsFromOperations",
    ],
    "shares_outstanding": [
        "NumberOfSharesOutstanding",
        "NumberOfOrdinarySharesOutstanding",
    ],
}


def extract_20f_sections(text: str) -> str:
    """Extract Items 4, 3D, and 5 from 20-F plain text."""
    return _extract_sections(text, _SECTION_PATTERNS_20F)


def get_ifrs_xbrl_facts(raw_facts: dict, annual_forms: set[str]) -> tuple[dict, str]:
    """
    Extract financial facts from the ifrs-full XBRL namespace.
    Returns (facts_dict, reporting_currency).
    """
    ifrs = raw_facts.get("facts", {}).get("ifrs-full", {})
    result: dict[str, float | None] = {}

    for key, concepts in IFRS_XBRL_FACTS.items():
        result[key] = _latest_value(ifrs, concepts, annual_forms, any_currency=True)

    reporting_currency = _detect_currency(ifrs, IFRS_XBRL_FACTS, annual_forms)
    result["net_debt"] = None  # derived by caller

    return result, reporting_currency
