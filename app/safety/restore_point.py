"""Windows System Restore point creation.

Uses PowerShell's ``Checkpoint-Computer`` which is exposed by the built-in
SystemRestore WMI class. Non-destructive — worst case the call silently
fails and we log it.

Note: On Windows 10+ System Restore is often disabled by default and
requires admin. We surface this status to the UI so users aren't surprised.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional

from ..utils.admin_check import is_admin
from ..utils.logger import get_logger
from ..utils.subprocess_helper import run as _run_silent

log = get_logger("safety.restore_point")


@dataclass
class RestorePointResult:
    created: bool
    reason: str = ""


class RestorePointService:
    """Thin wrapper around ``Checkpoint-Computer``."""

    def is_supported(self) -> bool:
        return sys.platform == "win32"

    def create(self, description: str = "GameBoost Optimizer") -> RestorePointResult:
        if not self.is_supported():
            return RestorePointResult(False, "System Restore is a Windows-only feature.")
        if not is_admin():
            return RestorePointResult(False, "Administrator rights are required for a restore point.")

        ps = (
            "$ErrorActionPreference='Stop';"
            f"Checkpoint-Computer -Description '{description}' -RestorePointType 'MODIFY_SETTINGS'"
        )
        rc, stdout, stderr = _run_silent(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
            timeout=90,
        )
        if rc == 0:
            log.info("Restore point created: %s", description)
            return RestorePointResult(True)
        msg = (stderr or stdout or "").strip()
        # Windows rate-limits restore points to one per 24h by default.
        if "within the frequency" in msg.lower() or "skipcreatefirstrunrp" in msg.lower():
            return RestorePointResult(False, "A restore point was created recently; Windows is rate-limiting.")
        log.warning("Restore point creation failed: %s", msg)
        return RestorePointResult(False, msg or "Unknown PowerShell error.")

    def last_restore_point(self) -> Optional[str]:
        """Return description of the most recent restore point, or None."""
        if not self.is_supported():
            return None
        rc, stdout, _ = _run_silent(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "Get-ComputerRestorePoint | Sort-Object -Property CreationTime -Descending | "
             "Select-Object -First 1 -ExpandProperty Description"],
            timeout=20,
        )
        if rc == 0:
            return (stdout or "").strip() or None
        return None
