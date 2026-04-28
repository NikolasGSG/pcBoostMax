"""Startup programs analysis — counts and surfaces bloat.

We explicitly do NOT disable startup programs automatically. Disabling a
critical launcher (e.g. a VPN, gaming peripheral driver) can break the user's
setup. Instead, we surface the count, list names, and let the user open
Task Manager to decide.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List

from ...core.constants import IMPACT_MODERATE, RISK_SAFE
from ...system.hardware_detector import HardwareSnapshot
from ...utils.logger import get_logger
from .base_rule import OptimizationRule, RuleEvaluation, RuleOutcome

log = get_logger("opt.startup")


_RUN_KEYS = [
    (r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU"),
    (r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM"),
]


class StartupProgramsRule(OptimizationRule):
    id = "startup.review"
    title = "Review programs that launch with Windows"
    category = "startup"
    what = (
        "Lists the third-party programs that auto-start with your PC. This "
        "rule never disables anything automatically — it surfaces the names "
        "and counts so you can decide in Task Manager."
    )
    why = (
        "Every startup entry eats RAM, CPU cycles and, on HDDs, boot time. "
        "Launchers you rarely use (pre-installed OEM tools, update agents, "
        "cloud-sync apps) are the usual culprits."
    )
    risk = RISK_SAFE
    impact = IMPACT_MODERATE
    reversible = False   # advisory only
    advisory = True

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Startup review is Windows-specific.")
        entries = self._list_entries()
        if len(entries) < 5:
            return RuleEvaluation(False, f"Only {len(entries)} startup entries — already lean.",
                                   evidence={"entries": entries})
        score = min(70, 20 + len(entries) * 2)
        return RuleEvaluation(
            True,
            f"{len(entries)} programs launch with Windows. Review the list.",
            score=score,
            evidence={"entries": entries},
        )

    def apply(self) -> RuleOutcome:
        return RuleOutcome(True, "Startup list surfaced to the user.")

    def restore(self, payload: Dict[str, Any]) -> None:  # pragma: no cover
        return None

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _list_entries() -> List[dict]:
        if sys.platform != "win32":
            return []
        entries: List[dict] = []
        try:
            import winreg  # type: ignore

            for subkey, hive_name in _RUN_KEYS:
                hive = winreg.HKEY_CURRENT_USER if hive_name == "HKCU" else winreg.HKEY_LOCAL_MACHINE
                try:
                    with winreg.OpenKey(hive, subkey) as key:
                        i = 0
                        while True:
                            try:
                                name, value, _ = winreg.EnumValue(key, i)
                                entries.append({"name": name, "command": value, "hive": hive_name})
                                i += 1
                            except OSError:
                                break
                except FileNotFoundError:
                    continue
        except Exception:
            log.debug("Startup enumeration failed", exc_info=True)
        return entries
