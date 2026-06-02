from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Standard LogRecord attributes — anything else is an "extra" field added by the caller.
_STANDARD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "process",
        "processName",
        "message",
        "request_id",
        "taskName",
    }
)

# ANSI colour codes
_RESET = "\033[0m"
_DIM = "\033[2m"
_CYAN = "\033[36m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_BOLD = "\033[1m"

_LEVEL_COLOUR = {
    "DEBUG": _DIM,
    "INFO": _CYAN,
    "WARNING": _YELLOW,
    "ERROR": _RED,
    "CRITICAL": _BOLD + _RED,
}


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        import json

        payload: dict = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _STANDARD_ATTRS and not k.startswith("_")
        }
        if extras:
            payload.update(extras)
        return json.dumps(payload)


class _PrettyFormatter(logging.Formatter):
    """Human-readable formatter for TTY output during development.

    Format:
        HH:MM:SS  LEVEL    logger_name      message              key=val  key=val
    """

    def format(self, record: logging.LogRecord) -> str:
        # Time
        t = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")

        # Level — padded to 7 chars, coloured
        level_str = record.levelname.ljust(7)
        colour = _LEVEL_COLOUR.get(record.levelname, "")
        level_coloured = f"{colour}{level_str}{_RESET}"

        # Logger name — last dotted component, capped at 14 chars
        short_name = record.name.rsplit(".", 1)[-1][:14].ljust(14)

        # Message
        message = record.getMessage()

        # Extra fields — key=value pairs in dim colour
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _STANDARD_ATTRS and not k.startswith("_")
        }
        extra_str = ""
        if extras:
            parts = [f"{k}={v}" for k, v in extras.items()]
            extra_str = f"  {_DIM}{' '.join(parts)}{_RESET}"

        line = f"{_DIM}{t}{_RESET}  {level_coloured}  {_DIM}{short_name}{_RESET}  {message}{extra_str}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)

        return line


def configure_logging(level: int = logging.INFO) -> None:
    """Call once at application startup to set up logging.

    Uses a human-readable pretty format when stdout is a TTY (local dev),
    and JSON structured logging otherwise (production / Vercel).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestIdFilter())

    if sys.stdout.isatty():
        handler.setFormatter(_PrettyFormatter())
    else:
        handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet noisy third-party loggers
    for name in ("uvicorn.access", "httpx", "httpcore", "yfinance", "peewee"):
        logging.getLogger(name).setLevel(logging.WARNING)
