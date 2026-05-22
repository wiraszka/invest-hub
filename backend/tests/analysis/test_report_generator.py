from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from services.analysis.context_builder import StructuredContext
from services.analysis.report_generator import _MERGER_NOTICE, generate


def _make_context() -> StructuredContext:
    return StructuredContext(
        ticker="AAPL",
        company_name="Apple Inc.",
        exchange="NASDAQ",
        currency="USD",
        canonical_id="abc-123",
        template_key="general",
        sector="Technology",
        industry="Software",
        metrics_block="Revenue: $1.00B\nNet income: $150.0M",
        filing_excerpt="Apple designs consumer electronics.",
    )


def _make_stream_mock(text: str) -> MagicMock:
    """Build a mock that behaves like client.messages.stream() async context manager."""
    usage = MagicMock(input_tokens=1000, output_tokens=500, cache_read_input_tokens=800)
    final_message = MagicMock()
    final_message.usage = usage

    stream = MagicMock()
    stream.get_final_text = AsyncMock(return_value=text)
    stream.get_final_message = AsyncMock(return_value=final_message)

    @asynccontextmanager
    async def _stream_ctx(*args, **kwargs):
        yield stream

    return _stream_ctx


class TestGenerate:
    async def test_returns_report_markdown(self) -> None:
        expected_markdown = "### Company Snapshot\n- Apple makes iPhones."

        with patch("services.analysis.report_generator.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.stream = _make_stream_mock(expected_markdown)
            mock_get_client.return_value = mock_client

            result = await generate(
                context=_make_context(),
                prompt_template="[H3] COMPANY SNAPSHOT\n[B] Description here.",
                report_template_key="revenue-generating/general",
                independence="independent",
            )

        assert result == expected_markdown

    async def test_appends_merger_notice_when_not_independent(self) -> None:
        base_markdown = "### Company Snapshot\n- A company."

        with patch("services.analysis.report_generator.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.stream = _make_stream_mock(base_markdown)
            mock_get_client.return_value = mock_client

            result = await generate(
                context=_make_context(),
                prompt_template="template",
                report_template_key="revenue-generating/general",
                independence="possibly_acquired",
            )

        assert _MERGER_NOTICE in result

    async def test_no_merger_notice_for_independent(self) -> None:
        base_markdown = "### Company Snapshot\n- A company."

        with patch("services.analysis.report_generator.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.stream = _make_stream_mock(base_markdown)
            mock_get_client.return_value = mock_client

            result = await generate(
                context=_make_context(),
                prompt_template="template",
                report_template_key="revenue-generating/general",
                independence="independent",
            )

        assert _MERGER_NOTICE not in result

    async def test_system_prompt_includes_template(self) -> None:
        prompt_template = "UNIQUE_TEMPLATE_MARKER_FOR_TEST"
        captured: dict = {}

        @asynccontextmanager
        async def _capturing_stream(*args, **kwargs):
            captured["kwargs"] = kwargs
            usage = MagicMock(input_tokens=100, output_tokens=50, cache_read_input_tokens=0)
            final_message = MagicMock()
            final_message.usage = usage
            stream = MagicMock()
            stream.get_final_text = AsyncMock(return_value="report")
            stream.get_final_message = AsyncMock(return_value=final_message)
            yield stream

        with patch("services.analysis.report_generator.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.stream = _capturing_stream
            mock_get_client.return_value = mock_client

            await generate(
                context=_make_context(),
                prompt_template=prompt_template,
                report_template_key="revenue-generating/general",
                independence="independent",
            )

        system_blocks = captured["kwargs"]["system"]
        assert any(prompt_template in block["text"] for block in system_blocks)

    async def test_system_prompt_has_cache_control(self) -> None:
        captured: dict = {}

        @asynccontextmanager
        async def _capturing_stream(*args, **kwargs):
            captured["kwargs"] = kwargs
            usage = MagicMock(input_tokens=100, output_tokens=50, cache_read_input_tokens=0)
            final_message = MagicMock()
            final_message.usage = usage
            stream = MagicMock()
            stream.get_final_text = AsyncMock(return_value="report")
            stream.get_final_message = AsyncMock(return_value=final_message)
            yield stream

        with patch("services.analysis.report_generator.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.stream = _capturing_stream
            mock_get_client.return_value = mock_client

            await generate(
                context=_make_context(),
                prompt_template="template",
                report_template_key="revenue-generating/general",
                independence="independent",
            )

        system_blocks = captured["kwargs"]["system"]
        assert any(block.get("cache_control") == {"type": "ephemeral"} for block in system_blocks)

    async def test_user_message_contains_metrics_and_filing(self) -> None:
        context = _make_context()
        captured: dict = {}

        @asynccontextmanager
        async def _capturing_stream(*args, **kwargs):
            captured["kwargs"] = kwargs
            usage = MagicMock(input_tokens=100, output_tokens=50, cache_read_input_tokens=0)
            final_message = MagicMock()
            final_message.usage = usage
            stream = MagicMock()
            stream.get_final_text = AsyncMock(return_value="report")
            stream.get_final_message = AsyncMock(return_value=final_message)
            yield stream

        with patch("services.analysis.report_generator.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.stream = _capturing_stream
            mock_get_client.return_value = mock_client

            await generate(
                context=context,
                prompt_template="template",
                report_template_key="revenue-generating/general",
                independence="independent",
            )

        user_content = captured["kwargs"]["messages"][0]["content"]
        assert context.metrics_block in user_content
        assert context.filing_excerpt in user_content

    async def test_empty_filing_uses_fallback_message(self) -> None:
        context = _make_context()
        context.filing_excerpt = ""
        captured: dict = {}

        @asynccontextmanager
        async def _capturing_stream(*args, **kwargs):
            captured["kwargs"] = kwargs
            usage = MagicMock(input_tokens=100, output_tokens=50, cache_read_input_tokens=0)
            final_message = MagicMock()
            final_message.usage = usage
            stream = MagicMock()
            stream.get_final_text = AsyncMock(return_value="report")
            stream.get_final_message = AsyncMock(return_value=final_message)
            yield stream

        with patch("services.analysis.report_generator.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.stream = _capturing_stream
            mock_get_client.return_value = mock_client

            await generate(
                context=context,
                prompt_template="template",
                report_template_key="revenue-generating/general",
                independence="independent",
            )

        user_content = captured["kwargs"]["messages"][0]["content"]
        assert "No filing data available" in user_content
