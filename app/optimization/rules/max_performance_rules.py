"""A bundle of high-impact "unleash" rules.

Each class below follows the ``OptimizationRule`` contract: declarative
metadata + ``evaluate/apply/restore``. Every change is reversible; registry
values are captured before being touched and restored from the stored
backup payload.

These rules deliberately raise the ceiling on what the engine will suggest.
Many are flagged ``RISK_MEDIUM`` because they change system-wide services
(telemetry, search indexer, Nagle's algorithm) — they're safe to turn off
for gaming but should be a conscious choice.

All rules no-op cleanly on non-Windows.
"""
from __future__ import annotations

import re
import sys
from typing import Any, Dict, Optional

from ...core.constants import (
    IMPACT_MINOR,
    IMPACT_MODERATE,
    IMPACT_SIGNIFICANT,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_SAFE,
)
from ...system.hardware_detector import HardwareSnapshot
from ...utils.logger import get_logger
from ...utils.subprocess_helper import run as _run_silent
from .base_rule import OptimizationRule, RuleEvaluation, RuleOutcome

log = get_logger("opt.max_perf")


# Well-known power-plan GUIDs
_ULTIMATE_PERFORMANCE = "e9a42b02-d5df-448d-aa00-03f14749eb61"
_HIGH_PERFORMANCE = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"


# --------------------------------------------------------------------- helpers
def _run(cmd: list[str], *, timeout: float = 15) -> tuple[int, str, str]:
    """Thin wrapper that defers to the central silent subprocess helper."""
    return _run_silent(cmd, timeout=timeout)


def _active_plan_guid() -> Optional[str]:
    rc, out, _ = _run(["powercfg", "/getactivescheme"])
    if rc != 0:
        return None
    m = re.search(r"([0-9a-fA-F\-]{36})", out)
    return m.group(1) if m else None


def _reg_read(path: str, name: str) -> tuple[Optional[str], Optional[str]]:
    """Read (value, type) for an HKLM/HKCU path. Returns (None, None) if missing."""
    rc, out, _ = _run(["reg", "query", path, "/v", name])
    if rc != 0:
        return None, None
    # Parse lines like "    <Name>    REG_DWORD    0x1"
    for line in out.splitlines():
        line = line.strip()
        if not line.lower().startswith(name.lower()):
            continue
        parts = line.split(None, 2)
        if len(parts) >= 3:
            return parts[2].strip(), parts[1].strip()
    return None, None


def _reg_write(path: str, name: str, value: str, type_: str = "REG_DWORD") -> bool:
    rc, _, _ = _run(["reg", "add", path, "/v", name, "/t", type_, "/d", value, "/f"])
    return rc == 0


def _reg_delete(path: str, name: str) -> bool:
    rc, _, _ = _run(["reg", "delete", path, "/v", name, "/f"])
    return rc == 0


def _reg_dword(path: str, name: str) -> Optional[int]:
    """Return a DWORD/QWORD value as a plain Python int, or None if missing.

    ``_reg_read`` gives us back the raw hex string (``0x64``) that
    ``reg query`` prints. Centralising the parse here avoids the fragile
    ``endswith('2')`` pattern that plagued several evaluate() methods.
    """
    val, _ = _reg_read(path, name)
    if not val:
        return None
    try:
        v = val.strip()
        return int(v, 16) if v.lower().startswith("0x") else int(v)
    except ValueError:
        return None


def _powercfg_ac_dc(guid: str, sub: str, setting: str) -> tuple[Optional[int], Optional[int]]:
    """Return the (AC, DC) current setting indices for a powercfg setting."""
    rc, out, _ = _run(["powercfg", "/query", guid, sub, setting])
    if rc != 0:
        return None, None
    ac = dc = None
    m_ac = re.search(r"Current AC Power Setting Index: 0x([0-9a-f]+)", out, re.IGNORECASE)
    m_dc = re.search(r"Current DC Power Setting Index: 0x([0-9a-f]+)", out, re.IGNORECASE)
    if m_ac:
        ac = int(m_ac.group(1), 16)
    if m_dc:
        dc = int(m_dc.group(1), 16)
    return ac, dc


