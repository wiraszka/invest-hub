# invest-hub

Personal investment tracking and stock research platform. Upload brokerage transaction history to track positions and portfolio composition, view live prices, and monitor commodity sentiment trends. Built on FastAPI + Next.js, deployed on Vercel.

## Features

- **Investments** — Upload Wealthsimple or Questrade transaction history; track open positions, cost basis, realized P/L, and portfolio composition via donut charts.
- **Symbol page** — Live price chart for any ticker (TwelveData → FMP fallback)
- **Research** — Search any SEC-registered ticker; AI analysis pipeline in active redesign
- **Commodities Sentiment** — Google Trends interest for 11 commodities with momentum indicators and a line chart
- **Shortlist** — Placeholder

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (React), Recharts, Tailwind CSS |
| Backend | FastAPI (Python), Vercel serverless functions |
| Database | PostgreSQL (Neon) |
| Auth | Clerk |
| Data providers | TwelveData, FMP, Finnhub, yfinance, SEC EDGAR, Google Trends, OpenFIGI |

See [PROJECT_OUTLINE.md](PROJECT_OUTLINE.md) for full architecture, database schema, and feature spec.

## Setup

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
uvicorn api.index:app --reload
```

### Frontend

```bash
cd frontend
pnpm install
cp .env.local.example .env.local   # fill in keys
pnpm dev
```

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `DATABASE_URL` | Neon PostgreSQL pooled connection string |
| `DATABASE_URL_UNPOOLED` | Neon PostgreSQL direct connection (used for Alembic migrations) |
| `FMP_API_KEY` | Financial Modeling Prep |
| `FINNHUB_API_KEY` | Finnhub |
| `OPENFIGI_API_KEY` | OpenFIGI |
| `TD_API_KEY` | TwelveData |
| `ANTHROPIC_API_KEY` | Claude API |
| `SEC_CONTACT_EMAIL` | Contact email for SEC EDGAR `User-Agent` header |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | Backend Vercel URL |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk frontend publishable key |
| `CLERK_SECRET_KEY` | Clerk backend secret key |

## Database Migrations

```bash
cd backend
alembic upgrade head
```
