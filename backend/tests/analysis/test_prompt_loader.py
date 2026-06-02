from __future__ import annotations

from pathlib import Path

import pytest

from services.analysis.prompt_loader import load, valid_template_keys

_ALL_KEYS = [
    # Stock — revenue-generating
    "general",
    "mining",
    "energy",
    "tech",
    "biotech",
    "financial",
    "reit",
    # Stock — pre-revenue
    "pre_revenue",
    "pre_revenue_mining",
    "pre_revenue_biotech",
    # ETF
    "etf",
    "etf_equity_broad",
    "etf_equity_sector",
    "etf_fixed_income_government",
    "etf_fixed_income_credit",
    "etf_commodity",
    # Legacy long-form keys
    "pre-revenue/general",
    "pre-revenue/mining",
    "revenue-generating/general",
    "revenue-generating/mining-producer",
    "revenue-generating/oil-gas",
]

_PROMPTS_AVAILABLE = (Path(__file__).parents[4] / "llm-prompts").exists()
_skip_without_prompts = pytest.mark.skipif(
    not _PROMPTS_AVAILABLE,
    reason="llm-prompts directory not present in this environment",
)


class TestLoad:
    @_skip_without_prompts
    def test_all_template_keys_resolve(self) -> None:
        for key in _ALL_KEYS:
            text, digest = load(key)

            assert isinstance(text, str)
            assert len(text) > 100
            assert isinstance(digest, str)
            assert len(digest) == 64

    @_skip_without_prompts
    def test_sha256_is_stable_across_calls(self) -> None:
        _, first_digest = load("revenue-generating/general")
        _, second_digest = load("revenue-generating/general")

        assert first_digest == second_digest

    @_skip_without_prompts
    def test_different_templates_have_different_digests(self) -> None:
        _, general_digest = load("revenue-generating/general")
        _, mining_digest = load("revenue-generating/mining-producer")

        assert general_digest != mining_digest

    def test_unknown_key_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="Unknown report template"):
            load("unknown/template")

    def test_valid_template_keys_returns_all_five(self) -> None:
        keys = valid_template_keys()

        assert keys == frozenset(_ALL_KEYS)
