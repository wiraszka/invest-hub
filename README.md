# invest-hub

A personal investment research toolkit built around a Streamlit dashboard. Covers commodity retail sentiment, portfolio tracking, SEC filing downloads, and financial chart generation.

## Modules

- **app.py** — Main Streamlit dashboard (Commodities Retail Sentiment)
- **fetch-price-data/** — Live price fetching via TwelveData API and TradingEconomics scraper
- **sec-csa-downloader/** — SEC EDGAR filing downloader (10-K, 10-Q, 8-K, and more)
- **visualization-scripts/** — Reusable financial donut charts and animated loading spinner
- **ws-statement-parser/** — Wealthsimple statement parser and portfolio tracker

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

## Run

```bash
streamlit run app.py
```

## Commodities Sentiment Dashboard

Tracks Google Trends search interest as a retail sentiment proxy for 11 commodities:

Gold, Silver, Platinum, Copper, Uranium, Lithium, Nickel, Phosphate, Graphite, Zinc, Antimony

- Interest values are normalized (0–100) within the selected timeframe and comparison set
- Momentum is based on a 7-period rolling average of smoothed interest

## Environment Variables

| Variable | Description |
|---|---|
| `TD_API_KEY` | [TwelveData](https://twelvedata.com) API key for live price data |
