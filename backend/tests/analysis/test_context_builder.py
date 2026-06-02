from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.market_data import (
    BalanceSheet,
    CashFlow,
    CompanyIdentity,
    CompanyOfficer,
    Financials,
    IncomeStatement,
    KeyMetrics,
    LeadershipData,
    MarketIntelligence,
    Quote,
)
from services.analysis.context_builder import (
    StructuredContext,
    _classify_template,
    _fmt,
    _format_leadership,
    _format_market_intelligence,
    _pct,
    _yoy,
    build,
)


def _make_financials() -> Financials:
    return Financials(
        security_id="abc-123",
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
        security_id="abc-123",
        name="Apple Inc.",
        exchange="NASDAQ",
        currency="USD",
    )


def _make_identity() -> CompanyIdentity:
    return CompanyIdentity(
        security_id="abc-123",
        name="Apple Inc.",
        exchange="NASDAQ",
        currency="USD",
    )


def _patch_fetch_providers(
    identity: CompanyIdentity,
    financials: "Financials | None",
    quote: "Quote | None",
    profile: "CompanyIdentity | None" = None,
    leadership: "LeadershipData | None" = None,
    market_intelligence: "MarketIntelligence | None" = None,
):
    """Return a context manager that patches all fetch_providers dependencies."""
    from contextlib import ExitStack

    # Map service method objects → return values so the side effect can
    # identify which capability is being requested without a "key" string.
    def _adapter_side_effect(method, ticker: str, security_id):
        from services.market_data_service import MarketDataService

        svc = MarketDataService.__new__(MarketDataService)
        mapping = {
            svc.get_financials.__func__: financials,
            svc.get_quote.__func__: quote,
            svc.get_profile.__func__: profile,
            svc.get_leadership.__func__: leadership,
            svc.get_market_intelligence.__func__: market_intelligence,
        }
        # method is a bound method; look up by its underlying function
        result = mapping.get(method.__func__)
        if result is None:
            raise Exception(f"unavailable: {method.__name__}")
        return result

    stack = ExitStack()
    stack.enter_context(
        patch(
            "services.analysis.context_builder.resolve_identity",
            new=AsyncMock(return_value=identity),
        )
    )
    stack.enter_context(
        patch(
            "services.analysis.context_builder._load_financials_from_db",
            new=AsyncMock(return_value=None),
        )
    )
    stack.enter_context(
        patch(
            "services.analysis.context_builder._load_quote_from_db",
            new=AsyncMock(return_value=None),
        )
    )
    stack.enter_context(
        patch(
            "services.analysis.context_builder._load_leadership_from_db",
            new=AsyncMock(return_value=None),
        )
    )
    stack.enter_context(
        patch(
            "services.analysis.context_builder._load_market_intelligence_from_db",
            new=AsyncMock(return_value=None),
        )
    )
    stack.enter_context(
        patch(
            "services.analysis.context_builder._service_call_with_own_session",
            side_effect=AsyncMock(side_effect=_adapter_side_effect),
        )
    )
    return stack


