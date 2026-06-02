from __future__ import annotations

import hashlib
from pathlib import Path

_PROMPTS_ROOT = Path(__file__).parents[3] / "llm-prompts"

_TEMPLATE_PATHS: dict[str, str] = {
    # ── Stock: revenue-generating ────────────────────────────────────────────
    "general": "stock/revenue-generating/general.md",
    "mining": "stock/revenue-generating/mining.md",
    "energy": "stock/revenue-generating/oil-gas.md",
    "tech": "stock/revenue-generating/tech.md",
    "biotech": "stock/revenue-generating/biotech.md",
    "financial": "stock/revenue-generating/general.md",  # fallback — no financial template yet
    "reit": "stock/revenue-generating/reit.md",
    # ── Stock: pre-revenue ───────────────────────────────────────────────────
    "pre_revenue": "stock/pre-revenue/general.md",
    "pre_revenue_mining": "stock/pre-revenue/mining.md",
    "pre_revenue_biotech": "stock/pre-revenue/biotech.md",
    # ── ETF ──────────────────────────────────────────────────────────────────
    "etf": "etf/equity/broad.md",  # default ETF fallback
    "etf_equity_broad": "etf/equity/broad.md",
    "etf_equity_sector": "etf/equity/sector.md",
    "etf_fixed_income_government": "etf/fixed-income/government.md",
    "etf_fixed_income_credit": "etf/fixed-income/credit.md",
    "etf_commodity": "etf/commodity/general.md",
    # ── Legacy long-form keys (backward compatibility) ───────────────────────
    "pre-revenue/general": "stock/pre-revenue/general.md",
    "pre-revenue/mining": "stock/pre-revenue/mining.md",
    "revenue-generating/general": "stock/revenue-generating/general.md",
    "revenue-generating/mining-producer": "stock/revenue-generating/mining.md",
    "revenue-generating/oil-gas": "stock/revenue-generating/oil-gas.md",
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
