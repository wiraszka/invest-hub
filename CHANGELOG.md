# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v1.11.0] - 2026-04-26

### Changed

- Rename app title from "invest-hub" to "InvestHub" in the browser tab and sidebar

### Fixed

- Resolve Canadian tickers correctly by appending `.TO` to all CAD-currency positions before querying FMP and SEC — prevents collisions where a Canadian ticker shares the same symbol as a US company (e.g. ARX → ARC Resources, not Accelerant Holdings)
- Reject SEC SIC fallback results for `.TO` tickers unless the matched company files a 40-F, preventing US ticker collisions from producing wrong sector data
- Ensure all tickers become clickable links after Analyze even when the metadata request times out (moved `setAnalyzedTickers` to `finally` block)

## [v1.10.0] - 2026-04-22

### Added

- Restructure the research pipeline to use FMP as the primary financial data source — income statement, balance sheet, cash flow, and key metrics are fetched directly from FMP rather than extracted via XBRL
- SEC filing retrieval is now a soft failure — when a CIK cannot be resolved the pipeline continues using the FMP company description as a narrative fallback and marks `data_source` as "FMP only"
- Standard charts (capital structure, cash burn) are now computed directly from FMP data; LLM extraction is reserved for industry-specific charts (reserves, production, NAV) found in filing text
- Add TwelveData → FMP price failover: live prices attempt TwelveData first and fall back to FMP quote endpoint on failure
- Add Sector column to the Positions table — blank before Analyze is run, populated with sector label (or "ETF") once metadata is fetched
- Lift analyze state into a React Context (`AnalyzeContext`) so the sequential metadata loop continues running when navigating away from the Investments page
- Add `←` back button to the company page linking back to Investments
- Replace placeholder "More Info" section on the company page with a Research Panel that fetches and renders the Company Snapshot, data source details, and filing metadata

### Changed

- Analyze button now only triggers FMP metadata lookup per ticker — the full LLM research pipeline is decoupled and will be triggered separately from the company page
- `data_integrity` schema updated: remove `xbrl_quality`, add `data_source` ("SEC + FMP" / "FMP only") and `fmp_financials` ("full" / "partial" / "none") fields
- Move Sector column in the Positions table to directly after Type

### Fixed

- Fall back to SEC EDGAR SIC data for symbol metadata when FMP does not cover a ticker — provides sector (from `sicDescription`) and country (inferred from annual filing type: 40-F → Canada, 20-F → International, 10-K → United States)
- Ensure company names become clickable links after Analyze even when FMP returns no metadata for a ticker (e.g. small TSX listings)
- Resolve Research Panel crash caused by accessing removed `xbrl_data` field after the pipeline was restructured to use FMP data

## [v1.9.0] - 2026-04-21

### Added

- Add sortable column headers to the Positions and Transactions tables — click once to sort, again to reverse, a third time to restore original order; numeric columns default to descending on first click
- Split the Positions view into separate Equities & ETFs and Crypto tables when crypto holdings are detected
- Add three portfolio donut charts above the Investments table: Asset Type (always visible), Sector, and Geography (populated after running Analyze)
- Add Analyze button that sequentially runs FMP metadata lookup and LLM research pipeline for each equity position; each row shows a loading spinner while in progress and a checkmark on completion
- Sector and Geography charts use ETF look-through via FMP sector and country weighting endpoints, distributing each ETF's cost basis proportionally across its underlying sectors and countries
- Company names in the Positions table become clickable links to the Research page after a successful LLM analysis
- Cache symbol metadata globally in a new `symbol_metadata` MongoDB collection with a 30-day TTL; charts hydrate instantly on subsequent page loads without re-running Analyze

### Changed

- Reorder TransactionsTable columns to align with Positions table layout (Account, Name, Symbol, Type, Date, Amount)
- Replace the full-height CSV dropzone in the loaded state with a compact inline re-upload button aligned with the tab row

## [v1.8.0] - 2026-04-21

### Added

- Build out Investments page with drag-and-drop CSV upload, positions table (account, symbol, shares, avg cost, cost basis, realized P/L), and all-transactions view (latest first) sourced from Wealthsimple activities exports
- Parse and persist Wealthsimple activities CSV to MongoDB per user, scoped by Clerk user ID; account IDs are stripped before storage
- Add `POST /api/investments/upload`, `GET /api/investments/positions`, `GET /api/investments/transactions` endpoints