def _active_plan_name() -> Optional[str]:
    """Return the *name* (e.g. 'Ultimate Performance') of the active power plan."""
    rc, out, _ = _run(["powercfg", "/getactivescheme"])
    if rc != 0:
        return None
    m = re.search(r"\(([^)]+)\)\s*$", out.strip())
    return m.group(1).strip() if m else None


def _service_state(name: str) -> Optional[str]:
    """Return one of 'running' | 'stopped' | 'missing'."""
    rc, out, _ = _run(["sc", "query", name])
    if rc != 0:
        return "missing"
    if "RUNNING" in out:
        return "running"
    if "STOPPED" in out:
        return "stopped"
    return "missing"


def _service_start_type(name: str) -> Optional[str]:
    rc, out, _ = _run(["sc", "qc", name])
    if rc != 0:
        return None
    m = re.search(r"START_TYPE\s*:\s*\d+\s+(\w+)", out)
    return m.group(1) if m else None


# ==================================================================== rules ==

class UltimatePerformancePlanRule(OptimizationRule):
    """Unlock + activate the Ultimate Performance power plan."""

    id = "power.ultimate_performance"
    title = "Unlock & activate Ultimate Performance plan"
    category = "power"
    what = (
        "Windows ships a hidden 'Ultimate Performance' power plan that fully "
        "disables CPU parking, raises minimum processor state and drops "
        "latency optimisations. We unlock and activate it."
    )
    why = (
        "Eliminates every Windows throttling heuristic. The most aggressive "
        "plan Microsoft ships — noticeable on laptops and older desktops."
    )
    risk = RISK_LOW
    impact = IMPACT_SIGNIFICANT
    reversible = True
    requires_admin = True

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        # Match by NAME so Home/Pro/Workstation all work: after a duplicate the
        # scheme GUID is new but the name is still "Ultimate Performance".
        active_name = _active_plan_name() or ""
        if "ultimate performance" in active_name.lower():
            return RuleEvaluation(False, "Already on Ultimate Performance.")
        return RuleEvaluation(True, "Ultimate plan will unlock maximum clocks.", score=70,
                              evidence={"active": active_name or "unknown"})

    def apply(self) -> RuleOutcome:
        previous = _active_plan_guid()
        # Find an existing Ultimate scheme first; only duplicate if missing.
        target = self._find_ultimate_guid()
        if not target:
            rc, out, err = _run(["powercfg", "/duplicatescheme", _ULTIMATE_PERFORMANCE])
            if rc != 0:
                return RuleOutcome(False, f"Could not unlock Ultimate plan: {err.strip()}")
            # `powercfg /duplicatescheme` prints the new GUID in its output.
            m = re.search(r"([0-9a-fA-F\-]{36})", out)
            target = m.group(1) if m else _ULTIMATE_PERFORMANCE
        rc, _, err = _run(["powercfg", "/setactive", target])
        if rc != 0:
            return RuleOutcome(False, f"Failed to activate Ultimate plan: {err.strip()}")
        return RuleOutcome(True, "Ultimate Performance is now active.",
                           backup_payload={"previous_guid": previous})

    @staticmethod
    def _find_ultimate_guid() -> Optional[str]:
        """Scan `powercfg /list` for an already-registered Ultimate Performance scheme."""
        rc, out, _ = _run(["powercfg", "/list"])
        if rc != 0:
            return None
        for line in out.splitlines():
            if "ultimate performance" in line.lower():
                m = re.search(r"([0-9a-fA-F\-]{36})", line)
                if m:
                    return m.group(1)
        return None

    def restore(self, payload: Dict[str, Any]) -> None:
        prev = payload.get("previous_guid") or _HIGH_PERFORMANCE
        _run(["powercfg", "/setactive", prev])


