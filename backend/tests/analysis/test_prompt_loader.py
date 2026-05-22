from __future__ import annotations

import pytest

from services.analysis.prompt_loader import load, valid_template_keys

_ALL_KEYS = [
    "pre-revenue/general",
    "pre-revenue/mining",
    "revenue-generating/general",
    "revenue-generating/mining-producer",
    "revenue-generating/oil-gas",
]


class TestLoad:
    def test_all_template_keys_resolve(self) -> None:
        for key in _ALL_KEYS:
            text, digest = load(key)

            assert isinstance(text, str)
            assert len(text) > 100
            assert isinstance(digest, str)
            assert len(digest) == 64

    def test_sha256_is_stable_across_calls(self) -> None:
        _, first_digest = load("revenue-generating/general")
        _, second_digest = load("revenue-generating/general")

        assert first_digest == second_digest

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
