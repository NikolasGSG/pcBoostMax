"""Common building blocks for hardware inspectors."""
from __future__ import annotations

import enum
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class FindingSeverity(enum.Enum):
    INFO = "info"
    SUGGESTION = "suggestion"     # nice-to-have
    WARNING = "warning"           # something to address soon
    CRITICAL = "critical"         # imminent problem


@dataclass
class Finding:
    """A single observation surfaced from an inspector.

    The fields map cleanly onto a Live Insights card.
    """
    id: str                                 # short stable id, e.g. "ram.xmp_off"
    severity: FindingSeverity
    title: str                              # human-readable, e.g. "RAM running below rated speed"
    detail: str = ""                        # one-paragraph explanation
    fix_hint: str = ""                      # what the user can do
    sponsored_link_id: Optional[str] = None # affiliate.AffiliateRegistry id
    evidence: Dict[str, Any] = field(default_factory=dict)


class Inspector(ABC):
    """Inspector contract."""

    id: str = "base"

    @abstractmethod
    def inspect(self) -> List[Finding]:
        """Return findings for the current system. Must be read-only."""


# ---------------------------------------------------------------- helpers
def run_powershell(script: str, *, timeout: int = 8) -> Optional[str]:
    """Run a PowerShell snippet and return its stdout, or None on failure."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def run_command(args: list, *, timeout: int = 5) -> Optional[str]:
    """Run an arbitrary command (e.g. nvidia-smi) and return stdout."""
    try:
        out = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()
