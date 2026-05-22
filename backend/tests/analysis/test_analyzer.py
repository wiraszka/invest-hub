from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from services.analysis.analyzer import (
    _detect_independence_regex,
    _extract_targeted_window,
    analyze,
)
from services.analysis.context_builder import StructuredContext


def _make_context(
    template_key: str = "general",
    metrics_block: str = "Revenue: $1.00B",
    filing_excerpt: str = "Annual report covering normal operations.",
    sector: str | None = "Technology",
    industry: str | None = "Software",
) -> StructuredContext:
    return StructuredContext(
        ticker="AAPL",
        company_name="Apple Inc.",
        exchange="NASDAQ",
        currency="USD",
        canonical_id="abc-123",
        template_key=template_key,
        sector=sector,
        industry=industry,
        metrics_block=metrics_block,
        filing_excerpt=filing_excerpt,
    )


def _mock_llm_response(content: str) -> MagicMock:
    message = MagicMock()
    message.content = [MagicMock(text=content)]
    return message


class TestDetectIndependenceRegex:
    def test_returns_none_for_normal_filing(self) -> None:
        assert _detect_independence_regex("Normal annual operations.") is None

    def test_detects_confirmed_inactive_on_acquired(self) -> None:
        result = _detect_independence_regex("The company was acquired by BigCorp in Q3.")
        assert result == "confirmed_inactive"

    def test_detects_confirmed_inactive_on_delisted(self) -> None:
        result = _detect_independence_regex("Shares were delisted from the exchange.")
        assert result == "confirmed_inactive"

    def test_detects_possibly_acquired_on_going_concern(self) -> None:
        result = _detect_independence_regex("The auditors raised going concern doubt.")
        assert result == "possibly_acquired"

    def test_detects_possibly_acquired_on_pending_acquisition(self) -> None:
        result = _detect_independence_regex("The pending acquisition by MegaCo is expected to close in Q2.")
        assert result == "possibly_acquired"

    def test_is_case_insensitive(self) -> None:
        assert _detect_independence_regex("ACQUIRED BY BIGCO") == "confirmed_inactive"
        assert _detect_independence_regex("GOING CONCERN") == "possibly_acquired"


class TestExtractTargetedWindow:
    def test_returns_window_around_keyword(self) -> None:
        text = "Some intro. " + "x" * 500 + " Segment revenue breakdown: Tech 100M, Services 50M." + " y" * 500
        result = _extract_targeted_window(text, "general")
        assert "Segment revenue breakdown" in result
        assert len(result) <= 1600

    def test_falls_back_to_head_when_no_keyword_matches(self) -> None:
        text = "No relevant keywords here. " + "a" * 2000
        result = _extract_targeted_window(text, "general", window=500)
        assert result == text[:500]

    def test_uses_template_specific_keywords(self) -> None:
        text = "Background text. " + "x" * 200 + " Proven mineral reserves: Gold 500koz." + " y" * 500
        result = _extract_targeted_window(text, "mining")
        assert "mineral reserves" in result


class TestAnalyze:
    async def test_returns_independence_and_chart_data(self) -> None:
        json_response = '{"independence": "independent", "chart_data": {"revenue_by_segment": null}}'

        with patch("services.analysis.analyzer.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=_mock_llm_response(json_response))
            mock_get_client.return_value = mock_client

            result = await analyze(_make_context(template_key="general"))

        assert result["independence"] == "independent"
        assert "chart_data" in result
        assert "report_template" not in result

    async def test_regex_skips_llm_when_no_chart_fields_and_inactive(self) -> None:
        filing = "The company has been acquired by BigCorp."
        context = _make_context(template_key="pre_revenue", filing_excerpt=filing)

        with patch("services.analysis.analyzer.get_client") as mock_get_client:
            result = await analyze(context)
            mock_get_client.assert_not_called()

        assert result["independence"] == "confirmed_inactive"
        assert result["chart_data"] == {}

    async def test_regex_skips_llm_for_etf_with_inactive_filing(self) -> None:
        filing = "This ETF was delisted last quarter."
        context = _make_context(template_key="etf", filing_excerpt=filing)

        with patch("services.analysis.analyzer.get_client") as mock_get_client:
            result = await analyze(context)
            mock_get_client.assert_not_called()

        assert result["independence"] == "confirmed_inactive"

    async def test_llm_called_for_mining_template_despite_inactive_regex(self) -> None:
        filing = "The company was acquired by BigCorp. Mineral reserves: Gold 500koz."
        context = _make_context(template_key="mining", filing_excerpt=filing)
        json_response = '{"independence": "confirmed_inactive", "chart_data": {"reserves_by_asset": {"Gold": 500000}}}'

        with patch("services.analysis.analyzer.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=_mock_llm_response(json_response))
            mock_get_client.return_value = mock_client

            result = await analyze(context)
            mock_client.messages.create.assert_called_once()

        assert result["independence"] == "confirmed_inactive"
        assert result["chart_data"].get("reserves_by_asset") is not None

    async def test_invalid_independence_from_llm_falls_back_to_independent(self) -> None:
        json_response = '{"independence": "completely_wrong", "chart_data": {}}'

        with patch("services.analysis.analyzer.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=_mock_llm_response(json_response))
            mock_get_client.return_value = mock_client

            result = await analyze(_make_context(template_key="general"))

        assert result["independence"] == "independent"

    async def test_falls_back_gracefully_on_malformed_json(self) -> None:
        with patch("services.analysis.analyzer.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=_mock_llm_response("not json at all"))
            mock_get_client.return_value = mock_client

            result = await analyze(_make_context(template_key="general"))

        assert result["independence"] == "independent"
        assert result["chart_data"] == {}

    async def test_falls_back_gracefully_on_llm_exception(self) -> None:
        with patch("services.analysis.analyzer.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(side_effect=RuntimeError("API error"))
            mock_get_client.return_value = mock_client

            result = await analyze(_make_context(template_key="general"))

        assert result["independence"] == "independent"
        assert result["chart_data"] == {}

    async def test_empty_filing_excerpt_proceeds_without_regex(self) -> None:
        context = _make_context(template_key="general", filing_excerpt="")
        json_response = '{"independence": "possibly_acquired", "chart_data": {}}'

        with patch("services.analysis.analyzer.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=_mock_llm_response(json_response))
            mock_get_client.return_value = mock_client

            result = await analyze(context)

        assert result["independence"] == "possibly_acquired"

    async def test_targeted_window_passed_to_llm_not_full_text(self) -> None:
        long_text = "Annual report. " + "x" * 3000 + " Segment revenue: North America 500M."
        context = _make_context(template_key="general", filing_excerpt=long_text)
        json_response = '{"independence": "independent", "chart_data": {"revenue_by_segment": null}}'

        with patch("services.analysis.analyzer.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=_mock_llm_response(json_response))
            mock_get_client.return_value = mock_client

            await analyze(context)
            call_kwargs = mock_client.messages.create.call_args.kwargs
            user_content = call_kwargs["messages"][0]["content"]

        assert len(user_content) < len(long_text)
