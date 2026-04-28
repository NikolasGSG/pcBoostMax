"""Advanced performance rules — quick, high-impact tweaks beyond the baseline.

Each rule keeps the same read-evaluate-apply-restore contract so the engine
can verify and roll them back like everything else.

Rules in this bundle:

* ``Win32PrioritySeparationRule`` — give foreground apps more CPU quanta.
* ``MemoryCompressionOffRule``     — stop Windows compressing cold pages
                                     (frees cycles, costs a bit of RAM).
* ``NduServiceOffRule``            — disable Ndu.sys Network Data Usage
                                     monitor (known latency micro-stutter).
* ``MouseAccelerationOffRule``     — enable raw mouse input for gaming.
* ``ScheduledTasksBloatRule``      — disable a curated list of background
                                     scheduled tasks (OneDrive auto-update,
                                     Customer Experience, Compatibility
                                     Appraiser, Error Reporting).

All rules no-op on non-Windows and all changes are reversible.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List

from ...core.constants import (
    IMPACT_MINOR,
    IMPACT_MODERATE,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_SAFE,
)
from ...system.hardware_detector import HardwareSnapshot
from ...utils.logger import get_logger
from ...utils.subprocess_helper import run as _run_silent
from .base_rule import OptimizationRule, RuleEvaluation, RuleOutcome
from .max_performance_rules import (
    _reg_delete,
    _reg_dword,
    _reg_read,
    _reg_write,
)

log = get_logger("opt.advanced_perf")


# ==================================================================== rules ==

class Win32PrioritySeparationRule(OptimizationRule):
    """Set Win32PrioritySeparation=26 (hex 0x1A) — heavy foreground boost."""

    id = "cpu.priority_separation_games"
    title = "Boost foreground app CPU quanta (Win32PrioritySeparation)"
    category = "cpu"
    what = (
        "Writes Win32PrioritySeparation=26 under HKLM\\SYSTEM\\...\\PriorityControl. "
        "Gives the foreground window long, fixed quantums with a 3× boost — "
        "Microsoft's own 'favour foreground applications' dial, cranked up."
    )
    why = (
        "The default value (2) uses short, variable quantums that favour even "
        "load balancing. 26 strongly biases the scheduler toward whatever has "
        "keyboard focus — usually your game."
    )
    risk = RISK_LOW
    impact = IMPACT_MODERATE
    reversible = True
    requires_admin = True

    _PATH = r"HKLM\SYSTEM\CurrentControlSet\Control\PriorityControl"
    _NAME = "Win32PrioritySeparation"
    _TARGET = 26  # 0x1A: long, fixed, foreground 3x
    _DEFAULT = 2  # Windows default

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        current = _reg_dword(self._PATH, self._NAME)
        if current == self._TARGET:
            return RuleEvaluation(False, "Foreground boost already at max.")
        return RuleEvaluation(
            True,
            "Foreground window will get long CPU quanta with 3× boost.",
            score=35,
            evidence={"current": current},
        )

    def apply(self) -> RuleOutcome:
        prev = _reg_dword(self._PATH, self._NAME)
        if not _reg_write(self._PATH, self._NAME, str(self._TARGET)):
            return RuleOutcome(False, "Could not write Win32PrioritySeparation (need admin).")
        return RuleOutcome(True, "Foreground boost raised to 26 (long + fixed + 3×).",
                           backup_payload={"prev": prev if prev is not None else self._DEFAULT})

    def restore(self, payload: Dict[str, Any]) -> None:
        prev = int(payload.get("prev", self._DEFAULT))
        _reg_write(self._PATH, self._NAME, str(prev))


class MemoryCompressionOffRule(OptimizationRule):
    """Disable Windows Memory Compression via MMAgent."""

    id = "memory.compression_off"
    title = "Disable Memory Compression"
    category = "memory"
    what = (
        "Calls Disable-MMAgent -MemoryCompression. Stops Windows from "
        "compressing cold pages in RAM to save space."
    )
    why = (
        "Memory compression costs a small slice of every CPU core whenever "
        "pages are squeezed or unsqueezed. On 16 GB+ machines the RAM saving "
        "isn't worth the background CPU cost during gameplay."
    )
    risk = RISK_MEDIUM
    impact = IMPACT_MINOR
    reversible = True
    requires_admin = True

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        # Don't recommend this on sub-12 GB machines.
        ram_gb = int(getattr(hardware, "ram_total_bytes", 0) / (1024 ** 3))
        if ram_gb and ram_gb < 12:
            return RuleEvaluation(False, f"Only {ram_gb} GB RAM — keep compression on.")
        enabled = self._mmagent_compression_enabled()
        if enabled is False:
            return RuleEvaluation(False, "Memory compression already disabled.")
        return RuleEvaluation(True, "Free cold-page CPU cost during gameplay.", score=20,
                              evidence={"enabled": enabled})

    def apply(self) -> RuleOutcome:
        prev = self._mmagent_compression_enabled()
        rc, _, err = _run_silent(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "Disable-MMAgent -MemoryCompression"],
            timeout=15,
        )
        if rc != 0:
            return RuleOutcome(False, f"Disable-MMAgent failed: {err.strip() or 'unknown'}")
        return RuleOutcome(True, "Memory Compression disabled — effective after reboot.",
                           backup_payload={"prev_enabled": prev})

    def restore(self, payload: Dict[str, Any]) -> None:
        # Only re-enable if it was on before.
        if payload.get("prev_enabled"):
            _run_silent(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 "Enable-MMAgent -MemoryCompression"],
                timeout=15,
            )

    @staticmethod
    def _mmagent_compression_enabled():
        rc, out, _ = _run_silent(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-MMAgent).MemoryCompression"],
            timeout=15,
        )
        if rc != 0:
            return None
        text = (out or "").strip().lower()
        if text in ("true", "1"):
            return True
        if text in ("false", "0"):
            return False
        return None


class NduServiceOffRule(OptimizationRule):
    """Disable Ndu.sys (Windows Network Data Usage monitor)."""

    id = "network.ndu_off"
    title = "Disable Ndu.sys (Network Data Usage monitor)"
    category = "network"
    what = (
        "Sets HKLM\\SYSTEM\\CurrentControlSet\\Services\\Ndu\\Start to 4 "
        "(disabled). Ndu.sys watches every network connection's byte counts "
        "for Task Manager's 'Network usage' column."
    )
    why = (
        "Ndu has long had micro-stutter reports on busy connections. Disabling "
        "it simply loses Task Manager's per-app network bytes column — every "
        "other network monitoring pathway is untouched."
    )
    risk = RISK_LOW
    impact = IMPACT_MINOR
    reversible = True
    requires_admin = True

    _PATH = r"HKLM\SYSTEM\CurrentControlSet\Services\Ndu"
    _NAME = "Start"
    _TARGET = 4  # disabled
    _DEFAULT = 2  # automatic

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        current = _reg_dword(self._PATH, self._NAME)
        if current == self._TARGET:
            return RuleEvaluation(False, "Ndu.sys already disabled.")
        return RuleEvaluation(True, "Disable the Network Data Usage monitor.", score=20,
                              evidence={"current": current})

    def apply(self) -> RuleOutcome:
        prev = _reg_dword(self._PATH, self._NAME)
        if not _reg_write(self._PATH, self._NAME, str(self._TARGET)):
            return RuleOutcome(False, "Could not write Ndu/Start (need admin).")
        return RuleOutcome(True, "Ndu.sys disabled — effective after reboot.",
                           backup_payload={"prev": prev if prev is not None else self._DEFAULT})

    def restore(self, payload: Dict[str, Any]) -> None:
        prev = int(payload.get("prev", self._DEFAULT))
        _reg_write(self._PATH, self._NAME, str(prev))


class MouseAccelerationOffRule(OptimizationRule):
    """Turn off 'Enhance pointer precision' (mouse acceleration)."""

    id = "input.mouse_accel_off"
    title = "Disable mouse acceleration (raw input)"
    category = "input"
    what = (
        "Writes HKCU\\Control Panel\\Mouse: MouseSpeed=0, "
        "MouseThreshold1=0, MouseThreshold2=0. Disables Windows' pointer "
        "acceleration so mouse movement becomes 1:1 raw input."
    )
    why = (
        "Acceleration makes identical mouse movements produce different "
        "on-screen distances depending on velocity. Competitive shooters, "
        "MOBAs and RTS titles rely on muscle memory — raw input is the norm."
    )
    risk = RISK_SAFE
    impact = IMPACT_MODERATE
    reversible = True
    requires_admin = False

    _PATH = r"HKCU\Control Panel\Mouse"
    _TARGETS: list[tuple[str, str]] = [
        ("MouseSpeed", "0"),
        ("MouseThreshold1", "0"),
        ("MouseThreshold2", "0"),
    ]

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        # These values are REG_SZ (strings) on Windows despite containing numbers.
        for name, expected in self._TARGETS:
            val, _ = _reg_read(self._PATH, name)
            if (val or "").strip() != expected:
                return RuleEvaluation(True, "Mouse acceleration is active.", score=30,
                                      evidence={name: val})
        return RuleEvaluation(False, "Mouse acceleration already disabled.")

    def apply(self) -> RuleOutcome:
        previous: Dict[str, str] = {}
        for name, value in self._TARGETS:
            prev, _ = _reg_read(self._PATH, name)
            previous[name] = (prev or "").strip()
            _reg_write(self._PATH, name, value, "REG_SZ")
        return RuleOutcome(True, "Mouse acceleration disabled — log out/in to apply system-wide.",
                           backup_payload={"previous": previous})

    def restore(self, payload: Dict[str, Any]) -> None:
        for name, prev in (payload.get("previous") or {}).items():
            if prev:
                _reg_write(self._PATH, name, prev, "REG_SZ")
            else:
                _reg_delete(self._PATH, name)


# ----------------------------------------------------------------- scheduled tasks

# Curated list of tasks that Microsoft itself documents as opt-outable. Each
# tuple is (path, short_reason) where path is the full schtasks /TN path.
_BLOAT_TASKS: list[tuple[str, str]] = [
    (r"\Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser",
     "Telemetry: compatibility data for Windows Update"),
    (r"\Microsoft\Windows\Application Experience\ProgramDataUpdater",
     "Telemetry: usage data for installed software"),
    (r"\Microsoft\Windows\Application Experience\StartupAppTask",
     "Telemetry: startup app timing"),
    (r"\Microsoft\Windows\Customer Experience Improvement Program\Consolidator",
     "Telemetry: consolidates CEIP data"),
    (r"\Microsoft\Windows\Customer Experience Improvement Program\UsbCeip",
     "Telemetry: USB device data"),
    (r"\Microsoft\Windows\Feedback\Siuf\DmClient",
     "Telemetry: feedback hub sync"),
    (r"\Microsoft\Windows\Feedback\Siuf\DmClientOnScenarioDownload",
     "Telemetry: feedback scenario download"),
    (r"\Microsoft\Windows\Windows Error Reporting\QueueReporting",
     "Telemetry: error report queue flush"),
    (r"\Microsoft\Windows\Autochk\Proxy",
     "Disk check agent telemetry"),
    (r"\Microsoft\Windows\DiskDiagnostic\Microsoft-Windows-DiskDiagnosticDataCollector",
     "Disk diagnostic telemetry"),
]


class ScheduledTasksBloatRule(OptimizationRule):
    """Disable a curated list of background telemetry / bloat tasks."""

    id = "tasks.disable_bloat"
    title = "Disable known bloat scheduled tasks"
    category = "services"
    what = (
        "Runs `schtasks /Change /TN <path> /Disable` for a curated list of "
        "telemetry / feedback / compatibility-appraiser tasks that run "
        "opportunistically in the background."
    )
    why = (
        "These tasks fire unpredictably and trigger small bursts of CPU + "
        "disk I/O. Nothing that matters to normal use depends on them — "
        "disabling just loses Microsoft telemetry and feedback auto-upload."
    )
    risk = RISK_LOW
    impact = IMPACT_MINOR
    reversible = True
    requires_admin = True

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        ready, status = self._collect_status()
        if not ready:
            return RuleEvaluation(False, "Could not enumerate scheduled tasks.")
        # Rule is applicable if at least one listed task is currently enabled.
        enabled = [p for p, state in status.items() if state == "Ready"]
        if not enabled:
            return RuleEvaluation(False, "All known bloat tasks already disabled.")
        return RuleEvaluation(
            True,
            f"{len(enabled)} known bloat task(s) are still enabled.",
            score=25,
            evidence={"enabled_count": len(enabled)},
        )

    def apply(self) -> RuleOutcome:
        previous: Dict[str, str] = {}
        disabled = 0
        for path, _reason in _BLOAT_TASKS:
            state = self._task_state(path)
            previous[path] = state or "Unknown"
            if state != "Ready":
                continue
            rc, _, _ = _run_silent(["schtasks", "/Change", "/TN", path, "/Disable"])
            if rc == 0:
                disabled += 1
        if disabled == 0:
            return RuleOutcome(False, "No enabled bloat tasks found to disable.")
        return RuleOutcome(
            True,
            f"Disabled {disabled} bloat scheduled task(s).",
            backup_payload={"previous": previous},
        )

    def restore(self, payload: Dict[str, Any]) -> None:
        for path, prev_state in (payload.get("previous") or {}).items():
            if prev_state == "Ready":
                _run_silent(["schtasks", "/Change", "/TN", path, "/Enable"])

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _collect_status() -> tuple[bool, Dict[str, str]]:
        """Return (ok, {path: state}) for every task in the curated list."""
        status: Dict[str, str] = {}
        for path, _reason in _BLOAT_TASKS:
            state = ScheduledTasksBloatRule._task_state(path)
            if state is None:
                continue
            status[path] = state
        return bool(status), status

    @staticmethod
    def _task_state(path: str):
        """Return 'Ready'/'Disabled'/None via schtasks /Query /TN."""
        rc, out, _ = _run_silent(["schtasks", "/Query", "/TN", path, "/FO", "CSV", "/NH"])
        if rc != 0:
            return None
        # CSV: "<TaskName>","<Next Run Time>","<Status>"
        line = (out or "").strip().split("\n")[0]
        parts = [p.strip().strip('"') for p in line.split(",")]
        if len(parts) >= 3:
            return parts[2]
        return None
