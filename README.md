# invest-hub

A personal investment tracking and stock research platform built on a FastAPI backend and Next.js frontend, deployed on Vercel.

## Features

- **Investments** — Upload Wealthsimple or Questrade transaction history to track open positions, cost basis, realized P/L, and portfolio composition via interactive charts. No external API calls — works entirely from your uploaded data.
- **Symbol page** — Live price chart for any ticker (TwelveData → FMP fallback)
- **Research** — Search any SEC-registered ticker; AI-powered analysis pipeline in active redesign
- **Commodities Sentiment** — Google Trends interest tracker for 11 commodities with a live line chart and momentum indicators
- **Shortlist** — Save tickers for quick re-access (placeholder)

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (React), Recharts, Tailwind CSS |
| Backend | FastAPI (Python), Vercel serverless functions |
| Database | PostgreSQL (Neon) — all app and market data |
| Auth | Clerk |
| LLM | Claude API (Anthropic) — pending Research redesign |
| Price Data | TwelveData API (FMP fallback) |
| Financial Data | FMP stable API, SEC EDGAR XBRL |
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
│   ├── core/           # Config, cache, circuit breaker, exceptions
│   ├── db/             # SQLAlchemy ORM models + async session factory
│   ├── models/         # Canonical domain models (Pydantic)
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
| `DATABASE_URL` | Neon PostgreSQL pooled connection string |
| `DATABASE_URL_UNPOOLED` | Neon PostgreSQL direct connection (used for migrations) |
| `FMP_API_KEY` | Financial Modeling Prep API key |
| `FINNHUB_API_KEY` | Finnhub API key |
| `OPENFIGI_API_KEY` | OpenFIGI API key |
| `TD_API_KEY` | TwelveData API key |
| `ANTHROPIC_API_KEY` | Claude API key |
| `SEC_CONTACT_EMAIL` | Contact email for SEC EDGAR User-Agent header |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | Backend Vercel URL |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk frontend publishable key |
| `CLERK_SECRET_KEY` | Clerk backend secret key |

## Documentation

See [PROJECT_OUTLINE.md](PROJECT_OUTLINE.md) for full architecture, database schema, and feature spec.
