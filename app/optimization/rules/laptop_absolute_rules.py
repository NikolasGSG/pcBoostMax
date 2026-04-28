"""Laptop-specific 'Absolute Performance' rules.

These rules deliberately trade battery life for raw throughput. They target
every place Windows holds a laptop back when on battery, and every subsystem
that quietly trims clocks for power savings:

    - PCIe Active-State Power Management (ASPM)
    - USB selective suspend
    - OS-level power-throttling
    - MMCSS system responsiveness / game priority
    - DC-plan mirrors AC (no battery throttling at all)
    - Battery Saver threshold clamped to 0

All rules are reversible. Many require admin to write HKLM; they'll report
``requires_admin`` so the UI can flag this up front.
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
)
from ...system.hardware_detector import HardwareSnapshot
from ...utils.logger import get_logger
from .base_rule import OptimizationRule, RuleEvaluation, RuleOutcome
from .max_performance_rules import (
    _active_plan_guid,
    _powercfg_ac_dc,
    _reg_delete,
    _reg_dword,
    _reg_read,
    _reg_write,
    _run,
)


# --------------------------------------------------------------------- helpers
def _powercfg_query(guid: str, sub: str, setting: str) -> Optional[int]:
    """Return current AC value index for a powercfg setting, or None.

    Retained for backward compat — internally defers to ``_powercfg_ac_dc``.
    """
    ac, _dc = _powercfg_ac_dc(guid, sub, setting)
    return ac


def _is_laptop(hardware: HardwareSnapshot) -> bool:
    """Heuristic — battery present ⇒ laptop."""
    return bool(getattr(hardware, "has_battery", False))


# ==================================================================== rules ==

class PcieAspmOffRule(OptimizationRule):
    """Disable PCIe Active-State Power Management on the active plan."""

    id = "power.pcie_aspm_off"
    title = "Disable PCIe link power management"
    category = "power"
    what = (
        "Sets SUB_PCIEXPRESS/ASPM to 0 (Off) on both AC and DC so the PCIe "
        "lanes feeding the discrete GPU and NVMe never downshift to save power."
    )
    why = (
        "On laptops, PCIe ASPM can cap the dGPU at low clocks and add "
        "micro-stutter the moment it tries to wake. Disabling locks the "
        "bus at full speed for the whole session."
    )
    risk = RISK_LOW
    impact = IMPACT_MODERATE
    reversible = True
    requires_admin = True

    _SUB = "SUB_PCIEXPRESS"
    _SETTING = "ASPM"

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        guid = _active_plan_guid()
        if guid:
            ac, dc = _powercfg_ac_dc(guid, self._SUB, self._SETTING)
            if ac == 0 and dc == 0:
                return RuleEvaluation(False, "PCIe ASPM already off on AC + DC.")
        return RuleEvaluation(
            True,
            "Lock PCIe lanes at full speed — big win on laptops with dGPUs.",
            score=45 if _is_laptop(hardware) else 25,
            evidence={"ac": ac if guid else None, "dc": dc if guid else None},
        )

    def apply(self) -> RuleOutcome:
        guid = _active_plan_guid()
        if not guid:
            return RuleOutcome(False, "No active power plan.")
        prev = _powercfg_query(guid, self._SUB, self._SETTING)
        r1, _, e1 = _run(["powercfg", "/setacvalueindex", guid, self._SUB, self._SETTING, "0"])
        r2, _, e2 = _run(["powercfg", "/setdcvalueindex", guid, self._SUB, self._SETTING, "0"])
        _run(["powercfg", "/setactive", guid])
        if r1 != 0 and r2 != 0:
            return RuleOutcome(False, (e1 or e2).strip() or "powercfg failed")
        return RuleOutcome(True, "PCIe ASPM disabled (AC + DC).",
                           backup_payload={"guid": guid, "prev": prev})

    def restore(self, payload: Dict[str, Any]) -> None:
        guid = payload.get("guid") or _active_plan_guid()
        prev = payload.get("prev")
        val = str(prev) if prev is not None else "2"  # 2 = Max power savings
        _run(["powercfg", "/setacvalueindex", guid, self._SUB, self._SETTING, val])
        _run(["powercfg", "/setdcvalueindex", guid, self._SUB, self._SETTING, val])
        _run(["powercfg", "/setactive", guid])


class UsbSelectiveSuspendOffRule(OptimizationRule):
    """Disable USB selective suspend."""

    id = "power.usb_selective_suspend_off"
    title = "Disable USB selective suspend"
    category = "power"
    what = (
        "Sets 2a737441-1930-4402-8d77-b2bebba308a3/48e6b7a6-50f5-4782-a5d4-"
        "53bb8f07e226 to 0 on AC and DC, so mice, keyboards, gamepads and "
        "headsets are never suspended between packets."
    )
    why = (
        "Eliminates occasional mouse / HID wake-up delays, and the "
        "~1-2 ms hiccup that happens the first time a USB device wakes "
        "mid-game."
    )
    risk = RISK_LOW
    impact = IMPACT_MINOR
    reversible = True
    requires_admin = True

    _SUB = "2a737441-1930-4402-8d77-b2bebba308a3"
    _SETTING = "48e6b7a6-50f5-4782-a5d4-53bb8f07e226"

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        guid = _active_plan_guid()
        if guid:
            ac, dc = _powercfg_ac_dc(guid, self._SUB, self._SETTING)
            if ac == 0 and dc == 0:
                return RuleEvaluation(False, "USB selective suspend already disabled on AC + DC.")
        return RuleEvaluation(True, "Keep USB peripherals always-on.", score=25,
                              evidence={"ac": ac if guid else None, "dc": dc if guid else None})

    def apply(self) -> RuleOutcome:
        guid = _active_plan_guid()
        if not guid:
            return RuleOutcome(False, "No active power plan.")
        prev = _powercfg_query(guid, self._SUB, self._SETTING)
        _run(["powercfg", "/setacvalueindex", guid, self._SUB, self._SETTING, "0"])
        _run(["powercfg", "/setdcvalueindex", guid, self._SUB, self._SETTING, "0"])
        _run(["powercfg", "/setactive", guid])
        return RuleOutcome(True, "USB selective suspend disabled.",
                           backup_payload={"guid": guid, "prev": prev})

    def restore(self, payload: Dict[str, Any]) -> None:
        guid = payload.get("guid") or _active_plan_guid()
        prev = payload.get("prev")
        val = str(prev) if prev is not None else "1"  # 1 = enabled (default)
        _run(["powercfg", "/setacvalueindex", guid, self._SUB, self._SETTING, val])
        _run(["powercfg", "/setdcvalueindex", guid, self._SUB, self._SETTING, val])
        _run(["powercfg", "/setactive", guid])


class PowerThrottlingOffRule(OptimizationRule):
    """Disable OS-level power throttling via registry."""

    id = "power.power_throttling_off"
    title = "Disable OS power-throttling"
    category = "power"
    what = (
        "Creates HKLM\\SYSTEM\\CurrentControlSet\\Control\\Power\\"
        "PowerThrottling with PowerThrottlingOff=1 so Windows stops auto-"
        "throttling background processes (and sometimes foreground ones)."
    )
    why = (
        "The OS power-throttling heuristic can silently clip a game's "
        "worker threads. Turning it off globally prevents any mis-classification."
    )
    risk = RISK_LOW
    impact = IMPACT_MODERATE
    reversible = True
    requires_admin = True

    _PATH = r"HKLM\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling"
    _NAME = "PowerThrottlingOff"

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        if _reg_dword(self._PATH, self._NAME) == 1:
            return RuleEvaluation(False, "Power-throttling already disabled.")
        return RuleEvaluation(True, "Force every thread off the throttle list.",
                              score=40 if _is_laptop(hardware) else 25)

    def apply(self) -> RuleOutcome:
        prev, _ = _reg_read(self._PATH, self._NAME)
        if not _reg_write(self._PATH, self._NAME, "1"):
            return RuleOutcome(False, "Could not write PowerThrottlingOff (need admin).")
        return RuleOutcome(True, "Power-throttling disabled.",
                           backup_payload={"prev": prev})

    def restore(self, payload: Dict[str, Any]) -> None:
        prev = payload.get("prev")
        if prev and prev.lower().startswith("0x"):
            _reg_write(self._PATH, self._NAME, str(int(prev, 16)))
        else:
            _reg_delete(self._PATH, self._NAME)


class DcMatchesAcRule(OptimizationRule):
    """Make on-battery settings identical to plugged-in for a laptop."""

    id = "power.dc_matches_ac"
    title = "Match battery settings to plugged-in"
    category = "power"
    what = (
        "Copies the min/max processor state, cooling policy and display-off "
        "timeout from the AC side to the DC side of the active plan — so "
        "the laptop never throttles when unplugged."
    )
    why = (
        "Default behaviour on every OEM laptop is to clip CPU clocks and "
        "dim the screen the instant the charger comes out. This rule kills "
        "that difference."
    )
    risk = RISK_MEDIUM
    impact = IMPACT_SIGNIFICANT
    reversible = True
    requires_admin = True

    _SETTINGS: list[tuple[str, str]] = [
        ("SUB_PROCESSOR", "PROCTHROTTLEMIN"),     # Min processor state
        ("SUB_PROCESSOR", "PROCTHROTTLEMAX"),     # Max processor state
        ("SUB_PROCESSOR", "SYSCOOLPOL"),          # Active cooling policy
        ("SUB_VIDEO", "VIDEOIDLE"),               # Turn off display
    ]

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        if not _is_laptop(hardware):
            return RuleEvaluation(False, "Desktop detected — no DC plan to mirror.")
        guid = _active_plan_guid()
        if guid:
            mismatches = 0
            for sub, setting in self._SETTINGS:
                ac, dc = _powercfg_ac_dc(guid, sub, setting)
                if ac is None or dc is None:
                    continue
                if ac != dc:
                    mismatches += 1
            if mismatches == 0:
                return RuleEvaluation(False, "DC already mirrors AC for every target setting.")
        return RuleEvaluation(True, "Keep laptop at full power even on battery.", score=60,
                              evidence={"mismatches": mismatches if guid else None})

    def apply(self) -> RuleOutcome:
        guid = _active_plan_guid()
        if not guid:
            return RuleOutcome(False, "No active power plan.")

        previous: list[dict] = []
        mirrored = 0
        for sub, setting in self._SETTINGS:
            ac, dc_prev = _powercfg_ac_dc(guid, sub, setting)
            if ac is None:
                continue
            previous.append({"sub": sub, "setting": setting, "dc_prev": dc_prev})
            _run(["powercfg", "/setdcvalueindex", guid, sub, setting, str(ac)])
            mirrored += 1
        _run(["powercfg", "/setactive", guid])

        if not mirrored:
            return RuleOutcome(False, "Could not mirror any DC settings.")
        return RuleOutcome(True, f"Mirrored {mirrored} DC settings to AC.",
                           backup_payload={"guid": guid, "previous": previous})

    def restore(self, payload: Dict[str, Any]) -> None:
        guid = payload.get("guid") or _active_plan_guid()
        for entry in payload.get("previous") or []:
            dc_prev = entry.get("dc_prev")
            if dc_prev is None:
                continue
            _run(["powercfg", "/setdcvalueindex", guid,
                  entry["sub"], entry["setting"], str(dc_prev)])
        _run(["powercfg", "/setactive", guid])


class SystemResponsivenessRule(OptimizationRule):
    """Pin MMCSS system responsiveness at 0 and unclip network throttling."""

    id = "system.mmcss_responsiveness"
    title = "Maximise MMCSS system responsiveness"
    category = "system"
    what = (
        "Sets SystemResponsiveness=0 and NetworkThrottlingIndex=0xFFFFFFFF "
        "under HKLM\\...\\Multimedia\\SystemProfile so MMCSS reserves the "
        "minimum possible time for non-multimedia work."
    )
    why = (
        "Default SystemResponsiveness=20 means MMCSS reserves 20% of CPU "
        "for other work. For a game that *is* the multimedia workload, "
        "that's wasted headroom."
    )
    risk = RISK_LOW
    impact = IMPACT_MODERATE
    reversible = True
    requires_admin = True

    _PATH = r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        sr = _reg_dword(self._PATH, "SystemResponsiveness")
        nti = _reg_dword(self._PATH, "NetworkThrottlingIndex")
        if sr == 0 and nti == 0xFFFFFFFF:
            return RuleEvaluation(False, "Already at max MMCSS responsiveness.")
        return RuleEvaluation(True, "Give games the CPU reserve MMCSS normally holds.", score=35,
                              evidence={"SystemResponsiveness": sr, "NetworkThrottlingIndex": nti})

    def apply(self) -> RuleOutcome:
        prev_sr, _ = _reg_read(self._PATH, "SystemResponsiveness")
        prev_nti, _ = _reg_read(self._PATH, "NetworkThrottlingIndex")
        ok1 = _reg_write(self._PATH, "SystemResponsiveness", "0")
        ok2 = _reg_write(self._PATH, "NetworkThrottlingIndex", "ffffffff")
        if not (ok1 or ok2):
            return RuleOutcome(False, "Could not write MMCSS values (need admin).")
        return RuleOutcome(True, "MMCSS reserves dropped, network throttling unclipped.",
                           backup_payload={"prev_sr": prev_sr, "prev_nti": prev_nti})

    def restore(self, payload: Dict[str, Any]) -> None:
        prev_sr = payload.get("prev_sr")
        prev_nti = payload.get("prev_nti")
        if prev_sr and prev_sr.lower().startswith("0x"):
            _reg_write(self._PATH, "SystemResponsiveness", str(int(prev_sr, 16)))
        else:
            _reg_delete(self._PATH, "SystemResponsiveness")
        if prev_nti and prev_nti.lower().startswith("0x"):
            _reg_write(self._PATH, "NetworkThrottlingIndex", str(int(prev_nti, 16)))
        else:
            _reg_delete(self._PATH, "NetworkThrottlingIndex")


class MmcssGamesBoostRule(OptimizationRule):
    """Promote the 'Games' MMCSS profile to highest priority."""

    id = "system.mmcss_games_boost"
    title = "Boost MMCSS 'Games' profile priority"
    category = "system"
    what = (
        "Under HKLM\\...\\Multimedia\\SystemProfile\\Tasks\\Games, raises GPU "
        "Priority to 8, CPU Priority to 6, Scheduling Category to 'High', "
        "SFIO Priority to 'High', and sets Clock Rate to 0x2710."
    )
    why = (
        "Games that cooperate with MMCSS are moved closer to the front of "
        "the scheduler queue — fewer preemptions, lower frame pacing jitter."
    )
    risk = RISK_LOW
    impact = IMPACT_MINOR
    reversible = True
    requires_admin = True

    _PATH = r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games"
    _TARGETS: list[tuple[str, str, str]] = [
        ("GPU Priority", "8", "REG_DWORD"),
        ("Priority", "6", "REG_DWORD"),
        ("Scheduling Category", "High", "REG_SZ"),
        ("SFIO Priority", "High", "REG_SZ"),
        ("Clock Rate", "2710", "REG_DWORD"),  # 10000 decimal
    ]

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        # Rule is "already applied" only if every target key matches exactly.
        missing = 0
        for name, expected, type_ in self._TARGETS:
            if type_ == "REG_DWORD":
                if _reg_dword(self._PATH, name) != int(expected, 16):
                    missing += 1
            else:  # REG_SZ
                val, _ = _reg_read(self._PATH, name)
                if (val or "").strip().lower() != expected.lower():
                    missing += 1
        if missing == 0:
            return RuleEvaluation(False, "Games MMCSS profile already at max priority.")
        return RuleEvaluation(True, "Rank Games profile at highest MMCSS priority.", score=20,
                              evidence={"pending": missing})

    def apply(self) -> RuleOutcome:
        previous: Dict[str, str] = {}
        wrote = 0
        for name, value, type_ in self._TARGETS:
            prev, _ = _reg_read(self._PATH, name)
            previous[name] = prev or ""
            if _reg_write(self._PATH, name, value, type_):
                wrote += 1
        if wrote == 0:
            return RuleOutcome(False, "Could not write MMCSS Games keys (need admin).")
        return RuleOutcome(True, f"Games MMCSS profile boosted ({wrote}/{len(self._TARGETS)} keys).",
                           backup_payload={"previous": previous})

    def restore(self, payload: Dict[str, Any]) -> None:
        previous = payload.get("previous") or {}
        for name, _value, type_ in self._TARGETS:
            prev = previous.get(name)
            if not prev:
                _reg_delete(self._PATH, name)
                continue
            if type_ == "REG_SZ":
                _reg_write(self._PATH, name, prev, "REG_SZ")
            elif prev.lower().startswith("0x"):
                _reg_write(self._PATH, name, str(int(prev, 16)))
            else:
                _reg_write(self._PATH, name, prev)


class BatterySaverOffRule(OptimizationRule):
    """Never trigger Battery Saver automatically."""

    id = "power.battery_saver_off"
    title = "Disable Battery Saver auto-activation"
    category = "power"
    what = (
        "Clears the Battery Saver auto-activation threshold so Windows "
        "never dims the display / throttles background apps when the "
        "battery dips below a certain level."
    )
    why = (
        "At low battery, Battery Saver silently throttles background apps "
        "and dims the display — ruining any competitive session."
    )
    risk = RISK_LOW
    impact = IMPACT_MINOR
    reversible = True
    requires_admin = False

    _SUB = "SUB_ENERGYSAVER"
    _SETTING = "ESBATTTHRESHOLD"

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        if not _is_laptop(hardware):
            return RuleEvaluation(False, "Desktop — Battery Saver is inactive anyway.")
        guid = _active_plan_guid()
        if guid:
            _ac, dc = _powercfg_ac_dc(guid, self._SUB, self._SETTING)
            if dc == 0:
                return RuleEvaluation(False, "Battery Saver threshold already at 0%.")
        return RuleEvaluation(True, "Battery Saver will never auto-engage.", score=20,
                              evidence={"dc": dc if guid else None})

    def apply(self) -> RuleOutcome:
        guid = _active_plan_guid()
        if not guid:
            return RuleOutcome(False, "No active power plan.")
        prev = _powercfg_query(guid, self._SUB, self._SETTING)
        _run(["powercfg", "/setdcvalueindex", guid, self._SUB, self._SETTING, "0"])
        _run(["powercfg", "/setactive", guid])
        return RuleOutcome(True, "Battery Saver threshold set to 0%.",
                           backup_payload={"guid": guid, "prev": prev})

    def restore(self, payload: Dict[str, Any]) -> None:
        guid = payload.get("guid") or _active_plan_guid()
        prev = payload.get("prev")
        val = str(prev) if prev is not None else "20"  # Windows default = 20%
        _run(["powercfg", "/setdcvalueindex", guid, self._SUB, self._SETTING, val])
        _run(["powercfg", "/setactive", guid])


class GpuPreferMaxPerfRule(OptimizationRule):
    """Set Windows graphics preference to 'High performance' for the dGPU."""

    id = "gpu.prefer_high_performance"
    title = "Prefer high-performance GPU globally"
    category = "gpu"
    what = (
        "Writes HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences\\"
        "DirectXUserGlobalSettings = 'VRROptimizeEnable=0;VRRCtrlMode=0;"
        "SwapEffectUpgradeEnable=1;' so DX apps default to the discrete GPU "
        "on MSHybrid laptops."
    )
    why = (
        "Default OEM behaviour picks the iGPU for any app that doesn't "
        "explicitly ask for the dGPU. This rule makes 'High performance' "
        "the default for every game."
    )
    risk = RISK_LOW
    impact = IMPACT_MODERATE
    reversible = True
    requires_admin = False

    _PATH = r"HKCU\Software\Microsoft\DirectX\UserGpuPreferences"
    _NAME = "DirectXUserGlobalSettings"
    _VALUE = "VRROptimizeEnable=0;VRRCtrlMode=0;SwapEffectUpgradeEnable=1;"

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows only.")
        if not _is_laptop(hardware):
            return RuleEvaluation(False, "Single-GPU desktop — no preference to set.")
        current, _ = _reg_read(self._PATH, self._NAME)
        if current and "vrroptimizeenable=0" in current.lower():
            return RuleEvaluation(False, "High-performance GPU preference already set.")
        return RuleEvaluation(True, "Force discrete GPU as the global default.", score=45,
                              evidence={"current": current or "unset"})

    def apply(self) -> RuleOutcome:
        prev, _ = _reg_read(self._PATH, self._NAME)
        ok = _reg_write(self._PATH, self._NAME, self._VALUE, "REG_SZ")
        if not ok:
            return RuleOutcome(False, "Could not write DirectXUserGlobalSettings.")
        return RuleOutcome(True, "Global GPU preference set to 'High performance'.",
                           backup_payload={"prev": prev})

    def restore(self, payload: Dict[str, Any]) -> None:
        prev = payload.get("prev")
        if prev:
            _reg_write(self._PATH, self._NAME, prev, "REG_SZ")
        else:
            _reg_delete(self._PATH, self._NAME)
