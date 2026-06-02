from __future__ import annotations

import anthropic
import groq as groq_lib

from core.config import settings

CLASSIFY_MODEL_GROQ = "llama-3.1-8b-instant"
REPORT_MODEL = "claude-sonnet-4-6"

_anthropic_client: anthropic.AsyncAnthropic | None = None
_groq_client: groq_lib.AsyncGroq | None = None


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        key = settings.anthropic_api_key
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _anthropic_client = anthropic.AsyncAnthropic(api_key=key, timeout=300.0)
    return _anthropic_client


def get_groq_client() -> groq_lib.AsyncGroq:
    global _groq_client
    if _groq_client is None:
        key = settings.groq_api_key
        if not key:
            raise RuntimeError("GROQ_API_KEY is not set")
        _groq_client = groq_lib.AsyncGroq(api_key=key)
    return _groq_client
