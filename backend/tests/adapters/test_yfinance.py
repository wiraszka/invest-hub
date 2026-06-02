from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from adapters.yfinance_adapter import YFinanceAdapter
from models.market_data import (
    CompanyIdentity,
    Financials,
    LeadershipData,
    MarketIntelligence,
    Quote,
)


@pytest.fixture
def adapter() -> YFinanceAdapter:
    return YFinanceAdapter()


def _mock_ticker(
    info: dict | None = None,
    financials: pd.DataFrame | None = None,
    balance_sheet: pd.DataFrame | None = None,
    cashflow: pd.DataFrame | None = None,
) -> MagicMock:
    ticker = MagicMock()
    ticker.info = info or {}
    ticker.financials = financials if financials is not None else pd.DataFrame()
    ticker.balance_sheet = (
        balance_sheet if balance_sheet is not None else pd.DataFrame()
    )
    ticker.cashflow = cashflow if cashflow is not None else pd.DataFrame()
    return ticker


class TestGetQuote:
    async def test_returns_quote_on_success(self, adapter: YFinanceAdapter) -> None:
        info = {"currentPrice": 185.5, "currency": "USD"}
        ticker = _mock_ticker(info=info)

        with patch.object(adapter, "_fetch_ticker", new=AsyncMock(return_value=ticker)):
            response = await adapter.get_quote("AAPL")

        assert response.data is not None
        assert isinstance(response.data, Quote)
        assert response.data.price == 185.5
        assert response.data.currency == "USD"
        assert response.provider == "yfinance"
        assert response.error is None

    async def test_uses_regularMarketPrice_fallback(
        self, adapter: YFinanceAdapter
    ) -> None:
        info = {"regularMarketPrice": 150.0, "currency": "USD"}
        ticker = _mock_ticker(info=info)

        with patch.object(adapter, "_fetch_ticker", new=AsyncMock(return_value=ticker)):
            response = await adapter.get_quote("AAPL")

        assert response.data is not None
        assert response.data.price == 150.0

    async def test_returns_error_when_no_price(self, adapter: YFinanceAdapter) -> None:
        ticker = _mock_ticker(info={"currency": "USD"})

        with patch.object(adapter, "_fetch_ticker", new=AsyncMock(return_value=ticker)):
            response = await adapter.get_quote("UNKNOWN")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_on_empty_info(self, adapter: YFinanceAdapter) -> None:
        ticker = _mock_ticker(info={})

        with patch.object(adapter, "_fetch_ticker", new=AsyncMock(return_value=ticker)):
            response = await adapter.get_quote("UNKNOWN")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_on_exception(self, adapter: YFinanceAdapter) -> None:
        with patch.object(
            adapter,
            "_fetch_ticker",
            new=AsyncMock(side_effect=RuntimeError("yf error")),
        ):
            response = await adapter.get_quote("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_when_circuit_is_open(
        self, adapter: YFinanceAdapter
    ) -> None:
        import time

        adapter._circuit._failures = adapter._circuit.failure_threshold
        adapter._circuit._opened_at = time.monotonic()

        response = await adapter.get_quote("AAPL")

        assert response.data is None
        assert response.error is not None


class TestGetFinancials:
    async def test_returns_financials_on_success(
        self, adapter: YFinanceAdapter
    ) -> None:
        import pandas as pd

        col = pd.Timestamp("2024-09-30")
        income_df = pd.DataFrame(
            {"Total Revenue": [400_000_000_000], "Net Income": [95_000_000_000]},
            index=[col],
        ).T
        info = {"financialCurrency": "USD"}
        ticker = _mock_ticker(info=info, financials=income_df)

        with patch.object(adapter, "_fetch_ticker", new=AsyncMock(return_value=ticker)):
            response = await adapter.get_financials("AAPL")

        assert response.data is not None
        assert isinstance(response.data, Financials)
        assert response.data.currency == "USD"
        assert len(response.data.income) == 1
        assert response.data.income[0].revenue == 400_000_000_000

    async def test_returns_financials_with_empty_dataframes(
        self, adapter: YFinanceAdapter
    ) -> None:
        info = {"financialCurrency": "USD"}
        ticker = _mock_ticker(info=info)

        with patch.object(adapter, "_fetch_ticker", new=AsyncMock(return_value=ticker)):
            response = await adapter.get_financials("AAPL")

        assert response.data is not None
        assert isinstance(response.data, Financials)
        assert response.data.income == []

    async def test_returns_error_on_exception(self, adapter: YFinanceAdapter) -> None:
        with patch.object(
            adapter,
            "_fetch_ticker",
            new=AsyncMock(side_effect=RuntimeError("yf error")),
        ):
            response = await adapter.get_financials("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_when_circuit_is_open(
        self, adapter: YFinanceAdapter
    ) -> None:
        import time

        adapter._circuit._failures = adapter._circuit.failure_threshold
        adapter._circuit._opened_at = time.monotonic()

        response = await adapter.get_financials("AAPL")

        assert response.data is None
        assert response.error is not None


