from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.exceptions import ProviderUnavailableError
from models.market_data import AnalysisData, AnalysisReport, AnalysisResult
from services.analysis.context_builder import StructuredContext
from services.analysis.pipeline import (
    get_cached_analyze,
    get_cached_report,
    run_analyze,
    run_data,
    run_format,
    run_providers,
    run_report,
)


def _make_context(template_key: str = "general") -> StructuredContext:
    return StructuredContext(
        ticker="AAPL",
        company_name="Apple Inc.",
        exchange="NASDAQ",
        currency="USD",
        security_id="abc-123",
        template_key=template_key,
        sector="Technology",
        industry="Software",
        metrics_block="Revenue: $1.00B",
        filing_excerpt="Annual report text.",
    )


def _make_data(generated_at: datetime | None = None) -> AnalysisData:
    return AnalysisData(
        ticker="AAPL",
        company_name="Apple Inc.",
        exchange="NASDAQ",
        currency="USD",
        sector="Technology",
        industry="Software",
        template_key="",
        generated_at=generated_at or datetime.now(timezone.utc),
    )


def _make_analyze_result(analyzed_at: datetime | None = None) -> AnalysisResult:
    return AnalysisResult(
        ticker="AAPL",
        independence="independent",
        chart_data={"revenue_by_segment": None},
        analyzed_at=analyzed_at or datetime.now(timezone.utc),
    )


def _make_report(generated_at: datetime | None = None) -> AnalysisReport:
    return AnalysisReport(
        ticker="AAPL",
        report_template="general",
        independence="independent",
        report_markdown="### Company Snapshot\n- Apple makes iPhones.",
        generated_at=generated_at or datetime.now(timezone.utc),
    )


class TestRunProviders:
    async def test_returns_analysis_data_with_empty_template_key(self) -> None:
        mock_session = MagicMock()
        context = _make_context(template_key="")

        with patch(
            "services.analysis.pipeline.context_builder.fetch_providers",
            new=AsyncMock(return_value=context),
        ):
            result = await run_providers("AAPL", mock_session)

        assert result.ticker == "AAPL"
        assert result.template_key == ""

    async def test_no_analyzer_call_during_run_providers(self) -> None:
        mock_session = MagicMock()
        context = _make_context(template_key="")

        with (
            patch(
                "services.analysis.pipeline.context_builder.fetch_providers",
                new=AsyncMock(return_value=context),
            ),
            patch(
                "services.analysis.pipeline.analyzer.analyze", new=AsyncMock()
            ) as mock_analyze,
        ):
            await run_providers("AAPL", mock_session)

        mock_analyze.assert_not_called()

    async def test_propagates_provider_unavailable_error(self) -> None:
        mock_session = MagicMock()

        with patch(
            "services.analysis.pipeline.context_builder.fetch_providers",
            new=AsyncMock(side_effect=ProviderUnavailableError("AAPL", [])),
        ):
            with pytest.raises(ProviderUnavailableError):
                await run_providers("AAPL", mock_session)


class TestRunData:
    """Backward-compat shim — delegates to run_providers."""

    async def test_run_data_delegates_to_run_providers(self) -> None:
        mock_session = MagicMock()
        context = _make_context(template_key="")

        with patch(
            "services.analysis.pipeline.context_builder.fetch_providers",
            new=AsyncMock(return_value=context),
        ):
            result = await run_data("AAPL", mock_session, force=False)

        assert result.ticker == "AAPL"