class DisableCoreParkingRule(OptimizationRule):
    """Force every CPU core to stay parked-off."""

    id = "cpu.no_core_parking"
    title = "Disable CPU core parking"
    category = "power"
    what = (
        "Sets the Processor Performance Core Parking Min Cores setting to "
        "100%, preventing Windows from 'parking' idle cores for power saving."
    )
    why = (
        "Parked cores take microseconds to wake, which shows up as micro-"
        "stutter in games that suddenly spawn worker threads."
    )
    risk = RISK_LOW
    impact = IMPACT_MODERATE
    reversible = True
    requires_admin = True

    # Core Parking alias on both AC and DC
    _SUB = "SUB_PROCESSOR"
    _SETTING = "CPMINCORES"

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        guid = _active_plan_guid()
        if guid:
            ac, dc = _powercfg_ac_dc(guid, self._SUB, self._SETTING)
            if ac == 100 and dc == 100:
                return RuleEvaluation(False, "Core parking already disabled on AC + DC.")
        return RuleEvaluation(True, "Force every physical core always-on.", score=40,
                              evidence={"ac": ac if guid else None,
                                         "dc": dc if guid else None})

    def apply(self) -> RuleOutcome:
        active = _active_plan_guid()
        if not active:
            return RuleOutcome(False, "Could not read active power plan.")
        # Capture previous AC value for rollback
        rc, out, _ = _run(["powercfg", "/query", active, self._SUB, self._SETTING])
        prev = None
        m = re.search(r"Current AC Power Setting Index: 0x([0-9a-f]+)", out, re.IGNORECASE)
        if m:
            prev = int(m.group(1), 16)
        r1, _, e1 = _run(["powercfg", "/setacvalueindex", active, self._SUB, self._SETTING, "100"])
        r2, _, e2 = _run(["powercfg", "/setdcvalueindex", active, self._SUB, self._SETTING, "100"])
        _run(["powercfg", "/setactive", active])
        if r1 != 0 and r2 != 0:
            return RuleOutcome(False, (e1 or e2).strip() or "powercfg failed")
        return RuleOutcome(True, "Core parking disabled.",
                           backup_payload={"guid": active, "prev_ac": prev})

    def restore(self, payload: Dict[str, Any]) -> None:
        guid = payload.get("guid") or _active_plan_guid()
        prev = payload.get("prev_ac")
        val = str(prev) if prev is not None else "0"  # 0 = default "park any core"
        _run(["powercfg", "/setacvalueindex", guid, self._SUB, self._SETTING, val])
        _run(["powercfg", "/setdcvalueindex", guid, self._SUB, self._SETTING, val])
        _run(["powercfg", "/setactive", guid])


class MinProcessorStateRule(OptimizationRule):
    """Pin minimum processor state at 100%."""

    id = "cpu.min_state_100"
    title = "Set minimum CPU state to 100%"
    category = "power"
    what = (
        "Pins the minimum processor performance state at 100% on AC so "
        "Windows never drops clocks below base frequency during gameplay."
    )
    why = (
        "Removes every 'ramp-up' delay after a brief idle — crucial for "
        "latency-sensitive moments (e.g. the instant an enemy appears)."
    )
    risk = RISK_LOW
    impact = IMPACT_MODERATE
    reversible = True
    requires_admin = True

    _SUB = "SUB_PROCESSOR"
    _SETTING = "PROCTHROTTLEMIN"

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        guid = _active_plan_guid()
        if guid:
            ac, _dc = _powercfg_ac_dc(guid, self._SUB, self._SETTING)
            if ac == 100:
                return RuleEvaluation(False, "Minimum CPU state already pinned at 100%.")
        return RuleEvaluation(True, "Keep cores at full base clock at all times.", score=50,
                              evidence={"ac": ac if guid else None})

    def apply(self) -> RuleOutcome:
        active = _active_plan_guid()
        if not active:
            return RuleOutcome(False, "No active power plan.")
        rc, out, _ = _run(["powercfg", "/query", active, self._SUB, self._SETTING])
        m = re.search(r"Current AC Power Setting Index: 0x([0-9a-f]+)", out, re.IGNORECASE)
        prev = int(m.group(1), 16) if m else None
        _run(["powercfg", "/setacvalueindex", active, self._SUB, self._SETTING, "100"])
        _run(["powercfg", "/setactive", active])
        return RuleOutcome(True, "Minimum CPU state pinned to 100%.",
                           backup_payload={"guid": active, "prev_ac": prev})

    def restore(self, payload: Dict[str, Any]) -> None:
        guid = payload.get("guid") or _active_plan_guid()
        prev = payload.get("prev_ac")
        val = str(prev) if prev is not None else "5"  # Windows default
        _run(["powercfg", "/setacvalueindex", guid, self._SUB, self._SETTING, val])
        _run(["powercfg", "/setactive", guid])