class TestGetProfile:
    async def test_returns_profile_on_success(self, adapter: YFinanceAdapter) -> None:
        info = {
            "longName": "Apple Inc.",
            "exchange": "NMS",
            "currency": "USD",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "longBusinessSummary": "Apple designs consumer electronics.",
            "country": "United States",
            "fullTimeEmployees": 150000,
            "quoteType": "EQUITY",
        }
        ticker = _mock_ticker(info=info)

        with patch.object(adapter, "_fetch_ticker", new=AsyncMock(return_value=ticker)):
            response = await adapter.get_profile("AAPL")

        assert response.data is not None
        assert isinstance(response.data, CompanyIdentity)
        assert response.data.name == "Apple Inc."
        assert response.data.sector == "Technology"
        assert response.data.industry == "Consumer Electronics"
        assert response.data.country == "United States"
        assert response.data.employees == 150000
        assert response.data.security_type == "equity"
        assert response.error is None

    async def test_uses_shortName_fallback(self, adapter: YFinanceAdapter) -> None:
        info = {"shortName": "Apple", "exchange": "NMS", "currency": "USD"}
        ticker = _mock_ticker(info=info)

        with patch.object(adapter, "_fetch_ticker", new=AsyncMock(return_value=ticker)):
            response = await adapter.get_profile("AAPL")

        assert response.data is not None
        assert response.data.name == "Apple"

    async def test_normalizes_etf_security_type(self, adapter: YFinanceAdapter) -> None:
        info = {
            "longName": "SPDR S&P 500 ETF Trust",
            "exchange": "PCX",
            "currency": "USD",
            "quoteType": "ETF",
        }
        ticker = _mock_ticker(info=info)

        with patch.object(adapter, "_fetch_ticker", new=AsyncMock(return_value=ticker)):
            response = await adapter.get_profile("SPY")

        assert response.data is not None
        assert response.data.security_type == "etf"

    async def test_returns_error_when_no_name(self, adapter: YFinanceAdapter) -> None:
        ticker = _mock_ticker(info={"exchange": "NMS"})

        with patch.object(adapter, "_fetch_ticker", new=AsyncMock(return_value=ticker)):
            response = await adapter.get_profile("UNKNOWN")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_on_exception(self, adapter: YFinanceAdapter) -> None:
        with patch.object(
            adapter,
            "_fetch_ticker",
            new=AsyncMock(side_effect=RuntimeError("yf error")),
        ):
            response = await adapter.get_profile("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_when_circuit_is_open(
        self, adapter: YFinanceAdapter
    ) -> None:
        import time

        adapter._circuit._failures = adapter._circuit.failure_threshold
        adapter._circuit._opened_at = time.monotonic()

        response = await adapter.get_profile("AAPL")

        assert response.data is None
        assert response.error is not None


