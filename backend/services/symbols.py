from __future__ import annotations

import re


def clean_symbol(raw: str) -> str:
    """Strip OCC option suffix. 'QQQ   260930P00460000' → 'QQQ'."""
    return re.sub(r"\s+\d{6}[PC]\d+$", "", raw.strip())


def is_option(raw: str) -> bool:
    return bool(re.search(r"\s+\d{6}[PC]\d+$", raw.strip()))


def option_details(raw: str) -> str:
    """Parse OCC symbol to human-readable string. 'QQQ   260930P00460000' → "Put $460 · Sep 30 '26"."""
    match = re.search(r"\s+(\d{2})(\d{2})(\d{2})([PC])(\d{8})$", raw.strip())
    if not match:
        return ""
    yy, mm, dd, pc, strike_raw = match.groups()
    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    month = months[int(mm) - 1]
    strike = int(strike_raw) / 1000
    opt_type = "Put" if pc == "P" else "Call"
    return f"{opt_type} ${strike:g} · {month} {int(dd)} '{yy}"


def parse_float(value: str) -> float | None:
    stripped = (value or "").strip()
    try:
        return float(stripped) if stripped else None
    except ValueError:
        return None
