from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.market_data import (
    BalanceSheet,
    CashFlow,
    CompanyIdentity,
    Financials,
    IncomeStatement,
    KeyMetrics,
    Quote,
)
from services.analysis.context_builder import (
    StructuredContext,
    _classify_template,
    _fmt,
    _pct,
    _yoy,
    build,
)


def _make_financials() -> Financials:
    return Financials(
        canonical_id="abc-123",
        currency="USD",
        income=[
            IncomeStatement(
                period="FY2024",
                fiscal_year=2024,
                revenue=1_000_000_000.0,
                gross_profit=400_000_000.0,
                operating_income=200_000_000.0,
                ebitda=250_000_000.0,
                net_income=150_000_000.0,
            ),
            IncomeStatement(
                period="FY2023",
                fiscal_year=2023,
                revenue=800_000_000.0,
                gross_profit=310_000_000.0,
                operating_income=160_000_000.0,
                ebitda=200_000_000.0,
                net_income=120_000_000.0,
            ),
        ],
        balance_sheet=BalanceSheet(
            period="FY2024",
            cash=300_000_000.0,
            total_debt=100_000_000.0,
            net_debt=-200_000_000.0,
            total_equity=900_000_000.0,
            total_assets=1_200_000_000.0,
        ),
        cash_flow=[
            CashFlow(
                period="FY2024",
                operating_cash_flow=180_000_000.0,
                capex=30_000_000.0,
                free_cash_flow=150_000_000.0,
            )
        ],
        metrics=KeyMetrics(
            period="FY2024",
            market_cap=2_000_000_000.0,
            enterprise_value=1_800_000_000.0,
            pe_ratio=13.3,
            ev_ebitda=7.2,
            price_to_book=2.2,
            roe=0.167,
        ),
    )


def _make_quote() -> Quote:
    return Quote(
        symbol="AAPL",
        price=150.25,
        currency="USD",
        source="twelvedata",
        fetched_at=datetime.now(timezone.utc),
    )


def _make_profile() -> CompanyIdentity:
    return CompanyIdentity(
        canonical_id="abc-123",
        name="Apple Inc.",
        exchange="NASDAQ",
        currency="USD",
    )


class TestBuild:
    async def test_returns_structured_context_on_success(self) -> None:
        mock_session = MagicMock()
        financials = _make_financials()
        quote = _make_quote()
        profile = _make_profile()

        with (
            patch("services.analysis.context_builder.MarketDataService") as mock_svc_cls,
            patch("services.analysis.context_builder.asyncio.to_thread", new=AsyncMock(return_value="filing text")),
        ):
            mock_svc = mock_svc_cls.return_value
            mock_svc.get_financials = AsyncMock(return_value=financials)
            mock_svc.get_quote = AsyncMock(return_value=quote)
            mock_svc.get_profile = AsyncMock(return_value=profile)

            result = await build("AAPL", mock_session)

        assert isinstance(result, StructuredContext)
        assert result.ticker == "AAPL"
        assert result.company_name == "Apple Inc."
        assert result.exchange == "NASDAQ"
        assert result.currency == "USD"
        assert result.canonical_id == "abc-123"
        assert result.template_key != ""
        assert "Revenue" in result.metrics_block
        assert result.filing_excerpt == "filing text"

    async def test_filing_failure_does_not_raise(self) -> None:
        mock_session = MagicMock()
        financials = _make_financials()
        quote = _make_quote()

        with (
            patch("services.analysis.context_builder.MarketDataService") as mock_svc_cls,
            patch("services.analysis.context_builder.asyncio.to_thread", new=AsyncMock(side_effect=ValueError("no CIK"))),
        ):
            mock_svc = mock_svc_cls.return_value
            mock_svc.get_financials = AsyncMock(return_value=financials)
            mock_svc.get_quote = AsyncMock(return_value=quote)
            mock_svc.get_profile = AsyncMock(side_effect=Exception("profile unavailable"))

            result = await build("AAPL", mock_session)

        assert result.filing_excerpt == ""
        assert result.company_name == "AAPL"

    async def test_raises_when_both_financials_and_quote_unavailable(self) -> None:
        from core.exceptions import ProviderUnavailableError

        mock_session = MagicMock()

        with (
            patch("services.analysis.context_builder.MarketDataService") as mock_svc_cls,
            patch("services.analysis.context_builder.asyncio.to_thread", new=AsyncMock(return_value="")),
        ):
            mock_svc = mock_svc_cls.return_value
            mock_svc.get_financials = AsyncMock(side_effect=Exception("down"))
            mock_svc.get_quote = AsyncMock(side_effect=Exception("down"))
            mock_svc.get_profile = AsyncMock(side_effect=Exception("down"))

            with pytest.raises(ProviderUnavailableError):
                await build("AAPL", mock_session)


