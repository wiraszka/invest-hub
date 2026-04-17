# invest-hub

A personal investment research platform built on a FastAPI backend and Next.js frontend, deployed on Vercel.

## Features

- **Research** — Search any SEC-registered company, trigger an LLM-driven analysis pipeline, and view a Company Snapshot, key financial metrics, charts, and a Data Integrity summary
- **Commodities Sentiment** — Google Trends interest tracker for 11 commodities with a live line chart and momentum indicators
- **Shortlist** — Save companies for quick re-access (in progress)
- **Investments** — Personal portfolio tracking via Wealthsimple integration (in progress)

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (React), Recharts, Tailwind CSS |
| Backend | FastAPI (Python), Vercel serverless functions |
| Database | MongoDB Atlas |
| Auth | Clerk |
| LLM | Claude API (Anthropic) |
| Price Data | TwelveData API |
| Filing Data | SEC EDGAR API (submissions + XBRL) |
| Sentiment Data | Google Trends (pytrends) |

## Project Structure

```
invest-hub/
├── frontend/          # Next.js app
├── backend/           # FastAPI app
│   ├── api/           # Entry point (index.py)
│   ├── routers/       # Route handlers
│   └── services/      # Business logic
└── PROJECT_OUTLINE.md # Full architecture and feature spec
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
npm install
cp .env.local.example .env.local  # fill in keys
npm run dev
```

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `MONGODB_URI` | MongoDB Atlas connection string |
| `TD_API_KEY` | TwelveData API key |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | Backend Vercel URL (e.g. `https://invest-hub-backend.vercel.app`) |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk frontend publishable key |
| `CLERK_SECRET_KEY` | Clerk backend secret key |

## Documentation

See [PROJECT_OUTLINE.md](PROJECT_OUTLINE.md) for full architecture, pipeline design, and feature spec.