class TestRunFormat:
    async def test_returns_structured_context(self) -> None:
        mock_session = MagicMock()
        context = _make_context(template_key="tech")

        with (
            patch(
                "services.analysis.pipeline.run_providers",
                new=AsyncMock(return_value=_make_data()),
            ),
            patch(
                "services.analysis.pipeline.filing_service.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.analysis.pipeline.context_builder.build_context",
                new=AsyncMock(return_value=context),
            ),
        ):
            result = await run_format("AAPL", mock_session)

        assert isinstance(result, StructuredContext)
        assert result.template_key == "tech"
        assert result.metrics_block == "Revenue: $1.00B"

    async def test_always_calls_run_providers(self) -> None:
        mock_session = MagicMock()
        context = _make_context()

        with (
            patch(
                "services.analysis.pipeline.run_providers",
                new=AsyncMock(return_value=_make_data()),
            ) as mock_providers,
            patch(
                "services.analysis.pipeline.filing_service.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.analysis.pipeline.context_builder.build_context",
                new=AsyncMock(return_value=context),
            ),
        ):
            await run_format("AAPL", mock_session)

        mock_providers.assert_awaited_once_with("AAPL", mock_session, force=False)

    async def test_passes_filing_to_build_context(self) -> None:
        mock_session = MagicMock()
        context = _make_context()
        mock_filing = MagicMock()

        with (
            patch(
                "services.analysis.pipeline.run_providers",
                new=AsyncMock(return_value=_make_data()),
            ),
            patch(
                "services.analysis.pipeline.filing_service.get_cached",
                new=AsyncMock(return_value=mock_filing),
            ),
            patch(
                "services.analysis.pipeline.context_builder.build_context",
                new=AsyncMock(return_value=context),
            ) as mock_build,
        ):
            await run_format("AAPL", mock_session)

        mock_build.assert_awaited_once_with("AAPL", mock_session, filing=mock_filing)

    async def test_force_passes_through_to_run_providers(self) -> None:
        mock_session = MagicMock()
        context = _make_context()

        with (
            patch(
                "services.analysis.pipeline.run_providers",
                new=AsyncMock(return_value=_make_data()),
            ) as mock_providers,
            patch(
                "services.analysis.pipeline.filing_service.get_cached",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.analysis.pipeline.context_builder.build_context",
                new=AsyncMock(return_value=context),
            ),
        ):
            await run_format("AAPL", mock_session, force=True)

        mock_providers.assert_awaited_once_with("AAPL", mock_session, force=True)


class TestRunAnalyze:
    async def test_returns_cached_result_when_fresh(self) -> None:
        mock_session = MagicMock()

        with patch(
            "services.analysis.pipeline._load_cached_analyze",
            new=AsyncMock(return_value=_make_analyze_result()),
        ) as mock_load:
            result = await run_analyze("AAPL", mock_session, force=False)

        assert result.ticker == "AAPL"
        mock_load.assert_awaited_once()

    async def test_calls_run_format_then_analyzer(self) -> None:
        mock_session = MagicMock()
        context = _make_context()

        with (
            patch(
                "services.analysis.pipeline._load_cached_analyze",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.analysis.pipeline.run_format",
                new=AsyncMock(return_value=context),
            ) as mock_format,
            patch(
                "services.analysis.pipeline.analyzer.analyze",
                new=AsyncMock(
                    return_value={
                        "independence": "independent",
                        "chart_data": {},
                    }
                ),
            ) as mock_analyze,
            patch("services.analysis.pipeline._upsert_analyze", new=AsyncMock()),
        ):
            result = await run_analyze("AAPL", mock_session)

        mock_format.assert_awaited_once()
        mock_analyze.assert_awaited_once()
        assert result.independence == "independent"

    async def test_bypasses_cache_when_force_true(self) -> None:
        mock_session = MagicMock()
        context = _make_context()

        with (
            patch(
                "services.analysis.pipeline.run_format",
                new=AsyncMock(return_value=context),
            ),
            patch(
                "services.analysis.pipeline.analyzer.analyze",
                new=AsyncMock(
                    return_value={
                        "independence": "possibly_acquired",
                        "chart_data": {},
                    }
                ),
            ),
            patch("services.analysis.pipeline._upsert_analyze", new=AsyncMock()),
        ):
            result = await run_analyze("AAPL", mock_session, force=True)

        assert result.independence == "possibly_acquired"


