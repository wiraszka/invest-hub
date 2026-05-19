# invest-hub

A personal investment tracking and stock research platform built on a FastAPI backend and Next.js frontend, deployed on Vercel.

## Features

- **Investments** — Upload your Wealthsimple transaction history to track open positions, cost basis, realized P/L, and portfolio composition (asset type, sector, geography) via interactive charts
- **Research** — Search any SEC-registered company, trigger an LLM-driven analysis pipeline, and view a Company Snapshot, key financial metrics, industry-specific charts, and a Data Integrity summary
- **Commodities Sentiment** — Google Trends interest tracker for 11 commodities with a live line chart and momentum indicators
- **Shortlist** — Save companies for quick re-access (in progress)

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (React), Recharts, Tailwind CSS |
| Backend | FastAPI (Python), Vercel serverless functions |
| Database — app data | MongoDB Atlas |
| Database — market data | PostgreSQL (Neon) |
| Auth | Clerk |
| LLM | Claude API (Anthropic) |
| Price Data | TwelveData API (FMP → yfinance fallback chain) |
| Financial Data | Financial Modeling Prep (FMP) API |
| Filing Data | SEC EDGAR API |
| Sentiment Data | Google Trends (pytrends) |
| Market Data | Finnhub API, yfinance |
| Identity Resolution | OpenFIGI API |

## Project Structure

```
invest-hub/
├── frontend/           # Next.js app
├── backend/            # FastAPI app
│   ├── api/            # Entry point (index.py)
│   ├── adapters/       # Market data provider adapters (hexagonal architecture)
│   ├── core/           # Config, cache, exceptions
│   ├── models/         # Canonical domain models
│   ├── routers/        # Route handlers
│   └── services/       # Business logic
└── PROJECT_OUTLINE.md  # Full architecture and feature spec
```

## Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in API keys
uvicorn api.index:app --reload
```

### Frontend

```bash
cd frontend
pnpm install
cp .env.local.example .env.local  # fill in keys
pnpm dev
```

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `MONGODB_URI` | MongoDB Atlas connection string |
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `TD_API_KEY` | TwelveData API key |
| `FMP_API_KEY` | Financial Modeling Prep API key |
| `FINNHUB_API_KEY` | Finnhub API key |
| `OPENFIGI_API_KEY` | OpenFIGI API key |
| `SEC_CONTACT_EMAIL` | Contact email for SEC EDGAR User-Agent header |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | Backend Vercel URL |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk frontend publishable key |
| `CLERK_SECRET_KEY` | Clerk backend secret key |

## Documentation

See [PROJECT_OUTLINE.md](PROJECT_OUTLINE.md) for full architecture, pipeline design, and feature spec.