## [v1.7.0] - 2026-04-21

### Changed

- Return full analysis document from `POST /api/analysis/{ticker}` — eliminates the redundant follow-up GET request from the frontend
- Consolidate duplicate XBRL helpers: `_latest_value` and `_detect_currency` in `sec.py` now serve both GAAP and IFRS namespaces; removed identical copies from `sec_20f.py`
- Move `SNAPSHOT_MODEL` and `LLM_KNOWLEDGE_CUTOFF` to `services/llm.py` as the single source of truth; `routers/analysis.py` now imports them

### Fixed

- Cache Anthropic client at module level to avoid creating a new connection pool on every LLM call
- Move `timedelta` import to module level in `services/db.py`
- Update SEC EDGAR User-Agent to use real contact email in both `services/sec.py` and `services/search.py`

### Removed

- Delete `backend/app.py`, `backend/trends.py`, and `backend/constants.py` — Streamlit-era files unused since the FastAPI rewrite
- Delete `get_filing_sections` from `services/sec.py` — unused since v1.6.0

### Tests

- Fix `test_search_returns_at_most_five_results` — limit was raised to 10 in v1.4.0; test was asserting stale behaviour
- Add `test_find_recent_annual_raises_when_no_annual_filing` to `test_sec.py`
- Add merger notice and `company_independence` fallback coverage to `test_llm.py`
- Add `test_trends.py` covering cache hit, cache miss, fetch error, and validation

## [v1.6.6] - 2026-04-21

### Fixed

- Pin urllib3 to 1.26.x to fix `method_whitelist` incompatibility with pytrends 4.9.2

## [v1.6.5] - 2026-04-21

### Fixed

- Add browser User-Agent header and retry logic to Google Trends requests to reduce cloud IP blocking
- Cache trends results in MongoDB for 1 hour so repeated refreshes are served locally instead of hitting Google

## [v1.6.4] - 2026-04-20

### Fixed

- Add `investhub.tech` and `www.investhub.tech` to CORS allowed origins so API requests from the new domain are not blocked

## [v1.6.3] - 2026-04-16

### Fixed

- Fetch the Annual Information Form (EX-99.1) from 40-F filings instead of the thin cover document — the primary document contains only metadata, so section extraction was returning nothing and the LLM had no filing context for Canadian MJDS filers (e.g. AEM)

## [v1.6.2] - 2026-04-17

### Added

- Support 40-F filings for Canadian MJDS filers (e.g. AEM, WPM) — detects as the most recent annual filing and extracts business, risk, and MD&A sections from the Canadian AIF structure
- Apply IFRS XBRL fallback for 40-F filers in addition to 20-F filers

## [v1.6.1] - 2026-04-17

### Changed

- Move LLM snapshot system prompt from MongoDB into code — removes the `prompts` collection dependency and ensures the correct generalized prompt is always used

## [v1.6.0] - 2026-04-16

### Added

- Support 20-F filings for foreign private issuers (e.g. Canadian, Australian companies cross-listed on US exchanges)
- Support amended filings (10-K/A, 20-F/A) in annual filing detection
- Add `sec_20f.py` service for 20-F section extraction and IFRS XBRL fallback
- Detect and label reporting currency from XBRL units (e.g. CAD, AUD) rather than assuming USD
- Add `company_independence` field to LLM classification — flags merger, acquisition, going-concern, or SPAC language in filings
- Add Data Integrity table to Research panel showing filing type, recency, currency, XBRL quality, company status, LLM model, and analysis timestamp

### Changed

- Analysis pipeline aborts with a clear error if no annual filing is found, rather than failing silently
- Filing extraction and XBRL fetch now tolerate partial failures — LLM proceeds with whatever context is available
- Stale filings (>18 months old) proceed with a warning rather than aborting

## [v1.5.0] - 2026-04-16

### Added

- Build out Commodities Sentiment page with Google Trends data, current interest panel, commodity toggles, and an interactive line chart

## [v1.4.1] - 2026-04-16

### Fixed

- Add CORS middleware to the backend to allow requests from the frontend deployment

## [v1.4.0] - 2026-04-13

### Added

- Add Research page (`/research`) with live company search, dropdown results (up to 10), and session-cached analysis results
- Display Company Snapshot, key metrics, and charts (capital structure, cash burn, revenue by segment) in the Research panel
- Add Recent chips row for quick navigation between previously searched companies within a session

