from __future__ import annotations

from unittest.mock import patch

import pytest

from adapters.sec import SECAdapter
from models.market_data import CompanyIdentity, Financials


@pytest.fixture
def adapter() -> SECAdapter:
    return SECAdapter()


SUBMISSIONS_STUB = {
    "name": "APPLE INC",
    "exchanges": ["NASDAQ"],
    "filings": {
        "recent": {
            "form": ["10-K"],
            "accessionNumber": ["0000320193-23-000106"],
            "primaryDocument": ["aapl-20230930.htm"],
            "filingDate": ["2023-11-03"],
        }
    },
}

FACTS_STUB = (
    {
        "revenue": 383_285_000_000.0,
        "net_income": 96_995_000_000.0,
        "cash": 29_965_000_000.0,
        "total_debt": 109_280_000_000.0,
        "net_debt": 79_315_000_000.0,
        "operating_cash_flow": 110_543_000_000.0,
        "shares_outstanding": None,
    },
    "USD",
)


class TestGetFinancials:
    async def test_returns_financials_on_success(self, adapter: SECAdapter) -> None:
        with patch("adapters.sec.asyncio.to_thread") as mock_thread:
            from models.market_data import BalanceSheet, CashFlow, IncomeStatement

            mock_thread.return_value = Financials(
                currency="USD",
                income=[
                    IncomeStatement(
                        period="annual",
                        revenue=383_285_000_000.0,
                        net_income=96_995_000_000.0,
                    )
                ],
                balance_sheet=BalanceSheet(
                    period="annual", cash=29_965_000_000.0, total_debt=109_280_000_000.0
                ),
                cash_flow=[
                    CashFlow(period="annual", operating_cash_flow=110_543_000_000.0)
                ],
            )

            response = await adapter.get_financials("AAPL")

        assert response.data is not None
        assert isinstance(response.data, Financials)
        assert response.data.currency == "USD"
        assert response.provider == "sec"
        assert response.error is None

    async def test_returns_error_on_exception(self, adapter: SECAdapter) -> None:
        with patch(
            "adapters.sec.asyncio.to_thread",
            side_effect=ValueError("Ticker not found: FAKE"),
        ):
            response = await adapter.get_financials("FAKE")

        assert response.data is None
        assert response.error is not None
        assert "FAKE" in response.error


class TestGetProfile:
    async def test_returns_profile_on_success(self, adapter: SECAdapter) -> None:
        with patch("adapters.sec.asyncio.to_thread") as mock_thread:
            mock_thread.return_value = CompanyIdentity(
                name="APPLE INC", exchange="NASDAQ"
            )

            response = await adapter.get_profile("AAPL")

        assert response.data is not None
        assert isinstance(response.data, CompanyIdentity)
        assert response.data.name == "APPLE INC"
        assert response.data.exchange == "NASDAQ"
        assert response.provider == "sec"
        assert response.error is None

    async def test_returns_error_on_exception(self, adapter: SECAdapter) -> None:
        with patch(
            "adapters.sec.asyncio.to_thread",
            side_effect=ValueError("Ticker not found: FAKE"),
        ):
            response = await adapter.get_profile("FAKE")

        assert response.data is None
        assert response.error is not None


class TestFetchSync:
    def test_fetch_financials_sync_builds_financials(self) -> None:
        from adapters.sec import _fetch_financials_sync

        with patch("adapters.sec.sec_service.resolve_cik", return_value="0000320193"):
            with patch(
                "adapters.sec.sec_service.get_submissions",
                return_value=SUBMISSIONS_STUB,
            ):
                with patch(
                    "adapters.sec.sec_service.find_recent_annual",
                    return_value=("acc", "doc", "10-K", "2023-11-03"),
                ):
                    with patch(
                        "adapters.sec.sec_service.get_xbrl_facts",
                        return_value=FACTS_STUB,
                    ):
                        result = _fetch_financials_sync("AAPL")

        assert isinstance(result, Financials)
        assert result.currency == "USD"
        assert result.income[0].revenue == 383_285_000_000.0
        assert result.balance_sheet is not None
        assert result.balance_sheet.cash == 29_965_000_000.0
        assert result.cash_flow[0].operating_cash_flow == 110_543_000_000.0

    def test_fetch_profile_sync_builds_identity(self) -> None:
        from adapters.sec import _fetch_profile_sync

        with patch("adapters.sec.sec_service.resolve_cik", return_value="0000320193"):
            with patch(
                "adapters.sec.sec_service.get_submissions",
                return_value=SUBMISSIONS_STUB,
            ):
                result = _fetch_profile_sync("AAPL")

        assert isinstance(result, CompanyIdentity)
        assert result.name == "APPLE INC"
        assert result.exchange == "NASDAQ"


class TestUnsupportedMethods:
    async def test_get_quote_returns_error(self, adapter: SECAdapter) -> None:
        response = await adapter.get_quote("AAPL")

        assert response.data is None
        assert response.error is not None
