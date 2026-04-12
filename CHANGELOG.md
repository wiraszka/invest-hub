# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[v1.1.0]: https://github.com/wiraszka/invest-hub/compare/v1.0.2...v1.1.0
[v1.0.2]: https://github.com/wiraszka/invest-hub/compare/v1.0.1...v1.0.2
[v1.0.1]: https://github.com/wiraszka/invest-hub/releases/tag/v1.0.1
