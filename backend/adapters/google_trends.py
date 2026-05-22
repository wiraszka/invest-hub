from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import pandas as pd
from pytrends.request import TrendReq

from models.market_data import ProviderResponse, TrendsPoint, TrendsResult

TIMEFRAME_OPTIONS: dict[str, str] = {
    "Past 1 week": "now 7-d",
    "Past 1 month": "today 1-m",
    "Past 3 months": "today 3-m",
    "Past 6 months": "custom-6m",
    "Past 12 months": "today 12-m",
    "Past 5 years": "today 5-y",
    "2004 to present": "all",
}

logger = logging.getLogger(__name__)


class GoogleTrendsAdapter:
    name = "google_trends"

    async def fetch(
        self,
        commodities: list[str],
        keyword_map: dict[str, str],
        timeframe_label: str,
        geo: str,
    ) -> ProviderResponse[TrendsResult]:
        fetched_at = datetime.now(timezone.utc)
        try:
            result = await asyncio.to_thread(
                _fetch_sync, commodities, keyword_map, timeframe_label, geo,
            )
            return ProviderResponse(data=result, raw={}, provider=self.name, fetched_at=fetched_at)
        except Exception as exc:
            logger.exception("google_trends fetch error")
            return ProviderResponse(data=None, raw={}, provider=self.name, fetched_at=fetched_at, error=str(exc))


def _resolve_timeframe(label: str) -> str:
    if label == "Past 6 months":
        end_date = pd.Timestamp.today().normalize()
        start_date = end_date - pd.Timedelta(days=182)
        return f"{start_date.strftime('%Y-%m-%d')} {end_date.strftime('%Y-%m-%d')}"
    return TIMEFRAME_OPTIONS[label]


def _fetch_sync(
    commodities: list[str],
    keyword_map: dict[str, str],
    timeframe_label: str,
    geo: str,
) -> TrendsResult:
    keywords = [keyword_map[commodity] for commodity in commodities]
    timeframe = _resolve_timeframe(timeframe_label)

    pytrends = TrendReq(
        hl="en-US",
        tz=360,
        retries=5,
        backoff_factor=2,
        requests_args={
            "headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
        },
    )
    pytrends.build_payload(keywords, timeframe=timeframe, geo=geo)
    raw_df = pytrends.interest_over_time()

    if raw_df.empty:
        return TrendsResult(series=[], latest=[])

    if "isPartial" in raw_df.columns:
        raw_df = raw_df.drop(columns=["isPartial"])

    inverse_map = {v: k for k, v in keyword_map.items()}
    raw_df = raw_df.rename(columns=inverse_map)
    raw_df.index = pd.to_datetime(raw_df.index)
    raw_df = raw_df.sort_index()

    long_df = raw_df.reset_index().rename(
        columns={"date": "Date", raw_df.index.name or "index": "Date"}
    )
    if "Date" not in long_df.columns:
        long_df = long_df.rename(columns={long_df.columns[0]: "Date"})
    long_df = long_df.melt(id_vars="Date", var_name="Commodity", value_name="Interest")
    long_df["Smoothed"] = (
        long_df.sort_values("Date")
        .groupby("Commodity")["Interest"]
        .transform(lambda series: series.rolling(window=7, min_periods=1).mean())
    )
    long_df["Momentum"] = long_df.groupby("Commodity")["Smoothed"].transform(
        lambda series: series.diff()
    )

    latest_df = (
        long_df.sort_values("Date")
        .groupby("Commodity", as_index=False)
        .tail(1)[["Commodity", "Interest", "Momentum"]]
        .sort_values("Interest", ascending=False)
    )
    latest = [
        TrendsPoint(
            commodity=row["Commodity"],
            interest=int(row["Interest"]),
            momentum=None if pd.isna(row["Momentum"]) else round(float(row["Momentum"]), 1),
        )
        for _, row in latest_df.iterrows()
    ]

    series_df = raw_df.reset_index()
    date_col = series_df.columns[0]
    series_df = series_df.rename(columns={date_col: "date"})
    series_df["date"] = series_df["date"].dt.strftime("%Y-%m-%d")
    series = series_df.to_dict(orient="records")

    return TrendsResult(series=series, latest=latest)
