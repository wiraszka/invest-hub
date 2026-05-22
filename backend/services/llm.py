from __future__ import annotations

import anthropic

from core.config import settings

CLASSIFY_MODEL = "claude-haiku-4-5-20251001"
REPORT_MODEL = "claude-sonnet-4-6"

_anthropic_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        key = settings.anthropic_api_key
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _anthropic_client = anthropic.AsyncAnthropic(api_key=key, timeout=300.0)
    return _anthropic_client
