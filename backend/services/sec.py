from __future__ import annotations

import re
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "invest-hub invest-hub-api@example.com",
    "Accept-Encoding": "gzip, deflate",
}
TIMEOUT = 30
TICKER_JSON_URL = "https://www.sec.gov/files/company_tickers.json"

ANNUAL_FORM_TYPES = {"10-K", "10-K/A", "20-F", "20-F/A"}
_STALE_THRESHOLD_DAYS = 548  # ~18 months

# Sections of the 10-K most useful for LLM analysis
_SECTION_PATTERNS = [
    re.compile(r"item\s+1\.?\s+business", re.I),
    re.compile(r"item\s+1a\.?\s+risk\s+factors", re.I),
    re.compile(r"item\s+7\.?\s+management", re.I),
]
_NEXT_ITEM_PATTERN = re.compile(r"item\s+\d+[a-z]?\.?\s+\w+", re.I)
MAX_SECTION_CHARS = 8_000
MAX_FILING_CHARS = 24_000

# US GAAP XBRL concepts to fetch
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


def _cik_str(cik: int | str) -> str:
    return str(cik).zfill(10)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_cik(ticker: str) -> str:
    resp = requests.get(TICKER_JSON_URL, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    ticker_upper = ticker.upper()
    for item in resp.json().values():
        if str(item["ticker"]).upper() == ticker_upper:
            return _cik_str(item["cik_str"])
    raise ValueError(f"Ticker not found: {ticker}")


def get_submissions(cik_10: str) -> dict:
    url = f"https://data.sec.gov/submissions/CIK{cik_10}.json"
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def find_recent_annual(
    submissions: dict,
) -> tuple[str, str, str, str]:
    """
    Return (accessionNumber, primaryDocument, form_type, filing_date) for the
    most recent annual filing (10-K, 10-K/A, 20-F, or 20-F/A).
    Raises ValueError if none found.
    """
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    filing_dates = recent.get("filingDate", [])

    for i, form in enumerate(forms):
        if form in ANNUAL_FORM_TYPES:
            return accessions[i], primary_docs[i], form, filing_dates[i]

    raise ValueError(
        "No recent annual filing found — this company may be delisted or inactive"
    )


def is_filing_stale(filing_date: str) -> bool:
    """Return True if the filing date is older than ~18 months."""
    try:
        filed = date.fromisoformat(filing_date)
        return (date.today() - filed) > timedelta(days=_STALE_THRESHOLD_DAYS)
    except ValueError:
        return False


def fetch_filing_text(cik_10: str, accession: str, primary_doc: str) -> str:
    """Fetch a filing from SEC EDGAR and return plain text."""
    cik_no_zeros = str(int(cik_10))
    accession_clean = accession.replace("-", "")
    url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_no_zeros}/{accession_clean}/{primary_doc}"
    )
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return _html_to_text(resp.text)


def extract_10k_sections(text: str) -> str:
    """Extract Items 1, 1A, and 7 from 10-K plain text."""
    return _extract_sections(text, _SECTION_PATTERNS)


def get_xbrl_facts(cik_10: str, form_type: str) -> tuple[dict, str]:
    """
    Return (facts_dict, reporting_currency) from the SEC XBRL API.
    Tries us-gaap first; falls back to ifrs-full for 20-F filers.
    reporting_currency is the detected currency code (e.g. "USD", "CAD").
    """
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_10}.json"
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    raw = resp.json()

    is_20f = form_type in ("20-F", "20-F/A")
    annual_forms = (
        {form_type, form_type.rstrip("/A")} if "/" in form_type else {form_type}
    )
    # Always accept both the exact form and its non-amended equivalent
    annual_forms = {"10-K", "20-F"} if is_20f else {"10-K", "10-K/A"}

    result: dict[str, float | None] = {}
    reporting_currency = "USD"

    # Try us-gaap first
    us_gaap = raw.get("facts", {}).get("us-gaap", {})
    if us_gaap:
        for key, concepts in _XBRL_FACTS.items():
            result[key] = _latest_value(us_gaap, concepts, annual_forms)
        reporting_currency = _detect_currency(us_gaap, _XBRL_FACTS, annual_forms)

    # For 20-F filers where us-gaap is empty or sparse, try ifrs-full
    if is_20f and all(v is None for v in result.values()):
        from services.sec_20f import get_ifrs_xbrl_facts

        ifrs_result, ifrs_currency = get_ifrs_xbrl_facts(raw, annual_forms)
        result = ifrs_result
        reporting_currency = ifrs_currency

    # Derive net_debt
    cash = result.get("cash")
    debt = result.get("total_debt")
    result["net_debt"] = (
        (debt - cash) if cash is not None and debt is not None else None
    )

    return result, reporting_currency


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _extract_sections(text: str, section_patterns: list[re.Pattern]) -> str:
    lines = text.split("\n")
    sections: list[str] = []
    current: list[str] | None = None
    chars_in_section = 0

    for line in lines:
        stripped = line.strip()

        matched_target = any(p.match(stripped) for p in section_patterns)
        if matched_target:
            if current is not None:
                sections.append("\n".join(current))
            current = [line]
            chars_in_section = len(line)
            continue

        if current is not None:
            if _NEXT_ITEM_PATTERN.match(stripped) and not any(
                p.match(stripped) for p in section_patterns
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


def _latest_value(
    namespace: dict, concept_names: list[str], annual_forms: set[str]
) -> float | None:
    """Return the most recent annual value for a list of concept names."""
    for name in concept_names:
        concept = namespace.get(name)
        if not concept:
            continue
        units = concept.get("units", {})
        entries = units.get("USD") or units.get("shares") or []
        annual = [e for e in entries if e.get("form") in annual_forms and "end" in e]
        if not annual:
            continue
        annual.sort(key=lambda e: e["end"], reverse=True)
        return float(annual[0]["val"])
    return None


def _detect_currency(
    namespace: dict, facts_map: dict[str, list[str]], annual_forms: set[str]
) -> str:
    """Detect reporting currency from XBRL units (defaults to USD)."""
    for concepts in facts_map.values():
        for name in concepts:
            concept = namespace.get(name)
            if not concept:
                continue
            units = concept.get("units", {})
            for unit_key, entries in units.items():
                if unit_key == "shares":
                    continue
                annual = [
                    e for e in entries if e.get("form") in annual_forms and "end" in e
                ]
                if annual:
                    return unit_key
    return "USD"
