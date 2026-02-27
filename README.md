# Metals Retail Sentiment Dashboard

Streamlit dashboard using `pytrends` (Google Trends) as a retail sentiment proxy for:

- Gold
- Silver
- Platinum
- Copper
- Uranium

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Notes

- Google Trends data is normalized (`0-100`) within the selected timeframe/comparison set.
- "Sentiment Proxy" in the app is based on short-term momentum in search interest (7-period rolling average change).
