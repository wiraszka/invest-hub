from __future__ import annotations

from typing import List

import pandas as pd
from pytrends.request import TrendReq
import streamlit as st

from constants import TIMEFRAME_OPTIONS


def resolve_timeframe(timeframe_label: str) -> str:
    if timeframe_label == "Past 6 months":
        end_date = pd.Timestamp.today().normalize()
        start_date = end_date - pd.Timedelta(days=182)
        return f"{start_date.strftime('%Y-%m-%d')} {end_date.strftime('%Y-%m-%d')}"
    return TIMEFRAME_OPTIONS[timeframe_label]


@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_trends(
    keywords: List[str],
    timeframe_label: str,
    geo: str,
    tz_minutes: int = 360,
) -> pd.DataFrame:
    pytrends = TrendReq(hl="en-US", tz=tz_minutes)
    timeframe = resolve_timeframe(timeframe_label)

    pytrends.build_payload(keywords, timeframe=timeframe, geo=geo)
    data = pytrends.interest_over_time()

    if data.empty:
        return data

    if "isPartial" in data.columns:
        data = data.drop(columns=["isPartial"])

    data.index = pd.to_datetime(data.index)
    return data.sort_index()


def to_long(df: pd.DataFrame) -> pd.DataFrame:
    long_df = df.reset_index().rename(columns={"date": "Date"})
    if "Date" not in long_df.columns:
        long_df = long_df.rename(columns={long_df.columns[0]: "Date"})

    long_df = long_df.melt(id_vars="Date", var_name="Commodity", value_name="Interest")
    return long_df


def add_momentum_metrics(df_long: pd.DataFrame) -> pd.DataFrame:
    out = df_long.copy()
    out["Smoothed Interest"] = (
        out.sort_values("Date")
        .groupby("Commodity")["Interest"]
        .transform(lambda s: s.rolling(window=7, min_periods=1).mean())
    )
    out["Momentum"] = out.groupby("Commodity")["Smoothed Interest"].transform(lambda s: s.diff())
    return out
