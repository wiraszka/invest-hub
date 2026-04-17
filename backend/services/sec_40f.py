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

The 40-F primary document is a thin cover form (metadata only). The actual content
lives in Exhibit 99.1 (Annual Information Form) and optionally Exhibit 99.2 (MD&A).
fetch_40f_sections handles locating and fetching those exhibits.
"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from services.sec import HEADERS, TIMEOUT, _extract_sections, _html_to_text

_SECTION_PATTERNS_40F = [
    re.compile(r"description\s+of\s+the\s+business", re.I),
    re.compile(r"general\s+development\s+of\s+the\s+business", re.I),
    re.compile(r"narrative\s+description\s+of\s+the\s+business", re.I),
    re.compile(r"risk\s+factors", re.I),
    re.compile(r"management.{0,5}s?\s+discussion\s+and\s+analysis", re.I),
]

_EDGAR_BASE = "https://www.sec.gov"


def extract_40f_sections(text: str) -> str:
    """Extract business, risk, and MD&A sections from a 40-F / Canadian AIF plain text."""
    return _extract_sections(text, _SECTION_PATTERNS_40F)


def fetch_40f_sections(cik_10: str, accession: str) -> str:
    """
    Fetch the Annual Information Form (EX-99.1) from a 40-F filing and extract
    the relevant sections. Falls back to EX-99.2 if EX-99.1 is absent.
    """
    cik_no_zeros = str(int(cik_10))
    accession_clean = accession.replace("-", "")
    index_url = (
        f"{_EDGAR_BASE}/Archives/edgar/data/"
        f"{cik_no_zeros}/{accession_clean}/{accession}-index.htm"
    )

    resp = requests.get(index_url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    exhibit_url = _find_exhibit_url(soup, ("EX-99.1", "EX-99.2"))
    if exhibit_url is None:
        raise ValueError("No EX-99.1 or EX-99.2 exhibit found in 40-F filing index")

    doc_resp = requests.get(exhibit_url, headers=HEADERS, timeout=60)
    doc_resp.raise_for_status()
    text = _html_to_text(doc_resp.text)
    return extract_40f_sections(text)


def _find_exhibit_url(soup: BeautifulSoup, exhibit_types: tuple[str, ...]) -> str | None:
    """
    Search the EDGAR filing index table for the first matching exhibit type
    and return its absolute URL.
    """
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        # Column layout: Description | Document | Type | ...
        # Type cell is index 3 in most index pages; Description is index 0
        type_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""
        if not any(t in type_text.upper() for t in exhibit_types):
            continue
        link = row.find("a", href=True)
        if link:
            href = link["href"]
            if href.startswith("/"):
                return f"{_EDGAR_BASE}{href}"
            return href
    return None