class HagsRule(OptimizationRule):
    """Enable Hardware-Accelerated GPU Scheduling."""

    id = "gpu.hw_scheduling"
    title = "Enable Hardware-accelerated GPU Scheduling"
    category = "gpu"
    what = (
        "Flips the HwSchMode registry value under GraphicsDrivers to 2 (on) "
        "so the GPU manages its own command queue instead of the CPU."
    )
    why = (
        "Modern Windows 10/11 + recent NVIDIA/AMD drivers use HAGS to reduce "
        "input lag and CPU overhead — particularly visible in DX12 titles."
    )
    risk = RISK_LOW
    impact = IMPACT_MODERATE
    reversible = True
    requires_admin = True

    _PATH = r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
    _NAME = "HwSchMode"

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        val, _ = _reg_read(self._PATH, self._NAME)
        # 2 = On, 1 = Off. Missing means the driver didn't report support.
        if val and val.endswith("2"):
            return RuleEvaluation(False, "HAGS already enabled.")
        return RuleEvaluation(True, "Hardware scheduling off — enabling can reduce CPU overhead.",
                              score=40, evidence={"current": val or "unset"})

    def apply(self) -> RuleOutcome:
        prev, _ = _reg_read(self._PATH, self._NAME)
        if not _reg_write(self._PATH, self._NAME, "2"):
            return RuleOutcome(False, "Could not write HwSchMode (need admin).")
        return RuleOutcome(True, "HAGS enabled — reboot required to take effect.",
                           backup_payload={"prev": prev})

    def restore(self, payload: Dict[str, Any]) -> None:
        prev = payload.get("prev")
        if prev and prev.lower().startswith("0x"):
            _reg_write(self._PATH, self._NAME, str(int(prev, 16)))
        else:
            _reg_delete(self._PATH, self._NAME)


class DisableFullscreenOptimizationsRule(OptimizationRule):
    """System-wide: disable DWM fullscreen optimizations."""

    id = "gpu.disable_fs_optimizations"
    title = "Disable Fullscreen Optimizations (system-wide)"
    category = "gpu"
    what = (
        "Sets GameDVR_FSEBehaviorMode to 2 and GameDVR_HonorUserFSEBehaviorMode "
        "to 1 so exclusive fullscreen games bypass DWM composition."
    )
    why = (
        "DWM's fullscreen optimization adds a compositor pass that raises input "
        "lag. Disabling it restores true exclusive fullscreen behaviour."
    )
    risk = RISK_LOW
    impact = IMPACT_MODERATE
    reversible = True
    requires_admin = False

    _PATH = r"HKCU\System\GameConfigStore"

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        v1, _ = _reg_read(self._PATH, "GameDVR_FSEBehaviorMode")
        v2, _ = _reg_read(self._PATH, "GameDVR_HonorUserFSEBehaviorMode")
        if (v1 and v1.endswith("2")) and (v2 and v2.endswith("1")):
            return RuleEvaluation(False, "Fullscreen optimizations already bypassed.")
        return RuleEvaluation(True, "Force exclusive fullscreen across every game.", score=35)

    def apply(self) -> RuleOutcome:
        prev1, _ = _reg_read(self._PATH, "GameDVR_FSEBehaviorMode")
        prev2, _ = _reg_read(self._PATH, "GameDVR_HonorUserFSEBehaviorMode")
        _reg_write(self._PATH, "GameDVR_FSEBehaviorMode", "2")
        _reg_write(self._PATH, "GameDVR_HonorUserFSEBehaviorMode", "1")
        _reg_write(self._PATH, "GameDVR_DXGIHonorFSEWindowsCompatible", "1")
        return RuleOutcome(True, "Fullscreen optimizations off system-wide.",
                           backup_payload={"p1": prev1, "p2": prev2})

    def restore(self, payload: Dict[str, Any]) -> None:
        for name, key in (("GameDVR_FSEBehaviorMode", "p1"),
                          ("GameDVR_HonorUserFSEBehaviorMode", "p2")):
            prev = payload.get(key)
            if prev and prev.lower().startswith("0x"):
                _reg_write(self._PATH, name, str(int(prev, 16)))
            else:
                _reg_delete(self._PATH, name)
        _reg_delete(self._PATH, "GameDVR_DXGIHonorFSEWindowsCompatible")


