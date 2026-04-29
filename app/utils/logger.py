"""Structured, rotating logging with a simple JSON-friendly formatter.

Logs land in ``%LOCALAPPDATA%/GameBoostApexOptimizer/logs/gameboostapex.log`` and
mirror to the console during development. The same logger is shared by
every module via :func:`get_logger`.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import datetime
from typing import Any

from .paths import LOG_DIR, ensure_app_dirs

_CONFIGURED = False


class _JsonFormatter(logging.Formatter):
    """One-line JSON log records — easy to tail, easy to export."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - std override
        payload: dict[str, Any] = {
            "ts": datetime.utcfromtimestamp(record.created).isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key.startswith("ctx_"):
                payload[key[4:]] = value
        return json.dumps(payload, ensure_ascii=False)


class _ConsoleFormatter(logging.Formatter):
    """Human-readable console output with lightweight ANSI hints."""

    _COLOURS = {
        "DEBUG": "\x1b[38;5;244m",
        "INFO": "\x1b[38;5;45m",
        "WARNING": "\x1b[38;5;214m",
        "ERROR": "\x1b[38;5;203m",
        "CRITICAL": "\x1b[1;38;5;196m",
    }
    _RESET = "\x1b[0m"

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        colour = self._COLOURS.get(record.levelname, "")
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        return f"{colour}{ts} {record.levelname:<7}{self._RESET} {record.name}: {record.getMessage()}"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the root logger exactly once."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    ensure_app_dirs()

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "gameboostapex.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(_JsonFormatter())
    file_handler.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_ConsoleFormatter())
    console.setLevel(level)
    root.addHandler(console)

    # Silence noisy third-parties.
    for noisy in ("PyQt6", "matplotlib", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Module-level logger helper — prefixes with ``gameboostapex.``."""
    if not name.startswith("gameboostapex"):
        name = f"gameboostapex.{name}"
    return logging.getLogger(name)