### Changed

- Move company search from the sidebar to the Research page
- Raise company search result limit from 5 to 10

## [v1.3.0] - 2026-04-12

### Changed

- Refactor LLM analysis pipeline: replace single monolithic call with two focused calls (Haiku for classification + chart JSON extraction, Sonnet for Company Snapshot prose)
- Extract only relevant 10-K sections (Item 1, 1A, 7) instead of full document, reducing input from 100k to ~24k chars
- Replace LLM-generated charts with structured data pipeline: XBRL API for standard financials, targeted LLM extraction for industry-specific fields
- Store `snapshot`, `chart_data`, `xbrl_data`, and `market_cap_usd` as discrete fields instead of a single markdown blob
- Derive market cap from XBRL shares outstanding × live TwelveData price
- Derive cash burn for pre-revenue companies from XBRL operating cash flow

### Added

- `services/sec.py`: section extractor for 10-K Items 1/1A/7 and XBRL structured financial facts fetcher
- `tests/test_sec.py`: 7 tests covering CIK resolution, section extraction, and XBRL parsing

## [v1.2.1] - 2026-04-12

### Changed

- Store LLM prompts in MongoDB instead of on disk, keeping them out of the public repository

## [v1.2.0] - 2026-04-12

### Added

- Add SEC EDGAR 10-K fetching and text extraction for any ticker
- Add LLM pre-classification and full company analysis pipeline powered by Claude
- Store and retrieve analysis results in MongoDB
- Add `POST /api/analysis/{ticker}` and `GET /api/analysis/{ticker}` endpoints

## [v1.1.0] - 2026-04-11

### Added

- Add company ticker and name search to the sidebar, powered by the SEC EDGAR company index
- Add company page (`/company/[ticker]`) with live price and 1-year price chart

## [v1.0.2] - 2026-04-10

### Added

- Add pytest and ruff for backend testing and linting
- Add Jest and React Testing Library for frontend testing
- Add GitHub Actions CI running lint and tests on every pull request to main

## [v1.0.1] - 2026-04-10

### Added

- Build Next.js frontend with Clerk authentication and sidebar navigation
- Restructure repository as a monorepo with separate `backend/` and `frontend/` directories

[v1.10.0]: https://github.com/wiraszka/invest-hub/compare/v1.9.0...v1.10.0
[v1.9.0]: https://github.com/wiraszka/invest-hub/compare/v1.8.0...v1.9.0
[v1.8.0]: https://github.com/wiraszka/invest-hub/compare/v1.7.0...v1.8.0
[v1.7.0]: https://github.com/wiraszka/invest-hub/compare/v1.6.6...v1.7.0
[v1.6.6]: https://github.com/wiraszka/invest-hub/compare/v1.6.5...v1.6.6
[v1.6.5]: https://github.com/wiraszka/invest-hub/compare/v1.6.4...v1.6.5
[v1.6.4]: https://github.com/wiraszka/invest-hub/compare/v1.6.3...v1.6.4
[v1.6.3]: https://github.com/wiraszka/invest-hub/compare/v1.6.2...v1.6.3
[v1.6.2]: https://github.com/wiraszka/invest-hub/compare/v1.6.1...v1.6.2
[v1.6.1]: https://github.com/wiraszka/invest-hub/compare/v1.6.0...v1.6.1
[v1.6.0]: https://github.com/wiraszka/invest-hub/compare/v1.5.0...v1.6.0
[v1.5.0]: https://github.com/wiraszka/invest-hub/compare/v1.4.1...v1.5.0
[v1.4.1]: https://github.com/wiraszka/invest-hub/compare/v1.4.0...v1.4.1
[v1.4.0]: https://github.com/wiraszka/invest-hub/compare/v1.3.0...v1.4.0
[v1.3.0]: https://github.com/wiraszka/invest-hub/compare/v1.2.1...v1.3.0
[v1.2.1]: https://github.com/wiraszka/invest-hub/compare/v1.2.0...v1.2.1
[v1.2.0]: https://github.com/wiraszka/invest-hub/compare/v1.1.0...v1.2.0
[v1.1.0]: https://github.com/wiraszka/invest-hub/compare/v1.0.2...v1.1.0
[v1.0.2]: https://github.com/wiraszka/invest-hub/compare/v1.0.1...v1.0.2
[v1.0.1]: https://github.com/wiraszka/invest-hub/releases/tag/v1.0.1