class DisableSysMainRule(OptimizationRule):
    """Stop & disable SysMain (aka Superfetch)."""

    id = "services.disable_sysmain"
    title = "Disable SysMain (Superfetch)"
    category = "services"
    what = (
        "SysMain pre-fetches frequently-used apps into RAM. On machines with "
        "SSDs its benefit is minimal and the background I/O can hurt."
    )
    why = (
        "Frees up memory, reduces background disk reads, and cuts a source "
        "of occasional frame-pacing hiccups during loading screens."
    )
    risk = RISK_LOW
    impact = IMPACT_MODERATE
    reversible = True
    requires_admin = True

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        state = _service_state("SysMain")
        start = _service_start_type("SysMain")
        if state == "missing":
            return RuleEvaluation(False, "SysMain not present on this build.")
        if state == "stopped" and start == "DISABLED":
            return RuleEvaluation(False, "SysMain already disabled.")
        return RuleEvaluation(True, "Disable SysMain to free RAM and reduce disk activity.",
                              score=35, evidence={"state": state, "start": start})

    def apply(self) -> RuleOutcome:
        prev_start = _service_start_type("SysMain") or "AUTO_START"
        prev_state = _service_state("SysMain")
        _run(["sc", "stop", "SysMain"])
        rc, _, err = _run(["sc", "config", "SysMain", "start=", "disabled"])
        if rc != 0:
            return RuleOutcome(False, f"sc config failed: {err.strip()}")
        return RuleOutcome(True, "SysMain stopped and disabled.",
                           backup_payload={"start": prev_start, "state": prev_state})

    def restore(self, payload: Dict[str, Any]) -> None:
        start = (payload.get("start") or "AUTO_START").lower()
        mapping = {
            "auto_start": "auto", "demand_start": "demand",
            "disabled": "disabled", "system_start": "system",
            "boot_start": "boot",
        }
        _run(["sc", "config", "SysMain", "start=", mapping.get(start, "auto")])
        if payload.get("state") == "running":
            _run(["sc", "start", "SysMain"])


class DisableSearchIndexerRule(OptimizationRule):
    """Stop & disable the Windows Search indexer."""

    id = "services.disable_wsearch"
    title = "Disable Windows Search indexer"
    category = "services"
    what = (
        "Halts the WSearch service which indexes file metadata for Start "
        "Menu search. Indexing runs opportunistically but can thrash SSDs."
    )
    why = (
        "One of the most common sources of unexpected background disk I/O. "
        "Disabling restores predictable disk latency during gameplay."
    )
    risk = RISK_MEDIUM
    impact = IMPACT_MODERATE
    reversible = True
    requires_admin = True

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        state = _service_state("WSearch")
        start = _service_start_type("WSearch")
        if state == "missing":
            return RuleEvaluation(False, "WSearch service not present.")
        if state == "stopped" and start == "DISABLED":
            return RuleEvaluation(False, "Windows Search already disabled.")
        return RuleEvaluation(True, "Disable Search to eliminate background disk activity.",
                              score=30, evidence={"state": state, "start": start})

    def apply(self) -> RuleOutcome:
        prev_start = _service_start_type("WSearch") or "AUTO_START"
        prev_state = _service_state("WSearch")
        _run(["sc", "stop", "WSearch"])
        rc, _, err = _run(["sc", "config", "WSearch", "start=", "disabled"])
        if rc != 0:
            return RuleOutcome(False, f"sc config failed: {err.strip()}")
        return RuleOutcome(True, "WSearch stopped and disabled.",
                           backup_payload={"start": prev_start, "state": prev_state})

    def restore(self, payload: Dict[str, Any]) -> None:
        start = (payload.get("start") or "AUTO_START").lower()
        mapping = {"auto_start": "auto", "demand_start": "demand",
                   "disabled": "disabled", "delayed_start": "delayed-auto"}
        _run(["sc", "config", "WSearch", "start=", mapping.get(start, "auto")])
        if payload.get("state") == "running":
            _run(["sc", "start", "WSearch"])


