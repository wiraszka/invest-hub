from pathlib import Path
from urllib.parse import urljoin
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from edgar import Company, set_identity

# -------- INPUTS -----------

IDENTITY = "User Identity"

ticker = "EQX"

sector = "MINING"
subsector = "GOLD" # If no subsector use None

# --- PATH CONFIGURATION ---

# Root folder for all SEC downloads
BASE_DIR = Path("SEC_Filings")

# Folder for this specific company
if not subsector:
    SAVE_DIR = BASE_DIR / f"{sector}" / f"{ticker}"
else:
    SAVE_DIR = BASE_DIR / f"{sector}" / f"{subsector}" / f"{ticker}"

# Manifest lives inside the company filings folder
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
set_identity(IDENTITY)
USER_AGENT = IDENTITY
company = Company(ticker)



def safe_filename(text: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', "_", str(text)).strip("_")


def pick_index_url(filing) -> str | None:
    """
    Try the most likely filing index URL attributes across edgartools versions.
    """
    candidates = [
        getattr(filing, "homepage_url", None),
        getattr(filing, "filing_url", None),
        getattr(filing, "url", None),
        getattr(filing, "index_url", None),
    ]
    for url in candidates:
        if isinstance(url, str) and url.startswith("http"):
            return url
    return None


def find_primary_document(index_url: str, expected_form: str) -> tuple[str | None, str | None]:
    """
    Return (document_url, document_filename) for the main filing document
    from the SEC filing index page.
    """
    resp = requests.get(index_url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="tableFile", summary=re.compile("Document Format Files", re.I))

    if table is None:
        return None, None

    rows = table.find_all("tr")[1:]  # skip header
    expected_form_upper = str(expected_form).upper()

    candidates = []
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        doc_cell = cells[2]
        type_cell = cells[3]

        link = doc_cell.find("a")
        if not link:
            continue

        href = link.get("href", "").strip()
        if not href:
            continue

        doc_filename = link.get_text(" ", strip=True)
        doc_type = type_cell.get_text(" ", strip=True).upper()
        full_url = urljoin("https://www.sec.gov", href)

        candidates.append({
            "url": full_url,
            "filename": doc_filename,
            "type": doc_type,
        })

    # 1) Exact filing type match first
    for item in candidates:
        if item["type"] == expected_form_upper:
            return item["url"], item["filename"]

    # 2) Match base form for amended forms, e.g. 10-Q/A -> 10-Q
    base_form = expected_form_upper.replace("/A", "").replace("-A", "").replace(" AMENDMENT", "")
    for item in candidates:
        if item["type"] == base_form:
            return item["url"], item["filename"]

    # 3) Fallback to first HTML/HTM/XML/TXT doc
    for item in candidates:
        if item["filename"].lower().endswith((".htm", ".html", ".xml", ".txt")):
            return item["url"], item["filename"]

    # 4) Last resort: first document row
    if candidates:
        return candidates[0]["url"], candidates[0]["filename"]

    return None, None


def download_file(url: str, out_path: Path) -> None:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    out_path.write_bytes(resp.content)


rows = []
SAVE_DIR.mkdir(parents=True, exist_ok=True)

for form, limit in FORM_LIMITS.items():
    try:
        filings = company.get_filings(form=form).head(limit)

        for filing in filings:
            filing_form = getattr(filing, "form", form)
            filing_date = str(getattr(filing, "filing_date", ""))

            accession_no = (
                getattr(filing, "accession_no", None)
                or getattr(filing, "accession_number", None)
            )

            company_name = getattr(filing, "company", None) or ticker
            index_url = pick_index_url(filing)

            record = {
                "form": filing_form,
                "filing_date": filing_date,
                "accession_no": accession_no,
                "company": company_name,
                "index_url": index_url,
                "primary_doc_url": None,
                "primary_doc_name": None,
                "local_path": None,
                "status": "metadata_only",
                "error": None,
            }

            try:
                if not index_url:
                    raise ValueError("No filing index URL found on filing object")

                primary_doc_url, primary_doc_name = find_primary_document(index_url, filing_form)
                if not primary_doc_url:
                    raise ValueError("Could not locate primary document on filing index page")

                ext = Path(primary_doc_name).suffix if primary_doc_name else ".html"
                if not ext:
                    ext = ".html"

                form_dir = SAVE_DIR / safe_filename(filing_form)
                form_dir.mkdir(parents=True, exist_ok=True)

                out_name = safe_filename(f"{filing_date}_{filing_form}_{accession_no}{ext}")
                out_path = form_dir / out_name

                download_file(primary_doc_url, out_path)

                record["primary_doc_url"] = primary_doc_url
                record["primary_doc_name"] = primary_doc_name
                record["local_path"] = str(out_path)
                record["status"] = "downloaded"

                print(f"Downloaded {filing_form} | {filing_date} | {out_path}")

            except Exception as file_err:
                record["error"] = str(file_err)
                print(f"Failed download {filing_form} | {filing_date} | {file_err}")

            rows.append(record)

    except Exception as e:
        print(f"Skipping {form}: {e}")

df = pd.DataFrame(rows)

if not df.empty:
    df["filing_date"] = pd.to_datetime(df["filing_date"], errors="coerce")
    df = df.sort_values(["filing_date", "form"], ascending=[False, True]).reset_index(drop=True)

df.to_csv(MANIFEST_CSV, index=False)
print(f"Saved manifest: {MANIFEST_CSV}")
print(f"Saved filings under: {SAVE_DIR.resolve()}")