class TestGetLeadership:
    async def test_returns_leadership_on_success(
        self, adapter: YFinanceAdapter
    ) -> None:
        info = {
            "companyOfficers": [
                {"name": "Tim Cook", "title": "CEO", "age": 63, "totalPay": 63_200_000},
                {
                    "name": "Luca Maestri",
                    "title": "CFO",
                    "age": 60,
                    "totalPay": 25_000_000,
                },
            ],
            "heldPercentInsiders": 0.000721,
            "heldPercentInstitutions": 0.612345,
            "auditRisk": 4,
            "boardRisk": 3,
            "compensationRisk": 7,
            "overallRisk": 4,
        }

        with patch.object(adapter, "_fetch_info", new=AsyncMock(return_value=info)):
            response = await adapter.get_leadership("AAPL")

        assert response.data is not None
        assert isinstance(response.data, LeadershipData)
        assert len(response.data.officers) == 2
        assert response.data.officers[0].name == "Tim Cook"
        assert response.data.officers[0].title == "CEO"
        assert response.data.officers[0].age == 63
        assert response.data.officers[0].total_pay == 63_200_000
        assert response.data.held_percent_insiders == pytest.approx(0.000721)
        assert response.data.held_percent_institutions == pytest.approx(0.612345)
        assert response.data.audit_risk == 4
        assert response.data.board_risk == 3
        assert response.data.compensation_risk == 7
        assert response.data.overall_governance_risk == 4
        assert response.provider == "yfinance"
        assert response.error is None

    async def test_skips_officers_missing_name_or_title(
        self, adapter: YFinanceAdapter
    ) -> None:
        info = {
            "companyOfficers": [
                {"name": "Tim Cook", "title": "CEO"},
                {"name": "Unnamed Officer"},  # missing title
                {"title": "CTO"},  # missing name
            ],
        }

        with patch.object(adapter, "_fetch_info", new=AsyncMock(return_value=info)):
            response = await adapter.get_leadership("AAPL")

        assert response.data is not None
        assert len(response.data.officers) == 1
        assert response.data.officers[0].name == "Tim Cook"

    async def test_limits_officers_to_five(self, adapter: YFinanceAdapter) -> None:
        info = {
            "companyOfficers": [
                {"name": f"Officer {i}", "title": f"Title {i}"} for i in range(8)
            ]
        }

        with patch.object(adapter, "_fetch_info", new=AsyncMock(return_value=info)):
            response = await adapter.get_leadership("AAPL")

        assert response.data is not None
        assert len(response.data.officers) == 5

    async def test_returns_data_on_empty_info(self, adapter: YFinanceAdapter) -> None:
        with patch.object(adapter, "_fetch_info", new=AsyncMock(return_value={})):
            response = await adapter.get_leadership("AAPL")

        assert response.data is not None
        assert response.data.officers == []
        assert response.data.held_percent_insiders is None
        assert response.data.overall_governance_risk is None

    async def test_returns_error_on_exception(self, adapter: YFinanceAdapter) -> None:
        with patch.object(
            adapter, "_fetch_info", new=AsyncMock(side_effect=RuntimeError("yf error"))
        ):
            response = await adapter.get_leadership("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_when_circuit_is_open(
        self, adapter: YFinanceAdapter
    ) -> None:
        import time

        adapter._circuit._failures = adapter._circuit.failure_threshold
        adapter._circuit._opened_at = time.monotonic()

        response = await adapter.get_leadership("AAPL")

        assert response.data is None
        assert response.error is not None


class TestGetMarketIntelligence:
    async def test_returns_market_intelligence_on_success(
        self, adapter: YFinanceAdapter
    ) -> None:
        info = {
            "recommendationKey": "buy",
            "recommendationMean": 2.1,
            "numberOfAnalystOpinions": 42,
            "targetMeanPrice": 225.0,
            "targetMedianPrice": 220.0,
            "targetHighPrice": 260.0,
            "targetLowPrice": 180.0,
            "sharesShort": 95_000_000,
            "shortRatio": 2.4,
            "shortPercentOfFloat": 0.0063,
            "fiftyTwoWeekHigh": 237.23,
            "fiftyTwoWeekLow": 164.08,
            "fiftyDayAverage": 201.50,
            "twoHundredDayAverage": 195.30,
        }

        with patch.object(adapter, "_fetch_info", new=AsyncMock(return_value=info)):
            response = await adapter.get_market_intelligence("AAPL")

        assert response.data is not None
        assert isinstance(response.data, MarketIntelligence)
        assert response.data.recommendation == "buy"
        assert response.data.recommendation_score == pytest.approx(2.1)
        assert response.data.analyst_count == 42
        assert response.data.target_mean_price == pytest.approx(225.0)
        assert response.data.target_high_price == pytest.approx(260.0)
        assert response.data.target_low_price == pytest.approx(180.0)
        assert response.data.shares_short == 95_000_000
        assert response.data.short_ratio == pytest.approx(2.4)
        assert response.data.short_percent_of_float == pytest.approx(0.0063)
        assert response.data.fifty_two_week_high == pytest.approx(237.23)
        assert response.data.fifty_two_week_low == pytest.approx(164.08)
        assert response.data.fifty_day_average == pytest.approx(201.50)
        assert response.data.two_hundred_day_average == pytest.approx(195.30)
        assert response.provider == "yfinance"
        assert response.error is None

    async def test_returns_data_on_empty_info(self, adapter: YFinanceAdapter) -> None:
        with patch.object(adapter, "_fetch_info", new=AsyncMock(return_value={})):
            response = await adapter.get_market_intelligence("AAPL")

        assert response.data is not None
        assert response.data.recommendation is None
        assert response.data.analyst_count is None
        assert response.data.fifty_two_week_high is None

    async def test_returns_error_on_exception(self, adapter: YFinanceAdapter) -> None:
        with patch.object(
            adapter, "_fetch_info", new=AsyncMock(side_effect=RuntimeError("yf error"))
        ):
            response = await adapter.get_market_intelligence("AAPL")

        assert response.data is None
        assert response.error is not None

    async def test_returns_error_when_circuit_is_open(
        self, adapter: YFinanceAdapter
    ) -> None:
        import time

        adapter._circuit._failures = adapter._circuit.failure_threshold
        adapter._circuit._opened_at = time.monotonic()

        response = await adapter.get_market_intelligence("AAPL")

        assert response.data is None
        assert response.error is not None