class TestMetricFormatters:
    def test_fmt_billions(self) -> None:
        assert _fmt(1_500_000_000.0) == "$1.50B"

    def test_fmt_millions(self) -> None:
        assert _fmt(42_000_000.0) == "$42.0M"

    def test_fmt_negative(self) -> None:
        assert _fmt(-50_000_000.0) == "-$50.0M"

    def test_fmt_none(self) -> None:
        assert _fmt(None) == "N/A"

    def test_pct_normal(self) -> None:
        assert _pct(40_000_000.0, 100_000_000.0) == "40.0%"

    def test_pct_zero_denominator(self) -> None:
        assert _pct(100.0, 0.0) == "N/A"

    def test_pct_none(self) -> None:
        assert _pct(None, 100.0) == "N/A"

    def test_yoy_positive(self) -> None:
        result = _yoy(110.0, 100.0)

        assert "+10.0% YoY" in result

    def test_yoy_negative(self) -> None:
        result = _yoy(90.0, 100.0)

        assert "-10.0% YoY" in result

    def test_yoy_none_prior(self) -> None:
        assert _yoy(100.0, None) == ""


class TestMetricsBlock:
    def test_includes_revenue_with_yoy(self) -> None:
        financials = _make_financials()
        quote = _make_quote()

        context = StructuredContext(
            ticker="AAPL",
            company_name="Apple Inc.",
            exchange="NASDAQ",
            currency="USD",
            canonical_id="abc-123",
            template_key="general",
            sector="Technology",
            industry="Software",
            metrics_block="",
            filing_excerpt="",
        )

        from services.analysis.context_builder import _format_metrics

        block = _format_metrics("AAPL", financials, quote)

        assert "Revenue" in block
        assert "+25.0% YoY" in block
        assert "40.0%" in block

    def test_net_cash_label_when_negative_net_debt(self) -> None:
        financials = _make_financials()

        from services.analysis.context_builder import _format_metrics

        block = _format_metrics("AAPL", financials, None)

        assert "Net cash" in block

    def test_no_financials_returns_minimal_block(self) -> None:
        from services.analysis.context_builder import _format_metrics

        block = _format_metrics("AAPL", None, _make_quote())

        assert "No financial data available" in block


class TestClassifyTemplate:
    def _profile(self, sector: str | None, industry: str | None, security_type: str | None = None) -> CompanyIdentity:
        return CompanyIdentity(name="Test Co", sector=sector, industry=industry, security_type=security_type)

    def test_etf_security_type_returns_etf(self) -> None:
        profile = self._profile("Financials", None, security_type="etf")
        assert _classify_template(profile, None) == "etf"

    def test_mutualfund_security_type_returns_etf(self) -> None:
        profile = self._profile(None, None, security_type="mutualfund")
        assert _classify_template(profile, None) == "etf"

    def test_mining_sector_with_revenue_returns_mining(self) -> None:
        profile = self._profile("Basic Materials", "Gold Mining")
        financials = Financials(currency="USD", income=[
            IncomeStatement(period="FY2024", revenue=50_000_000)
        ])
        assert _classify_template(profile, financials) == "mining"

    def test_mining_sector_without_revenue_returns_pre_revenue_mining(self) -> None:
        profile = self._profile("Basic Materials", "Gold Mining")
        financials = Financials(currency="USD", income=[
            IncomeStatement(period="FY2024", revenue=0)
        ])
        assert _classify_template(profile, financials) == "pre_revenue_mining"

    def test_biotech_industry_with_revenue_returns_biotech(self) -> None:
        profile = self._profile("Healthcare", "Biotechnology")
        financials = Financials(currency="USD", income=[
            IncomeStatement(period="FY2024", revenue=100_000_000)
        ])
        assert _classify_template(profile, financials) == "biotech"

    def test_energy_sector_with_revenue_returns_energy(self) -> None:
        profile = self._profile("Energy", "Oil & Gas")
        financials = Financials(currency="USD", income=[
            IncomeStatement(period="FY2024", revenue=500_000_000)
        ])
        assert _classify_template(profile, financials) == "energy"

    def test_tech_sector_with_revenue_returns_tech(self) -> None:
        profile = self._profile("Technology", "Software")
        financials = Financials(currency="USD", income=[
            IncomeStatement(period="FY2024", revenue=1_000_000_000)
        ])
        assert _classify_template(profile, financials) == "tech"

    def test_no_sector_with_revenue_returns_general(self) -> None:
        profile = self._profile(None, None)
        financials = Financials(currency="USD", income=[
            IncomeStatement(period="FY2024", revenue=200_000_000)
        ])
        assert _classify_template(profile, financials) == "general"

    def test_no_sector_without_revenue_returns_pre_revenue(self) -> None:
        assert _classify_template(None, None) == "pre_revenue"

    def test_no_financials_returns_pre_revenue(self) -> None:
        profile = self._profile("Technology", "Software")
        assert _classify_template(profile, None) == "pre_revenue"
