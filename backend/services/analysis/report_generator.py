from __future__ import annotations

import logging
from datetime import datetime, timezone

from services.analysis.context_builder import StructuredContext
from services.llm import REPORT_MODEL, get_anthropic_client

logger = logging.getLogger(__name__)

_SYSTEM_PREAMBLE = """\
You are a financial analyst writing a structured investment research report for a personal investment platform.

You will be given structured financial data (pre-computed — use these exact figures) and an excerpt from the company's most recent annual filing. Your task is to populate the report template below.

Strict rules:
1. Use ONLY the financial figures provided in the structured data block — do not calculate, estimate, or invent any numbers not explicitly given.
2. Where data is not available for a specific field, write exactly: Data not available
3. Render the output as clean markdown: use ### for [H3] headings, - for [B] bullet points, and plain paragraphs for [P] markers.
4. Do not add an introduction, preamble, closing summary, or any text outside the template structure.
5. Do not repeat the template instructions — output only the populated report content.

Report template:
"""

_MERGER_NOTICE = (
    "\n\n---\n> **Note:** Filing content suggests this company may have been acquired, "
    "merged, or is no longer independent — verify current status before acting on this analysis."
)


async def generate(
    context: StructuredContext,
    prompt_template: str,
    report_template_key: str,
    independence: str,
) -> str:
    """Call Sonnet to generate the Bucket A+B report sections.

    The system prompt (preamble + template) is marked for Anthropic prompt caching.
    The user message contains per-company data and is never cached.
    Returns a markdown string.
    """
    system_text = _SYSTEM_PREAMBLE + prompt_template
    exchange_line = f" ({context.exchange})" if context.exchange else ""
    report_date = datetime.now(timezone.utc).strftime("%B %d, %Y")

    sections = [
        f"Company: {context.ticker} — {context.company_name}{exchange_line}",
        f"Report date: {report_date}",
        "",
        "=== STRUCTURED FINANCIAL DATA ===",
        context.metrics_block,
    ]
    if context.business_summary:
        sections += ["", "=== BUSINESS OVERVIEW ===", context.business_summary]
    if context.leadership_block:
        sections += ["", "=== LEADERSHIP & GOVERNANCE ===", context.leadership_block]
    if context.market_intelligence_block:
        sections += [
            "",
            "=== MARKET INTELLIGENCE ===",
            context.market_intelligence_block,
        ]
    sections += [
        "",
        "=== ANNUAL FILING EXCERPT ===",
        context.filing_excerpt or "No filing data available for this ticker.",
    ]
    user_content = "\n".join(sections)

    logger.info(
        "calling Sonnet (streaming)",
        extra={
            "ticker": context.ticker,
            "model": REPORT_MODEL,
            "template": report_template_key,
            "has_business_summary": bool(context.business_summary),
            "has_leadership": bool(context.leadership_block),
            "has_market_intel": bool(context.market_intelligence_block),
        },
    )
    client = get_anthropic_client()
    async with client.messages.stream(
        model=REPORT_MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    ) as stream:
        report_markdown = await stream.get_final_text()
        message = await stream.get_final_message()

    cache_read = getattr(message.usage, "cache_read_input_tokens", 0)
    logger.info(
        "Sonnet complete",
        extra={
            "ticker": context.ticker,
            "in": message.usage.input_tokens,
            "out": message.usage.output_tokens,
            "cache_hit": cache_read,
        },
    )

    if independence != "independent":
        report_markdown += _MERGER_NOTICE

    return report_markdown
