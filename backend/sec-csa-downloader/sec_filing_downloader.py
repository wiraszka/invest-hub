import re
import time
from pathlib import Path

import pandas as pd
import requests

# -------- INPUTS -----------

IDENTITY = "User Identity"

ticker = "IONR"

sector = "MINING"
subsector = "LITHIUM"  # Use None if no subsector

# --- PATH CONFIGURATION ---

BASE_DIR = Path("companies")

if not subsector:
    SAVE_DIR = BASE_DIR / sector / ticker
else:
    SAVE_DIR = BASE_DIR / sector / subsector / ticker

MANIFEST_CSV = SAVE_DIR / f"{ticker}_SEC_manifest.csv"

# -------- PARAMS -----------

FORM_LIMITS = {
    # Core financials
    "10-K": 3,
    "10-K/A": 2,
    "10-Q": 6,
    "10-Q/A": 3,
    # Material event flow
    "8-K": 25,
    "8-K/A": 5,
    # Governance / compensation / proxy
    "DEF 14A": 5,
    "PRE 14A": 3,
    "DEFA14A": 3,
    # Capital markets / dilution / M&A
    "S-1": 3,
    "S-1/A": 5,
    "S-3": 3,
    "S-3/A": 5,
    "S-4": 3,
    "S-4/A": 5,
    "424B1": 3,
    "424B2": 3,
    "424B3": 3,
    "424B4": 3,
    "424B5": 5,
    # Insider ownership
    "3": 5,
    "4": 25,
    "5": 5,
    # Large shareholders
    "SC 13D": 10,
    "SC 13D/A": 15,
    "SC 13G": 10,
    "SC 13G/A": 15,
    # Institutional ownership
    "13F-HR": 8,
    "13F-HR/A": 5,
    # Foreign issuer equivalents
    "20-F": 3,
    "6-K": 20,
}

TIMEOUT = 30
HEADERS = {
    "User-Agent": IDENTITY,
    "Accept-Encoding": "gzip, deflate",
}

TICKER_JSON_URL = "https://www.sec.gov/files/company_tickers.json"


def safe_filename(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(text)).strip("_")


def cik_str(cik: int | str) -> str:
    return str(cik).zfill(10)


def accession_nodash(accession: str) -> str:
    return str(accession).replace("-", "")


def get_ticker_map() -> dict:
    resp = requests.get(TICKER_JSON_URL, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def resolve_ticker_to_cik(ticker: str) -> tuple[str, str]:
    """
    Returns (company_name, cik_10digit)
    """
    data = get_ticker_map()
    ticker_upper = ticker.upper()

    for _, item in data.items():
        if str(item["ticker"]).upper() == ticker_upper:
            return item["title"], cik_str(item["cik_str"])

    raise ValueError(f"Ticker not found in SEC ticker map: {ticker}")


def get_company_submissions(cik_10: str) -> dict:
    url = f"https://data.sec.gov/submissions/CIK{cik_10}.json"
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def submissions_to_dataframe(submissions: dict) -> pd.DataFrame:
    recent = submissions.get("filings", {}).get("recent", {})
    if not recent:
        return pd.DataFrame()

    df = pd.DataFrame(recent)

    wanted = [
        "accessionNumber",
        "filingDate",
        "reportDate",
        "acceptanceDateTime",
        "act",
        "form",
        "fileNumber",
        "filmNumber",
        "items",
        "size",
        "isXBRL",
        "isInlineXBRL",
        "primaryDocument",
        "primaryDocDescription",
    ]
    existing = [c for c in wanted if c in df.columns]
    return df[existing].copy()


def build_filing_urls(
    cik_10: str, accession: str, primary_document: str
) -> tuple[str, str]:
    """
    Returns:
      filing_index_url
      primary_doc_url
    """
    cik_no_leading_zeros = str(int(cik_10))
    accession_clean = accession_nodash(accession)

    filing_index_url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_no_leading_zeros}/{accession_clean}/{accession}-index.htm"
    )

    primary_doc_url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_no_leading_zeros}/{accession_clean}/{primary_document}"
    )

    return filing_index_url, primary_doc_url