class TestBuild:
    """Tests for build() / fetch_providers() — provider data fetching only.

    The SEC filing is no longer fetched here (moved to filing_service /
    run_filing).  filing_excerpt is always "" from fetch_providers().
    """

    async def test_returns_structured_context_on_success(self) -> None:
        mock_session = MagicMock()
        financials = _make_financials()
        quote = _make_quote()
        profile = _make_profile()
        identity = _make_identity()

        with _patch_fetch_providers(identity, financials, quote, profile):
            result = await build("AAPL", mock_session)

        assert isinstance(result, StructuredContext)
        assert result.ticker == "AAPL"
        assert result.company_name == "Apple Inc."
        assert result.exchange == "NASDAQ"
        assert result.currency == "USD"
        assert result.security_id == "abc-123"
        # fetch_providers() no longer classifies — template_key is always ""
        assert result.template_key == ""
        assert "Revenue" in result.metrics_block
        # Filing is no longer fetched by build() — always empty
        assert result.filing_excerpt == ""
        assert result.leadership_block == ""
        assert result.market_intelligence_block == ""

    async def test_leadership_and_market_intelligence_populate_blocks(self) -> None:
        mock_session = MagicMock()
        financials = _make_financials()
        quote = _make_quote()
        profile = _make_profile()
        identity = _make_identity()
        leadership = LeadershipData(
            officers=[
                CompanyOfficer(
                    name="Tim Cook", title="CEO", age=63, total_pay=63_000_000
                )
            ],
            held_percent_insiders=0.0007,
            audit_risk=4,
        )
        mi = MarketIntelligence(
            recommendation="buy",
            recommendation_score=2.1,
            analyst_count=42,
            fifty_two_week_high=237.23,
            fifty_two_week_low=164.08,
        )

        with _patch_fetch_providers(
            identity, financials, quote, profile, leadership, mi
        ):
            result = await build("AAPL", mock_session)

        assert "Tim Cook" in result.leadership_block
        assert "CEO" in result.leadership_block
        assert "buy" in result.market_intelligence_block
        assert "237.23" in result.market_intelligence_block

    async def test_leadership_failure_does_not_raise(self) -> None:
        mock_session = MagicMock()
        financials = _make_financials()
        quote = _make_quote()
        identity = _make_identity()

        with _patch_fetch_providers(identity, financials, quote):
            result = await build("AAPL", mock_session)

        assert result.leadership_block == ""
        assert result.market_intelligence_block == ""
        assert result.company_name == "Apple Inc."

    async def test_raises_when_both_financials_and_quote_unavailable(self) -> None:
        from core.exceptions import ProviderUnavailableError

        mock_session = MagicMock()
        identity = _make_identity()

        with _patch_fetch_providers(identity, None, None):
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

        _context = StructuredContext(
            ticker="AAPL",
            company_name="Apple Inc.",
            exchange="NASDAQ",
            currency="USD",
            security_id="abc-123",
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


class TestFormatLeadership:
    def test_returns_empty_string_for_none(self) -> None:
        assert _format_leadership(None) == ""

    def test_includes_officer_name_and_title(self) -> None:
        leadership = LeadershipData(
            officers=[
                CompanyOfficer(
                    name="Tim Cook", title="CEO", age=63, total_pay=63_000_000
                )
            ]
        )
        block = _format_leadership(leadership)
        assert "Tim Cook" in block
        assert "CEO" in block
        assert "63" in block
        assert "63,000,000" in block

    def test_includes_ownership_percentages(self) -> None:
        leadership = LeadershipData(
            held_percent_insiders=0.000721,
            held_percent_institutions=0.612345,
        )
        block = _format_leadership(leadership)
        assert "0.07%" in block
        assert "61.23%" in block

    def test_includes_governance_risk_scores(self) -> None:
        leadership = LeadershipData(
            audit_risk=4, board_risk=3, compensation_risk=7, overall_governance_risk=4
        )
        block = _format_leadership(leadership)
        assert "Audit: 4" in block
        assert "Board: 3" in block
        assert "Overall: 4" in block

    def test_empty_leadership_returns_header_only(self) -> None:
        block = _format_leadership(LeadershipData())
        assert "Leadership" in block


class TestFormatMarketIntelligence:
    def test_returns_empty_string_for_none(self) -> None:
        assert _format_market_intelligence(None) == ""

    def test_includes_analyst_recommendation(self) -> None:
        mi = MarketIntelligence(
            recommendation="buy", recommendation_score=2.1, analyst_count=42
        )
        block = _format_market_intelligence(mi)
        assert "buy" in block
        assert "2.1" in block
        assert "42" in block

    def test_includes_price_targets(self) -> None:
        mi = MarketIntelligence(
            recommendation="buy",
            target_mean_price=225.0,
            target_median_price=220.0,
            target_high_price=260.0,
            target_low_price=180.0,
        )
        block = _format_market_intelligence(mi)
        assert "225.00" in block
        assert "260.00" in block
        assert "180.00" in block

    def test_includes_short_interest(self) -> None:
        mi = MarketIntelligence(
            shares_short=95_000_000,
            short_ratio=2.4,
            short_percent_of_float=0.0063,
        )
        block = _format_market_intelligence(mi)
        assert "95,000,000" in block
        assert "2.4" in block
        assert "0.63%" in block

    def test_includes_52_week_range(self) -> None:
        mi = MarketIntelligence(fifty_two_week_high=237.23, fifty_two_week_low=164.08)
        block = _format_market_intelligence(mi)
        assert "237.23" in block
        assert "164.08" in block

    def test_returns_empty_string_for_all_none_fields(self) -> None:
        assert _format_market_intelligence(MarketIntelligence()) == ""


class TestClassifyTemplate:
    def _profile(
        self, sector: str | None, industry: str | None, security_type: str | None = None
    ) -> CompanyIdentity:
        return CompanyIdentity(
            name="Test Co",
            sector=sector,
            industry=industry,
            security_type=security_type,
        )

    def test_etf_security_type_returns_etf(self) -> None:
        profile = self._profile("Financials", None, security_type="etf")
        assert _classify_template(profile, None) == "etf"

    def test_mutualfund_security_type_returns_etf(self) -> None:
        profile = self._profile(None, None, security_type="mutualfund")
        assert _classify_template(profile, None) == "etf"

    def test_mining_sector_with_revenue_returns_mining(self) -> None:
        profile = self._profile("Basic Materials", "Gold Mining")
        financials = Financials(
            currency="USD",
            income=[IncomeStatement(period="FY2024", revenue=50_000_000)],
        )
        assert _classify_template(profile, financials) == "mining"

    def test_mining_sector_without_revenue_returns_pre_revenue_mining(self) -> None:
        profile = self._profile("Basic Materials", "Gold Mining")
        financials = Financials(
            currency="USD", income=[IncomeStatement(period="FY2024", revenue=0)]
        )
        assert _classify_template(profile, financials) == "pre_revenue_mining"

    def test_biotech_industry_with_revenue_returns_biotech(self) -> None:
        profile = self._profile("Healthcare", "Biotechnology")
        financials = Financials(
            currency="USD",
            income=[IncomeStatement(period="FY2024", revenue=100_000_000)],
        )
        assert _classify_template(profile, financials) == "biotech"

    def test_energy_sector_with_revenue_returns_energy(self) -> None:
        profile = self._profile("Energy", "Oil & Gas")
        financials = Financials(
            currency="USD",
            income=[IncomeStatement(period="FY2024", revenue=500_000_000)],
        )
        assert _classify_template(profile, financials) == "energy"

    def test_tech_sector_with_revenue_returns_tech(self) -> None:
        profile = self._profile("Technology", "Software")
        financials = Financials(
            currency="USD",
            income=[IncomeStatement(period="FY2024", revenue=1_000_000_000)],
        )
        assert _classify_template(profile, financials) == "tech"

    def test_no_sector_with_revenue_returns_general(self) -> None:
        profile = self._profile(None, None)
        financials = Financials(
            currency="USD",
            income=[IncomeStatement(period="FY2024", revenue=200_000_000)],
        )
        assert _classify_template(profile, financials) == "general"

    def test_no_sector_without_revenue_returns_pre_revenue(self) -> None:
        assert _classify_template(None, None) == "pre_revenue"

    def test_no_financials_returns_pre_revenue(self) -> None:
        profile = self._profile("Technology", "Software")
        assert _classify_template(profile, None) == "pre_revenue"


class TestBuildContextClassification:
    """build_context() classifies internally when template_key is not provided."""

    async def test_classifies_template_from_db_profile(self) -> None:
        from unittest.mock import AsyncMock, MagicMock, patch

        from db.pg_models import NormalizedFinancials, NormalizedProfile, Security
        from services.analysis.context_builder import build_context

        mock_session = MagicMock()

        mock_security = MagicMock(spec=Security)
        mock_security.name = "Test Corp"
        mock_security.exchange = "NYSE"
        mock_security.currency = "USD"

        mock_profile = MagicMock(spec=NormalizedProfile)
        mock_profile.sector = "Technology"
        mock_profile.industry = "Software"
        mock_profile.asset_type = None
        mock_profile.logo_url = None
        mock_profile.description = None

        mock_fin_row = MagicMock(spec=NormalizedFinancials)
        mock_fin_row.period = "FY2024"
        mock_fin_row.fiscal_year = 2024
        mock_fin_row.revenue = 1_000_000_000.0
        mock_fin_row.gross_profit = 400_000_000.0
        mock_fin_row.operating_income = 200_000_000.0
        mock_fin_row.ebitda = None
        mock_fin_row.net_income = 150_000_000.0
        mock_fin_row.cash = None
        mock_fin_row.total_debt = None
        mock_fin_row.net_debt = None
        mock_fin_row.total_equity = None
        mock_fin_row.total_assets = None
        mock_fin_row.operating_cash_flow = None
        mock_fin_row.capex = None
        mock_fin_row.free_cash_flow = None
        mock_fin_row.market_cap = None
        mock_fin_row.enterprise_value = None
        mock_fin_row.pe_ratio = None
        mock_fin_row.forward_pe = None
        mock_fin_row.ev_ebitda = None
        mock_fin_row.enterprise_to_revenue = None
        mock_fin_row.price_to_book = None
        mock_fin_row.peg_ratio = None
        mock_fin_row.roe = None
        mock_fin_row.return_on_assets = None
        mock_fin_row.eps = None
        mock_fin_row.forward_eps = None
        mock_fin_row.revenue_growth = None
        mock_fin_row.earnings_growth = None
        mock_fin_row.dividend_yield = None
        mock_fin_row.dividend_rate = None
        mock_fin_row.payout_ratio = None
        mock_fin_row.beta = None
        mock_fin_row.debt_to_equity = None
        mock_fin_row.quick_ratio = None
        mock_fin_row.current_ratio = None
        mock_fin_row.currency = "USD"
        mock_fin_row.security_id = "abc-123"
        mock_fin_row.updated_at = datetime.now(timezone.utc)

        with (
            patch(
                "services.analysis.context_builder.resolve_identity",
                new=AsyncMock(return_value=MagicMock(security_id="abc-123")),
            ),
            patch(
                "services.analysis.context_builder._load_financials_from_db",
                new=AsyncMock(
                    return_value=Financials(
                        security_id="abc-123",
                        currency="USD",
                        income=[
                            IncomeStatement(
                                period="FY2024",
                                fiscal_year=2024,
                                revenue=1_000_000_000.0,
                            )
                        ],
                    )
                ),
            ),
            patch(
                "services.analysis.context_builder._load_quote_from_db",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.analysis.context_builder._load_leadership_from_db",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.analysis.context_builder._load_market_intelligence_from_db",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                mock_session,
                "execute",
                new=AsyncMock(
                    side_effect=[
                        MagicMock(
                            scalar_one_or_none=MagicMock(return_value=mock_security)
                        ),
                        MagicMock(
                            scalar_one_or_none=MagicMock(return_value=mock_profile)
                        ),
                    ]
                ),
            ),
        ):
            result = await build_context("TEST", mock_session)

        assert result.template_key == "tech"

    async def test_respects_explicit_template_key_override(self) -> None:
        from unittest.mock import AsyncMock, MagicMock, patch

        from services.analysis.context_builder import build_context

        mock_session = MagicMock()

        with (
            patch(
                "services.analysis.context_builder.resolve_identity",
                new=AsyncMock(return_value=MagicMock(security_id=None)),
            ),
            patch(
                "services.analysis.context_builder._load_financials_from_db",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.analysis.context_builder._load_quote_from_db",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.analysis.context_builder._load_leadership_from_db",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.analysis.context_builder._load_market_intelligence_from_db",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await build_context("TEST", mock_session, template_key="mining")

        assert result.template_key == "mining"
