"""Detect administrator / elevated privileges.

Many optimizations (service changes, power plan, restore points) require
elevation. The UI surfaces this state so the user never sees silent failures.
"""
from __future__ import annotations

import os
import sys


def is_admin() -> bool:
    """Return ``True`` when the process has admin / root privileges."""
    if sys.platform == "win32":
        try:
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    try:
        return os.geteuid() == 0  # type: ignore[attr-defined]
    except AttributeError:
        return False