class DisableTelemetryRule(OptimizationRule):
    """Stop & disable Microsoft DiagTrack telemetry."""

    id = "services.disable_telemetry"
    title = "Disable Connected User Experiences & Telemetry"
    category = "services"
    what = (
        "Stops the DiagTrack service. It ships diagnostic data back to "
        "Microsoft and periodically flushes to disk."
    )
    why = (
        "Removes a persistent background service and occasional bursts of "
        "network + disk activity. Privacy bonus on top of the perf win."
    )
    risk = RISK_MEDIUM
    impact = IMPACT_MINOR
    reversible = True
    requires_admin = True

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        state = _service_state("DiagTrack")
        start = _service_start_type("DiagTrack")
        if state == "missing":
            return RuleEvaluation(False, "DiagTrack not present.")
        if state == "stopped" and start == "DISABLED":
            return RuleEvaluation(False, "Telemetry service already disabled.")
        return RuleEvaluation(True, "Remove the DiagTrack telemetry service.", score=20,
                              evidence={"state": state, "start": start})

    def apply(self) -> RuleOutcome:
        prev_start = _service_start_type("DiagTrack") or "AUTO_START"
        prev_state = _service_state("DiagTrack")
        _run(["sc", "stop", "DiagTrack"])
        rc, _, err = _run(["sc", "config", "DiagTrack", "start=", "disabled"])
        if rc != 0:
            return RuleOutcome(False, f"sc config failed: {err.strip()}")
        return RuleOutcome(True, "DiagTrack stopped and disabled.",
                           backup_payload={"start": prev_start, "state": prev_state})

    def restore(self, payload: Dict[str, Any]) -> None:
        start = (payload.get("start") or "AUTO_START").lower()
        mapping = {"auto_start": "auto", "demand_start": "demand",
                   "disabled": "disabled", "delayed_start": "delayed-auto"}
        _run(["sc", "config", "DiagTrack", "start=", mapping.get(start, "auto")])
        if payload.get("state") == "running":
            _run(["sc", "start", "DiagTrack"])


class NagleOffRule(OptimizationRule):
    """Disable Nagle's algorithm on every active NIC for lower input latency online."""

    id = "network.nagle_off"
    title = "Disable Nagle's algorithm (online gaming)"
    category = "network"
    what = (
        "Sets TcpAckFrequency=1 and TCPNoDelay=1 for every NIC interface key "
        "under Tcpip\\Parameters\\Interfaces."
    )
    why = (
        "Nagle buffers small TCP packets to reduce wire chatter at the cost "
        "of ~40-200 ms of extra latency. Online shooters notice it."
    )
    risk = RISK_LOW
    impact = IMPACT_MODERATE
    reversible = True
    requires_admin = True

    _BASE = r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        interfaces = self._enumerate_interfaces()
        if not interfaces:
            return RuleEvaluation(False, "No TCP interfaces detected.")
        # Rule is "already applied" only if EVERY interface has both values set to 1.
        missing = 0
        for iface in interfaces:
            if _reg_dword(iface, "TcpAckFrequency") != 1 or _reg_dword(iface, "TCPNoDelay") != 1:
                missing += 1
        if missing == 0:
            return RuleEvaluation(False, "Nagle already disabled on every interface.")
        return RuleEvaluation(
            True,
            f"TCP ACKs held on {missing}/{len(interfaces)} interfaces — latency penalty likely.",
            score=45,
            evidence={"interfaces": len(interfaces), "pending": missing},
        )

    def _enumerate_interfaces(self) -> list[str]:
        rc, out, _ = _run(["reg", "query", self._BASE])
        if rc != 0:
            return []
        return [line.strip() for line in out.splitlines()
                if line.strip().startswith(self._BASE + "\\")]

    def apply(self) -> RuleOutcome:
        interfaces = self._enumerate_interfaces()
        if not interfaces:
            return RuleOutcome(False, "No TCP interfaces found.")
        payload: Dict[str, Any] = {"interfaces": {}}
        for iface in interfaces:
            prev_ack, _ = _reg_read(iface, "TcpAckFrequency")
            prev_nd, _ = _reg_read(iface, "TCPNoDelay")
            payload["interfaces"][iface] = {"TcpAckFrequency": prev_ack, "TCPNoDelay": prev_nd}
            _reg_write(iface, "TcpAckFrequency", "1")
            _reg_write(iface, "TCPNoDelay", "1")
        return RuleOutcome(True, f"Nagle disabled on {len(interfaces)} NIC(s).",
                           backup_payload=payload)

    def restore(self, payload: Dict[str, Any]) -> None:
        for iface, vals in (payload.get("interfaces") or {}).items():
            for name, prev in vals.items():
                if prev and str(prev).lower().startswith("0x"):
                    _reg_write(iface, name, str(int(prev, 16)))
                else:
                    _reg_delete(iface, name)


