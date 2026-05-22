from __future__ import annotations

import hashlib
from pathlib import Path

_PROMPTS_ROOT = Path(__file__).parents[3] / "llm-prompts"

_TEMPLATE_PATHS: dict[str, str] = {
    "pre-revenue/general": "pre-revenue/general.md",
    "pre-revenue/mining": "pre-revenue/mining-pre-revenue.md",
    "revenue-generating/general": "revenue-generating/general.md",
    "revenue-generating/mining-producer": "revenue-generating/mining-producer.md",
    "revenue-generating/oil-gas": "revenue-generating/oil&gas.md",
}

_cache: dict[str, tuple[str, str]] = {}


def load(template_key: str) -> tuple[str, str]:
    """Return (prompt_text, sha256_hex) for the given template key.

    Results are cached in memory for the lifetime of the process.
    Raises KeyError if the template key is not recognised.
    Raises FileNotFoundError if the prompt file is missing.
    """
    if template_key in _cache:
        return _cache[template_key]

    relative = _TEMPLATE_PATHS.get(template_key)
    if relative is None:
        raise KeyError(f"Unknown report template: {template_key!r}")

    path = _PROMPTS_ROOT / relative
    text = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode()).hexdigest()
    _cache[template_key] = (text, digest)
    return text, digest


def valid_template_keys() -> frozenset[str]:
    return frozenset(_TEMPLATE_PATHS)
