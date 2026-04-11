import os
from pathlib import Path
import requests
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from twelvedata import TDClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
TD_API_KEY = os.environ["TD_API_KEY"]

td = TDClient(apikey=TD_API_KEY)

# ── Fetch current price ────────────────────────────────────────────────────────

ticker = "EU"

price = td.price(symbol=ticker).as_json()
print(f"Current price for {ticker}: {price}")

# ── Plot time series (1-year) ──────────────────────────────────────────────────

ticker = "NNE"

params = {
    "symbol": ticker,
    "interval": "1day",
    "outputsize": 365,
    "apikey": TD_API_KEY,
}

url = "https://api.twelvedata.com/time_series"
response = requests.get(url, params=params)
data = response.json()

if "values" not in data:
    print("Error:", data)
    exit()

df = pd.DataFrame(data["values"])
df["datetime"] = pd.to_datetime(df["datetime"])
df = df.sort_values("datetime")
df["close"] = df["close"].astype(float)

plt.figure(figsize=(12, 5))
plt.plot(df["datetime"], df["close"])
plt.title(f"{ticker} Closing Prices - Last 1 Year")
plt.xlabel("Date")
plt.ylabel("Closing Price (USD)")
plt.grid(True)
plt.show()

output_path = Path(__file__).parent / "price-data-1yr" / f"{ticker}.csv"
output_path.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(output_path, index=False)
print(f"Saved CSV to: {output_path}")