def download_file(url: str, out_path: Path) -> None:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    out_path.write_bytes(resp.content)


def select_filings(df: pd.DataFrame, form_limits: dict[str, int]) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    df = df.copy()
    df["filingDate"] = pd.to_datetime(df["filingDate"], errors="coerce")
    df = df.sort_values("filingDate", ascending=False)

    parts = []
    for form, limit in form_limits.items():
        subset = df[df["form"] == form].head(limit)
        if not subset.empty:
            parts.append(subset)

    if not parts:
        return pd.DataFrame(columns=df.columns)

    selected = pd.concat(parts, ignore_index=True)
    selected = selected.drop_duplicates(subset=["accessionNumber"]).reset_index(
        drop=True
    )
    return selected


def main():
    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    company_name, cik_10 = resolve_ticker_to_cik(ticker)
    print(f"Resolved {ticker} -> {company_name} | CIK {cik_10}")

    submissions = get_company_submissions(cik_10)
    df = submissions_to_dataframe(submissions)

    if df.empty:
        print("No recent filings found.")
        pd.DataFrame().to_csv(MANIFEST_CSV, index=False)
        print(f"Saved manifest: {MANIFEST_CSV}")
        print(f"Saved filings under: {SAVE_DIR.resolve()}")
        return

    selected = select_filings(df, FORM_LIMITS)

    rows = []

    for _, filing in selected.iterrows():
        filing_form = filing.get("form")
        filing_date = filing.get("filingDate")
        accession = filing.get("accessionNumber")
        primary_document = filing.get("primaryDocument")
        primary_doc_desc = filing.get("primaryDocDescription")

        record = {
            "company": company_name,
            "ticker": ticker,
            "sector": sector,
            "subsector": subsector,
            "cik": cik_10,
            "form": filing_form,
            "filing_date": str(filing_date.date()) if pd.notna(filing_date) else None,
            "accession_no": accession,
            "primary_doc_name": primary_document,
            "primary_doc_description": primary_doc_desc,
            "index_url": None,
            "primary_doc_url": None,
            "local_path": None,
            "status": "metadata_only",
            "error": None,
        }

        try:
            if not accession or not primary_document:
                raise ValueError("Missing accession number or primary document")

            index_url, primary_doc_url = build_filing_urls(
                cik_10, accession, primary_document
            )

            ext = Path(primary_document).suffix or ".html"
            form_dir = SAVE_DIR / safe_filename(filing_form)
            form_dir.mkdir(parents=True, exist_ok=True)

            out_name = safe_filename(
                f"{record['filing_date']}_{filing_form}_{accession}{ext}"
            )
            out_path = form_dir / out_name

            download_file(primary_doc_url, out_path)

            record["index_url"] = index_url
            record["primary_doc_url"] = primary_doc_url
            record["local_path"] = str(out_path)
            record["status"] = "downloaded"

            print(f"Downloaded {filing_form} | {record['filing_date']} | {out_path}")

            time.sleep(0.2)

        except Exception as e:
            record["error"] = str(e)
            print(f"Failed download {filing_form} | {record['filing_date']} | {e}")

        rows.append(record)

    manifest = pd.DataFrame(rows)
    if not manifest.empty:
        manifest["filing_date"] = pd.to_datetime(
            manifest["filing_date"], errors="coerce"
        )
        manifest = manifest.sort_values(
            ["filing_date", "form"], ascending=[False, True]
        ).reset_index(drop=True)

    manifest.to_csv(MANIFEST_CSV, index=False)
    print(f"Saved manifest: {MANIFEST_CSV}")
    print(f"Saved filings under: {SAVE_DIR.resolve()}")


if __name__ == "__main__":
    main()