class VisualPerformanceModeRule(OptimizationRule):
    """Set Windows visual effects to 'Adjust for best performance'."""

    id = "visual.performance_mode"
    title = "Adjust for best performance (visual effects)"
    category = "visual"
    what = (
        "Writes VisualFXSetting=2 to VisualEffects so Windows disables "
        "animations, shadows, thumbnails and other compositor candy."
    )
    why = (
        "Reduces DWM GPU load and input lag outside the game. Particularly "
        "noticeable on iGPU-only systems."
    )
    risk = RISK_SAFE
    impact = IMPACT_MINOR
    reversible = True
    requires_admin = False

    _PATH = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        val, _ = _reg_read(self._PATH, "VisualFXSetting")
        if val and val.endswith("2"):
            return RuleEvaluation(False, "Already using 'Best performance'.")
        return RuleEvaluation(True, "Disable animations and shadows.", score=20,
                              evidence={"current": val or "unset"})

    def apply(self) -> RuleOutcome:
        prev, _ = _reg_read(self._PATH, "VisualFXSetting")
        if not _reg_write(self._PATH, "VisualFXSetting", "2"):
            return RuleOutcome(False, "Could not write VisualFXSetting.")
        return RuleOutcome(True, "Visual effects set to 'Best performance'.",
                           backup_payload={"prev": prev})

    def restore(self, payload: Dict[str, Any]) -> None:
        prev = payload.get("prev")
        if prev and prev.lower().startswith("0x"):
            _reg_write(self._PATH, "VisualFXSetting", str(int(prev, 16)))
        else:
            _reg_delete(self._PATH, "VisualFXSetting")


class TimerResolutionRule(OptimizationRule):
    """Raise the NT timer resolution to 0.5 ms for this user session."""

    id = "input.timer_resolution"
    title = "Raise timer resolution to 0.5 ms"
    category = "input"
    what = (
        "Calls NtSetTimerResolution(5000) to request the highest timer "
        "resolution Windows supports (~0.5 ms). This is a per-process setting "
        "that remains as long as our process holds the handle."
    )
    why = (
        "Many games rely on Sleep() and WaitForSingleObject timings; a "
        "higher timer resolution tightens their frame pacing."
    )
    risk = RISK_LOW
    impact = IMPACT_MINOR
    reversible = True
    requires_admin = False

    def __init__(self) -> None:
        self._active = False

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        if self._active:
            return RuleEvaluation(False, "Timer resolution already raised.")
        return RuleEvaluation(True, "Request 0.5 ms scheduler timer.", score=20)

    def apply(self) -> RuleOutcome:
        try:
            import ctypes
            ntdll = ctypes.WinDLL("ntdll")
            current = ctypes.c_ulong()
            rc = ntdll.NtSetTimerResolution(5000, 1, ctypes.byref(current))
            if rc != 0:
                return RuleOutcome(False, f"NtSetTimerResolution returned {rc:#x}")
            self._active = True
            return RuleOutcome(True, f"Timer set to {current.value / 10000:.2f} ms.",
                               backup_payload={"requested": 5000})
        except Exception as exc:  # pragma: no cover
            return RuleOutcome(False, str(exc))

    def restore(self, payload: Dict[str, Any]) -> None:
        try:
            import ctypes
            ntdll = ctypes.WinDLL("ntdll")
            current = ctypes.c_ulong()
            ntdll.NtSetTimerResolution(payload.get("requested", 5000), 0, ctypes.byref(current))
            self._active = False
        except Exception:
            pass
