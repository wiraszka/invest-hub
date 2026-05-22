from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SYMBOLS_PATH = Path(__file__).parents[1] / "data" / "symbols.json"

_cache: list[dict] = []
_ticker_set: set[str] = set()
_loaded = False

_EXCHANGE_SUFFIX: dict[str, str] = {
    "TSX": ".TO",
    "TSXV": ".V",
    "TSX-V": ".V",
    "TSX VENTURE": ".V",
}


def _load() -> None:
    global _cache, _ticker_set, _loaded
    if _loaded:
        return
    if not _SYMBOLS_PATH.exists():
        logger.warning(
            "Symbol list not found — run: python scripts/refresh_symbol_list.py",
            extra={"path": str(_SYMBOLS_PATH)},
        )
    else:
        _cache = json.loads(_SYMBOLS_PATH.read_text(encoding="utf-8"))
        logger.info("Symbol list loaded", extra={"count": len(_cache)})
    _ticker_set = {entry["ticker"].upper() for entry in _cache}
    _loaded = True


def resolve_canonical(symbol: str, exchange: str | None = None) -> str:
    """Return the canonical ticker with the correct exchange suffix.

    When exchange is provided (e.g. from a holdings CSV), map it directly.
    Otherwise probe the symbol list: .TO → .V → bare → default .TO.
    """
    sym = symbol.strip().upper()
    if exchange:
        suffix = _EXCHANGE_SUFFIX.get(exchange.strip().upper())
        return f"{sym}{suffix}" if suffix else sym
    _load()
    for suffix in (".TO", ".V"):
        if f"{sym}{suffix}" in _ticker_set:
            return f"{sym}{suffix}"
    if sym in _ticker_set:
        return sym
    return f"{sym}.TO"


def search_companies(query: str, limit: int = 10) -> list[dict]:
    """Search the symbol snapshot by ticker prefix or name substring.

    Returns up to `limit` results ranked ticker-first.
    Returns an empty list if the snapshot has not been generated yet.
    """
    if not query or len(query.strip()) < 1:
        return []

    _load()
    q = query.strip().upper()

    ticker_exact: list[dict] = []
    ticker_prefix: list[dict] = []
    name_matches: list[dict] = []

    for entry in _cache:
        ticker = entry.get("ticker", "").upper()
        name = entry.get("name", "").upper()

        if ticker == q:
            ticker_exact.append(entry)
        elif ticker.startswith(q):
            ticker_prefix.append(entry)
        elif q in name:
            name_matches.append(entry)

    return (ticker_exact + ticker_prefix + name_matches)[:limit]
