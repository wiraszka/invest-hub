from __future__ import annotations

from unittest.mock import patch

from services.search import resolve_canonical


class TestResolveCanonicalWithExchange:
    def test_tsx_suffix(self) -> None:
        assert resolve_canonical("SU", "TSX") == "SU.TO"

    def test_tsxv_suffix(self) -> None:
        assert resolve_canonical("GGD", "TSXV") == "GGD.V"

    def test_tsxv_hyphen_variant(self) -> None:
        assert resolve_canonical("GGD", "TSX-V") == "GGD.V"

    def test_tsxv_venture_variant(self) -> None:
        assert resolve_canonical("GGD", "TSX VENTURE") == "GGD.V"

    def test_nyse_no_suffix(self) -> None:
        assert resolve_canonical("AAPL", "NYSE") == "AAPL"

    def test_nasdaq_no_suffix(self) -> None:
        assert resolve_canonical("MSFT", "NASDAQ") == "MSFT"

    def test_unknown_exchange_no_suffix(self) -> None:
        assert resolve_canonical("XYZ", "BATS") == "XYZ"

    def test_symbol_uppercased(self) -> None:
        assert resolve_canonical("su", "TSX") == "SU.TO"

    def test_exchange_case_insensitive(self) -> None:
        assert resolve_canonical("SU", "tsx") == "SU.TO"


class TestResolveCanonicalSymbolList:
    def test_tsx_found_in_symbol_list(self) -> None:
        with (
            patch("services.search._loaded", True),
            patch("services.search._ticker_set", {"SU.TO", "AAPL"}),
        ):
            assert resolve_canonical("SU") == "SU.TO"

    def test_tsxv_found_in_symbol_list(self) -> None:
        with (
            patch("services.search._loaded", True),
            patch("services.search._ticker_set", {"GGD.V", "AAPL"}),
        ):
            assert resolve_canonical("GGD") == "GGD.V"

    def test_us_only_no_suffix(self) -> None:
        with (
            patch("services.search._loaded", True),
            patch("services.search._ticker_set", {"AAPL"}),
        ):
            assert resolve_canonical("AAPL") == "AAPL"

    def test_to_checked_before_v(self) -> None:
        with (
            patch("services.search._loaded", True),
            patch("services.search._ticker_set", {"SU.TO", "SU.V"}),
        ):
            assert resolve_canonical("SU") == "SU.TO"

    def test_unknown_defaults_to_to(self) -> None:
        with (
            patch("services.search._loaded", True),
            patch("services.search._ticker_set", set()),
        ):
            assert resolve_canonical("XYZ") == "XYZ.TO"

    def test_exchange_hint_overrides_symbol_list(self) -> None:
        with (
            patch("services.search._loaded", True),
            patch("services.search._ticker_set", {"SU.TO"}),
        ):
            assert resolve_canonical("SU", "NYSE") == "SU"
