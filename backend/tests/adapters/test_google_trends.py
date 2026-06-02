from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from adapters.google_trends import GoogleTrendsAdapter
from models.market_data import TrendsResult


@pytest.fixture
def adapter() -> GoogleTrendsAdapter:
    return GoogleTrendsAdapter()


KEYWORD_MAP = {"Gold": "gold", "Silver": "silver"}


def _make_trends_df() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({"gold": range(50, 60), "silver": range(30, 40)}, index=dates)
    df.index.name = "date"
    return df


class TestFetch:
    async def test_returns_trends_result_on_success(
        self, adapter: GoogleTrendsAdapter
    ) -> None:
        with patch("adapters.google_trends.asyncio.to_thread") as mock_thread:
            from adapters.google_trends import _fetch_sync

            mock_thread.return_value = (
                _fetch_sync.__wrapped__ if hasattr(_fetch_sync, "__wrapped__") else None
            )

            with patch("adapters.google_trends._fetch_sync") as mock_fetch:
                from models.market_data import TrendsPoint

                mock_fetch.return_value = TrendsResult(
                    series=[{"date": "2024-01-10", "Gold": 59, "Silver": 39}],
                    latest=[
                        TrendsPoint(commodity="Gold", interest=59, momentum=1.0),
                        TrendsPoint(commodity="Silver", interest=39, momentum=1.0),
                    ],
                )
                mock_thread.return_value = mock_fetch.return_value

                with patch("asyncio.to_thread", return_value=mock_fetch.return_value):
                    response = await adapter.fetch(
                        commodities=["Gold", "Silver"],
                        keyword_map=KEYWORD_MAP,
                        timeframe_label="Past 1 month",
                        geo="",
                    )

        assert response.data is not None
        assert isinstance(response.data, TrendsResult)
        assert len(response.data.latest) == 2
        assert response.provider == "google_trends"
        assert response.error is None

    async def test_returns_error_on_exception(
        self, adapter: GoogleTrendsAdapter
    ) -> None:
        with patch(
            "adapters.google_trends.asyncio.to_thread",
            side_effect=RuntimeError("pytrends error"),
        ):
            response = await adapter.fetch(
                commodities=["Gold"],
                keyword_map=KEYWORD_MAP,
                timeframe_label="Past 1 month",
                geo="",
            )

        assert response.data is None
        assert response.error is not None


class TestFetchSync:
    def test_returns_empty_result_on_empty_dataframe(self) -> None:
        from adapters.google_trends import _fetch_sync

        with patch("adapters.google_trends.TrendReq") as mock_pytrends_cls:
            mock_pytrends = mock_pytrends_cls.return_value
            mock_pytrends.interest_over_time.return_value = pd.DataFrame()

            result = _fetch_sync(
                commodities=["Gold"],
                keyword_map=KEYWORD_MAP,
                timeframe_label="Past 1 month",
                geo="",
            )

        assert result.series == []
        assert result.latest == []

    def test_returns_trends_result_with_data(self) -> None:
        from adapters.google_trends import _fetch_sync

        mock_df = _make_trends_df()

        with patch("adapters.google_trends.TrendReq") as mock_pytrends_cls:
            mock_pytrends = mock_pytrends_cls.return_value
            mock_pytrends.interest_over_time.return_value = mock_df

            result = _fetch_sync(
                commodities=["Gold", "Silver"],
                keyword_map=KEYWORD_MAP,
                timeframe_label="Past 1 month",
                geo="",
            )

        assert isinstance(result, TrendsResult)
        assert len(result.series) == 10
        assert len(result.latest) == 2
        gold_latest = next(p for p in result.latest if p.commodity == "Gold")
        assert gold_latest.interest == 59
