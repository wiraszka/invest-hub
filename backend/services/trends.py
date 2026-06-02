from __future__ import annotations

from typing import Any

from adapters.google_trends import TIMEFRAME_OPTIONS, GoogleTrendsAdapter

__all__ = ["TIMEFRAME_OPTIONS", "fetch_trends_data"]

_adapter = GoogleTrendsAdapter()


async def fetch_trends_data(
    commodities: list[str],
    keyword_map: dict[str, str],
    timeframe_label: str,
    geo: str,
) -> dict[str, Any]:
    response = await _adapter.fetch(commodities, keyword_map, timeframe_label, geo)
    if response.data is None:
        raise ValueError(response.error or "Google Trends fetch failed")
    return {
        "series": response.data.series,
        "latest": [p.model_dump() for p in response.data.latest],
    }
