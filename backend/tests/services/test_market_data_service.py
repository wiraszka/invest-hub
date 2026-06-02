from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from models.market_data import BalanceSheet, CashFlow, Financials, IncomeStatement
from services.market_data_service import _financials_sufficient


def _make_financials(
    income: bool = False,
    balance_sheet: bool = False,
    cash_flow: bool = False,
) -> Financials:
    return Financials(
        currency="USD",
        income=[IncomeStatement(period="FY2024", revenue=1_000_000.0)]
        if income
        else [],
        balance_sheet=BalanceSheet(period="FY2024", cash=100_000.0)
        if balance_sheet
        else None,
        cash_flow=[CashFlow(period="FY2024", free_cash_flow=50_000.0)]
        if cash_flow
        else [],
    )


class TestFinancialsSufficient:
    def test_returns_true_when_income_present(self) -> None:
        data = _make_financials(income=True)

        assert _financials_sufficient(data) is True

    def test_returns_true_when_only_balance_sheet_present(self) -> None:
        data = _make_financials(balance_sheet=True)

        assert _financials_sufficient(data) is True

    def test_returns_true_when_only_cash_flow_present(self) -> None:
        data = _make_financials(cash_flow=True)

        assert _financials_sufficient(data) is True

    def test_returns_false_when_all_empty(self) -> None:
        data = _make_financials()

        assert _financials_sufficient(data) is False

    def test_returns_true_when_all_present(self) -> None:
        data = _make_financials(income=True, balance_sheet=True, cash_flow=True)

        assert _financials_sufficient(data) is True


class TestGetFinancialsHollowFallthrough:
    async def test_falls_through_to_fmp_when_yfinance_returns_hollow_response(
        self,
    ) -> None:
        hollow = _make_financials()
        full = _make_financials(income=True, balance_sheet=True, cash_flow=True)

        yfinance_response = MagicMock()
        yfinance_response.data = hollow
        yfinance_response.raw = {}
        yfinance_adapter = MagicMock()
        yfinance_adapter.name = "yfinance"
        yfinance_adapter.get_financials = AsyncMock(return_value=yfinance_response)

        fmp_response = MagicMock()
        fmp_response.data = full
        fmp_response.raw = {}
        fmp_adapter = MagicMock()
        fmp_adapter.name = "fmp"
        fmp_adapter.get_financials = AsyncMock(return_value=fmp_response)

        registry = MagicMock()
        registry.for_capability.return_value = [yfinance_adapter, fmp_adapter]

        from services.market_data_service import MarketDataService

        svc = MarketDataService(registry)
        mock_session = MagicMock()

        with patch("services.market_data_service.cache") as mock_cache:
            mock_cache.get.return_value = None
            result = await svc.get_financials("AAPL", None, mock_session)

        assert result is full
        yfinance_adapter.get_financials.assert_awaited_once()
        fmp_adapter.get_financials.assert_awaited_once()
