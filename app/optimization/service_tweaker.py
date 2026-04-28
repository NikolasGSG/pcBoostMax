"""Curated Windows-services advisor.

A read + recommend service. We **don't** disable services automatically
without user consent — instead we surface a curated list with
recommendations based on what the typical gaming PC does and doesn't
need.

For each service we record:
    * **id** — the Windows service short name (sc.exe key)
    * **safety** — "safe" / "review" / "do_not_touch"
    * **default_recommendation** — what most users should do
    * **what / why** — plain-English copy

The service tweaker can apply changes and roll them back via the same
backup pipeline as the optimization rules. Each apply emits a single
``ActionRecord`` so the user can undo the whole batch.
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..safety.action_history import ActionHistory, ActionRecord
from ..utils.logger import get_logger

log = get_logger("opt.services")


# ---------------------------------------------------------------- catalogue
@dataclass(frozen=True)
class ServiceTip:
    name: str                        # sc service name (e.g. "DiagTrack")
    display: str                     # human-readable
    safety: str                      # "safe" | "review" | "do_not_touch"
    recommendation: str              # "disable" | "manual" | "leave"
    what: str
    why: str


CURATED_SERVICES: List[ServiceTip] = [
    ServiceTip(
        "DiagTrack", "Connected User Experiences and Telemetry",
        "safe", "disable",
        "Sends diagnostic + usage data to Microsoft.",
        "Pure background telemetry — disabling has no functional impact."
    ),
    ServiceTip(
        "WSearch", "Windows Search Indexer",
        "review", "manual",
        "Builds the file-index used by Start Menu search and Outlook.",
        "Heavy disk reader. Disable only if you don't use file search."
    ),
    ServiceTip(
        "SysMain", "SysMain (formerly SuperFetch)",
        "safe", "disable",
        "Pre-loads frequently-used apps into RAM.",
        "On NVMe + 16+ GB RAM the benefit is negligible; the eviction churn isn't."
    ),
    ServiceTip(
        "Spooler", "Print Spooler",
        "review", "manual",
        "Coordinates print jobs.",
        "Disable only if you have no printer attached or networked."
    ),
    ServiceTip(
        "Fax", "Fax",
        "safe", "disable",
        "Sends and receives faxes via a fax modem.",
        "Almost no modern PC needs this."
    ),
    ServiceTip(
        "RemoteRegistry", "Remote Registry",
        "safe", "disable",
        "Lets remote users edit your registry over the network.",
        "Big attack surface; almost nobody actually uses it."
    ),
    ServiceTip(
        "MapsBroker", "Downloaded Maps Manager",
        "safe", "disable",
        "Downloads + caches offline maps for the Maps app.",
        "If you don't use Windows Maps offline, it's pure overhead."
    ),
    ServiceTip(
        "RetailDemo", "Retail Demo Service",
        "safe", "disable",
        "Powers in-store demo mode.",
        "Not needed on any consumer machine."
    ),
    ServiceTip(
        "WMPNetworkSvc", "Windows Media Player Network Sharing",
        "safe", "disable",
        "Shares Windows Media Player libraries over UPnP.",
        "Legacy. Disable unless you stream from Windows Media Player."
    ),
    ServiceTip(
        "TabletInputService", "Touch Keyboard and Handwriting",
        "review", "manual",
        "Powers the touch keyboard + handwriting panel.",
        "Disable only on a non-touch desktop."
    ),
    ServiceTip(
        "XblGameSave", "Xbox Live Game Save",
        "review", "manual",
        "Cloud-saves for Xbox Game Pass / Microsoft Store games.",
        "Disable only if you don't play Microsoft Store / Game Pass titles."
    ),
    ServiceTip(
        "XboxNetApiSvc", "Xbox Live Networking",
        "review", "manual",
        "Multiplayer networking for Xbox Live.",
        "Disable only if you don't play Microsoft Store / Game Pass titles."
    ),
    ServiceTip(
        "DPS", "Diagnostic Policy Service",
        "do_not_touch", "leave",
        "Detects + diagnoses problems with Windows components.",
        "Disabling causes phantom error popups and breaks repair tools."
    ),
    ServiceTip(
        "WinDefend", "Microsoft Defender Antivirus Service",
        "do_not_touch", "leave",
        "Real-time antivirus protection.",
        "Never disable. We don't even offer the option."
    ),
]


@dataclass
class ServiceState:
    """Live state of one service."""
    name: str
    display: str
    start_type: str = ""        # "auto" | "demand" | "disabled" | "boot" | "system"
    state: str = ""             # "running" | "stopped" | …
    safety: str = "review"
    recommendation: str = "leave"
    what: str = ""
    why: str = ""


@dataclass
class ServiceChange:
    name: str
    previous_start_type: str
    new_start_type: str


@dataclass
class ServiceApplyReport:
    changed: List[ServiceChange] = field(default_factory=list)
    failed: List[Tuple[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------- service
class ServiceTweaker:
    """Reads + applies service changes safely.

    All operations route through ``sc.exe``; ``Set-Service`` would also
    work but `sc.exe` is the most consistent across SKUs.
    """

    def __init__(self, history: Optional[ActionHistory] = None) -> None:
        self._history = history

    # ------------------------------------------------------------------ read
    def list_states(self) -> List[ServiceState]:
        """Return live state for every curated service."""
        out: List[ServiceState] = []
        for tip in CURATED_SERVICES:
            cur = self._query(tip.name)
            out.append(ServiceState(
                name=tip.name,
                display=tip.display,
                start_type=cur.get("start_type", ""),
                state=cur.get("state", ""),
                safety=tip.safety,
                recommendation=tip.recommendation,
                what=tip.what,
                why=tip.why,
            ))
        return out

    def recommendations(self) -> List[ServiceState]:
        """Subset that we recommend changing (and isn't already changed)."""
        out: List[ServiceState] = []
        for s in self.list_states():
            if s.safety == "do_not_touch":
                continue
            wanted = self._wanted_start_type(s.recommendation)
            if wanted is None or s.start_type == wanted:
                continue
            out.append(s)
        return out

    # ------------------------------------------------------------------ apply / restore
    def apply_recommendations(
        self,
        *,
        only: Optional[List[str]] = None,
    ) -> Tuple[ServiceApplyReport, Dict[str, Any]]:
        """Apply recommendations. Returns a report + a backup payload
        suitable for :meth:`restore`.
        """
        report = ServiceApplyReport()
        backup: Dict[str, str] = {}
        targets = [s for s in self.recommendations() if (only is None or s.name in only)]
        for s in targets:
            wanted = self._wanted_start_type(s.recommendation)
            if wanted is None:
                continue
            backup[s.name] = s.start_type
            ok = self._set_start_type(s.name, wanted)
            if ok:
                report.changed.append(ServiceChange(
                    name=s.name,
                    previous_start_type=s.start_type,
                    new_start_type=wanted,
                ))
            else:
                report.failed.append((s.name, "sc config failed"))
        if report.changed and self._history is not None:
            try:
                self._history.add(ActionRecord.new(
                    category="services",
                    action="services.tweak",
                    summary=f"Adjusted {len(report.changed)} services",
                    risk="low",
                    reversible=True,
                    payload={"backup": backup, "changes": [c.__dict__ for c in report.changed]},
                ))
            except Exception:
                log.exception("failed to record service tweak in history")
        return report, {"backup": backup}

    def restore(self, payload: Dict[str, Any]) -> ServiceApplyReport:
        report = ServiceApplyReport()
        backup = payload.get("backup", {}) or {}
        for name, prev in backup.items():
            if not prev:
                continue
            ok = self._set_start_type(name, prev)
            if ok:
                report.changed.append(ServiceChange(name=name, previous_start_type="", new_start_type=prev))
            else:
                report.failed.append((name, "restore failed"))
        return report

    # ------------------------------------------------------------------ low-level
    @staticmethod
    def _wanted_start_type(rec: str) -> Optional[str]:
        return {"disable": "disabled", "manual": "demand", "leave": None}.get(rec)

    @staticmethod
    def _query(name: str) -> Dict[str, str]:
        if sys.platform != "win32":
            return {}
        try:
            cfg = subprocess.run(["sc", "qc", name], capture_output=True, text=True,
                                 timeout=5, check=False)
            qry = subprocess.run(["sc", "query", name], capture_output=True, text=True,
                                 timeout=5, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return {}
        out: Dict[str, str] = {}
        for line in cfg.stdout.splitlines():
            if "START_TYPE" in line:
                # e.g. "        START_TYPE         : 2   AUTO_START"
                parts = line.split(":", 1)[-1].strip().split()
                if len(parts) >= 2:
                    label = parts[1].lower()
                    out["start_type"] = {
                        "auto_start": "auto",
                        "demand_start": "demand",
                        "disabled": "disabled",
                        "boot_start": "boot",
                        "system_start": "system",
                    }.get(label, label)
                break
        for line in qry.stdout.splitlines():
            if "STATE" in line:
                parts = line.split(":", 1)[-1].strip().split()
                if len(parts) >= 2:
                    out["state"] = parts[1].lower()
                break
        return out

    @staticmethod
    def _set_start_type(name: str, start_type: str) -> bool:
        if sys.platform != "win32":
            return False
        try:
            res = subprocess.run(
                ["sc", "config", name, f"start={start_type}"],
                capture_output=True, text=True, timeout=8, check=False,
            )
            return res.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False
