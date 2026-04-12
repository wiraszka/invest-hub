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
MAX_TEXT_CHARS = 200_000


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


def get_recent_10k_text(ticker: str) -> str:
    cik_10 = resolve_cik(ticker)

    url = f"https://data.sec.gov/submissions/CIK{cik_10}.json"
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    submissions = resp.json()

    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    accession = primary_doc = None
    for i, form in enumerate(forms):
        if form == "10-K":
            accession = accessions[i]
            primary_doc = primary_docs[i]
            break

    if not accession or not primary_doc:
        raise ValueError(f"No 10-K found for {ticker}")

    cik_no_zeros = str(int(cik_10))
    accession_clean = accession.replace("-", "")
    doc_url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_no_zeros}/{accession_clean}/{primary_doc}"
    )

    resp = requests.get(doc_url, headers=HEADERS, timeout=60)
    resp.raise_for_status()

    text = _extract_text(resp.text)
    return text[:MAX_TEXT_CHARS]


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()
