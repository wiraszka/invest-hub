"""
40-F filing support: section extraction for Canadian MJDS filers.

Canadian companies cross-listed on US exchanges file 40-F annually under the
Multijurisdictional Disclosure System (MJDS). The filing embeds or references the
Canadian Annual Information Form (AIF) and MD&A, which use Canadian section headings
rather than SEC Item numbers.

Approximate equivalents to 10-K sections:
  - "Description of the Business" / "General Development"  ≈ Item 1  (Business)
  - "Risk Factors"                                          ≈ Item 1A (Risk Factors)
  - "Management's Discussion and Analysis"                  ≈ Item 7  (MD&A)
"""

from __future__ import annotations

import re

from services.sec import _extract_sections

_SECTION_PATTERNS_40F = [
    re.compile(r"description\s+of\s+the\s+business", re.I),
    re.compile(r"general\s+development\s+of\s+the\s+business", re.I),
    re.compile(r"narrative\s+description\s+of\s+the\s+business", re.I),
    re.compile(r"risk\s+factors", re.I),
    re.compile(r"management.{0,5}s?\s+discussion\s+and\s+analysis", re.I),
]


def extract_40f_sections(text: str) -> str:
    """Extract business, risk, and MD&A sections from a 40-F / Canadian AIF plain text."""
    return _extract_sections(text, _SECTION_PATTERNS_40F)
