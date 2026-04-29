"""Filesystem paths used across the application.

All writable data lives under ``%LOCALAPPDATA%/GameBoostApexOptimizer`` on Windows
(or ``~/.gameboostapex-optimizer`` elsewhere, for development on other OSes).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _data_root() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "GameBoostApexOptimizer"
    return Path.home() / ".gameboostapex-optimizer"


APP_DATA_DIR: Path = _data_root()
LOG_DIR: Path = APP_DATA_DIR / "logs"
BACKUP_DIR: Path = APP_DATA_DIR / "backups"
HISTORY_DIR: Path = APP_DATA_DIR / "history"
CONFIG_FILE: Path = APP_DATA_DIR / "config.json"
PROFILES_DIR: Path = APP_DATA_DIR / "profiles"
# v2.1 — daily reports, achievements, benchmarks, macros, plugins
REPORTS_DIR: Path = APP_DATA_DIR / "reports"
STATS_DIR: Path = APP_DATA_DIR / "stats"
BENCHMARKS_DIR: Path = APP_DATA_DIR / "benchmarks"
MACROS_DIR: Path = APP_DATA_DIR / "macros"
PLUGINS_DIR: Path = APP_DATA_DIR / "plugins"


def ensure_app_dirs() -> None:
    """Create every writable directory the app expects. Idempotent."""
    for d in (
        APP_DATA_DIR, LOG_DIR, BACKUP_DIR, HISTORY_DIR, PROFILES_DIR,
        REPORTS_DIR, STATS_DIR, BENCHMARKS_DIR, MACROS_DIR, PLUGINS_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)


def project_root() -> Path:
    """Root of the source tree (one level above the ``app`` package)."""
    return Path(__file__).resolve().parents[2]
