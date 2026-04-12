from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "invest-hub invest-hub-api@example.com",
    "Accept-Encoding": "gzip, deflate",
}
TIMEOUT = 30
TICKER_JSON_URL = "https://www.sec.gov/files/company_tickers.json"

# Sections of the 10-K most useful for LLM analysis
_SECTION_PATTERNS = [
    re.compile(r"item\s+1\.?\s+business", re.I),
    re.compile(r"item\s+1a\.?\s+risk\s+factors", re.I),
    re.compile(r"item\s+7\.?\s+management", re.I),
]
_NEXT_ITEM_PATTERN = re.compile(r"item\s+\d+[a-z]?\.?\s+\w+", re.I)
MAX_SECTION_CHARS = 8_000
MAX_FILING_CHARS = 24_000


def _cik_str(cik: int | str) -> str:
    return str(cik).zfill(10)


def resolve_cik(ticker: str) -> str:
    resp = requests.get(TICKER_JSON_URL, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    ticker_upper = ticker.upper()
    for item in resp.json().values():
        if str(item["ticker"]).upper() == ticker_upper:
            return _cik_str(item["cik_str"])
    raise ValueError(f"Ticker not found: {ticker}")


def _get_submissions(cik_10: str) -> dict:
    url = f"https://data.sec.gov/submissions/CIK{cik_10}.json"
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _find_recent_10k(submissions: dict) -> tuple[str, str]:
    """Return (accessionNumber, primaryDocument) for the most recent 10-K."""
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    for i, form in enumerate(forms):
        if form == "10-K":
            return accessions[i], primary_docs[i]

    raise ValueError("No 10-K found in recent filings")


def _fetch_filing_html(cik_10: str, accession: str, primary_doc: str) -> str:
    cik_no_zeros = str(int(cik_10))
    accession_clean = accession.replace("-", "")
    url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_no_zeros}/{accession_clean}/{primary_doc}"
    )
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.text


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _extract_sections(text: str) -> str:
    """Extract Item 1, 1A, and 7 from the filing text."""
    lines = text.split("\n")
    sections: list[str] = []
    current: list[str] | None = None
    chars_in_section = 0

    for line in lines:
        stripped = line.strip()

        # Check if this line starts a target section
        matched_target = any(p.match(stripped) for p in _SECTION_PATTERNS)
        if matched_target:
            if current is not None:
                sections.append("\n".join(current))
            current = [line]
            chars_in_section = len(line)
            continue

        # If we're inside a target section, check if a new item starts
        if current is not None:
            if _NEXT_ITEM_PATTERN.match(stripped) and not any(
                p.match(stripped) for p in _SECTION_PATTERNS
            ):
                sections.append("\n".join(current))
                current = None
                chars_in_section = 0
            else:
                if chars_in_section < MAX_SECTION_CHARS:
                    current.append(line)
                    chars_in_section += len(line)

    if current:
        sections.append("\n".join(current))

    combined = "\n\n".join(sections)
    return combined[:MAX_FILING_CHARS]


def get_filing_sections(ticker: str) -> str:
    """Return the key 10-K sections (Item 1, 1A, 7) as plain text."""
    cik_10 = resolve_cik(ticker)
    submissions = _get_submissions(cik_10)
    accession, primary_doc = _find_recent_10k(submissions)
    html = _fetch_filing_html(cik_10, accession, primary_doc)
    text = _html_to_text(html)
    return _extract_sections(text)


# ---------------------------------------------------------------------------
# XBRL structured financial facts
# ---------------------------------------------------------------------------

_XBRL_FACTS = {
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
    ],
    "total_debt": [
        "LongTermDebtAndCapitalLeaseObligations",
        "LongTermDebt",
        "DebtAndCapitalLeaseObligations",
    ],
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "net_income": [
        "NetIncomeLoss",
    ],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
    ],
    "shares_outstanding": [
        "CommonStockSharesOutstanding",
    ],
}


def _latest_annual_value(facts: dict, concept_names: list[str]) -> float | None:
    """Return the most recent annual (10-K) reported value for a list of concept names."""
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    for name in concept_names:
        concept = us_gaap.get(name)
        if not concept:
            continue
        units = concept.get("units", {})
        entries = units.get("USD") or units.get("shares") or []
        # Filter to 10-K annual filings only, sort by end date descending
        annual = [e for e in entries if e.get("form") == "10-K" and "end" in e]
        if not annual:
            continue
        annual.sort(key=lambda e: e["end"], reverse=True)
        return float(annual[0]["val"])
    return None


def get_xbrl_facts(ticker: str) -> dict:
    """Return standardised financial facts from the SEC XBRL API."""
    cik_10 = resolve_cik(ticker)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_10}.json"
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    facts = resp.json()

    result: dict[str, float | None] = {}
    for key, concepts in _XBRL_FACTS.items():
        result[key] = _latest_annual_value(facts, concepts)

    # Derive net_debt from available figures
    cash = result.get("cash")
    debt = result.get("total_debt")
    if cash is not None and debt is not None:
        result["net_debt"] = debt - cash
    else:
        result["net_debt"] = None

    return result
