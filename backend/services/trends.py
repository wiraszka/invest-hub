from __future__ import annotations

from typing import Any

import pandas as pd
from pytrends.request import TrendReq

TIMEFRAME_OPTIONS: dict[str, str] = {
    "Past 1 week": "now 7-d",
    "Past 1 month": "today 1-m",
    "Past 3 months": "today 3-m",
    "Past 6 months": "custom-6m",
    "Past 12 months": "today 12-m",
    "Past 5 years": "today 5-y",
    "2004 to present": "all",
}


def _resolve_timeframe(label: str) -> str:
    if label == "Past 6 months":
        end_date = pd.Timestamp.today().normalize()
        start_date = end_date - pd.Timedelta(days=182)
        return f"{start_date.strftime('%Y-%m-%d')} {end_date.strftime('%Y-%m-%d')}"
    return TIMEFRAME_OPTIONS[label]


def fetch_trends_data(
    commodities: list[str],
    keyword_map: dict[str, str],
    timeframe_label: str,
    geo: str,
) -> dict[str, Any]:
    """
    Fetch Google Trends data for the given commodities and return:
    - series: wide-format list of {date, Commodity1, Commodity2, ...}
    - latest: list of {commodity, interest, momentum}
    """
    keywords = [keyword_map[c] for c in commodities]
    timeframe = _resolve_timeframe(timeframe_label)

    pytrends = TrendReq(hl="en-US", tz=360)
    pytrends.build_payload(keywords, timeframe=timeframe, geo=geo)
    raw = pytrends.interest_over_time()

    if raw.empty:
        return {"series": [], "latest": []}

    if "isPartial" in raw.columns:
        raw = raw.drop(columns=["isPartial"])

    # Rename keyword columns back to display names
    inverse_map = {v: k for k, v in keyword_map.items()}
    raw = raw.rename(columns=inverse_map)
    raw.index = pd.to_datetime(raw.index)
    raw = raw.sort_index()

    # Long format for momentum calculation
    long_df = raw.reset_index().rename(
        columns={"date": "Date", raw.index.name or "index": "Date"}
    )
    if "Date" not in long_df.columns:
        long_df = long_df.rename(columns={long_df.columns[0]: "Date"})
    long_df = long_df.melt(id_vars="Date", var_name="Commodity", value_name="Interest")
    long_df["Smoothed"] = (
        long_df.sort_values("Date")
        .groupby("Commodity")["Interest"]
        .transform(lambda s: s.rolling(window=7, min_periods=1).mean())
    )
    long_df["Momentum"] = long_df.groupby("Commodity")["Smoothed"].transform(
        lambda s: s.diff()
    )

    # Latest interest + momentum per commodity
    latest_df = (
        long_df.sort_values("Date")
        .groupby("Commodity", as_index=False)
        .tail(1)[["Commodity", "Interest", "Momentum"]]
        .sort_values("Interest", ascending=False)
    )
    latest = [
        {
            "commodity": row["Commodity"],
            "interest": int(row["Interest"]),
            "momentum": None
            if pd.isna(row["Momentum"])
            else round(float(row["Momentum"]), 1),
        }
        for _, row in latest_df.iterrows()
    ]

    # Wide-format series for the line chart
    series_df = raw.reset_index()
    date_col = series_df.columns[0]
    series_df = series_df.rename(columns={date_col: "date"})
    series_df["date"] = series_df["date"].dt.strftime("%Y-%m-%d")
    series = series_df.to_dict(orient="records")

    return {"series": series, "latest": latest}