class TestRunReport:
    async def test_returns_cached_report_when_fresh(self) -> None:
        mock_session = MagicMock()

        with patch(
            "services.analysis.pipeline._load_cached_report",
            new=AsyncMock(return_value=_make_report()),
        ) as mock_load:
            result = await run_report("AAPL", mock_session, force=False)

        assert result.ticker == "AAPL"
        mock_load.assert_awaited_once()

    async def test_calls_run_format_then_generates_report(self) -> None:
        mock_session = MagicMock()
        context = _make_context(template_key="general")

        with (
            patch(
                "services.analysis.pipeline._load_cached_report",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.analysis.pipeline.run_format",
                new=AsyncMock(return_value=context),
            ) as mock_format,
            patch(
                "services.analysis.pipeline._load_independence",
                new=AsyncMock(return_value="independent"),
            ),
            patch(
                "services.analysis.pipeline.prompt_loader.load",
                return_value=("template text", "abc123"),
            ),
            patch(
                "services.analysis.pipeline.report_generator.generate",
                new=AsyncMock(return_value="## Report"),
            ),
            patch("services.analysis.pipeline._upsert_report", new=AsyncMock()),
        ):
            result = await run_report("AAPL", mock_session)

        mock_format.assert_awaited_once()
        assert result.report_markdown == "## Report"
        assert result.report_template == "general"

    async def test_uses_independence_from_analyze_phase(self) -> None:
        mock_session = MagicMock()
        context = _make_context()

        with (
            patch(
                "services.analysis.pipeline._load_cached_report",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.analysis.pipeline.run_format",
                new=AsyncMock(return_value=context),
            ),
            patch(
                "services.analysis.pipeline._load_independence",
                new=AsyncMock(return_value="possibly_acquired"),
            ),
            patch(
                "services.analysis.pipeline.prompt_loader.load",
                return_value=("template text", "abc123"),
            ),
            patch(
                "services.analysis.pipeline.report_generator.generate",
                new=AsyncMock(return_value="## Report"),
            ),
            patch("services.analysis.pipeline._upsert_report", new=AsyncMock()),
        ):
            result = await run_report("AAPL", mock_session)

        assert result.independence == "possibly_acquired"

    async def test_bypasses_cache_when_force_true(self) -> None:
        mock_session = MagicMock()
        context = _make_context()

        with (
            patch(
                "services.analysis.pipeline.run_format",
                new=AsyncMock(return_value=context),
            ),
            patch(
                "services.analysis.pipeline._load_independence",
                new=AsyncMock(return_value="independent"),
            ),
            patch(
                "services.analysis.pipeline.prompt_loader.load",
                return_value=("template text", "abc123"),
            ),
            patch(
                "services.analysis.pipeline.report_generator.generate",
                new=AsyncMock(return_value="## Forced"),
            ),
            patch("services.analysis.pipeline._upsert_report", new=AsyncMock()),
        ):
            result = await run_report("AAPL", mock_session, force=True)

        assert result.report_markdown == "## Forced"


class TestGetCachedAnalyze:
    async def test_returns_result_regardless_of_age(self) -> None:
        mock_session = MagicMock()
        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        old_result = _make_analyze_result(analyzed_at=old_date)

        with patch(
            "services.analysis.pipeline._load_cached_analyze",
            new=AsyncMock(return_value=old_result),
        ):
            result = await get_cached_analyze("AAPL", mock_session)

        assert result is not None
        assert result.analyzed_at == old_date

    async def test_returns_none_when_no_result_exists(self) -> None:
        mock_session = MagicMock()

        with patch(
            "services.analysis.pipeline._load_cached_analyze",
            new=AsyncMock(return_value=None),
        ):
            result = await get_cached_analyze("UNKNOWN", mock_session)

        assert result is None


class TestGetCachedReport:
    async def test_returns_report_regardless_of_age(self) -> None:
        mock_session = MagicMock()
        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        old_report = _make_report(generated_at=old_date)

        with patch(
            "services.analysis.pipeline._load_cached_report",
            new=AsyncMock(return_value=old_report),
        ):
            result = await get_cached_report("AAPL", mock_session)

        assert result is not None
        assert result.generated_at == old_date

    async def test_returns_none_when_no_report_exists(self) -> None:
        mock_session = MagicMock()

        with patch(
            "services.analysis.pipeline._load_cached_report",
            new=AsyncMock(return_value=None),
        ):
            result = await get_cached_report("UNKNOWN", mock_session)

        assert result is None
