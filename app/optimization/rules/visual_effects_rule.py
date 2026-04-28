"""Visual effects rule — suggests trimming Windows animations before gaming.

We don't patch the registry blindly. Instead we read ``VisualFXSetting`` and,
only on apply, write the "Best performance" value. Captures original for
one-tap restore.
"""
from __future__ import annotations

import sys
from typing import Any, Dict

from ...core.constants import IMPACT_MINOR, RISK_LOW
from ...system.hardware_detector import HardwareSnapshot
from ...utils.logger import get_logger
from .base_rule import OptimizationRule, RuleEvaluation, RuleOutcome

log = get_logger("opt.visual_effects")

_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"
_VALUE_NAME = "VisualFXSetting"
# 0 = Let Windows choose, 1 = Best appearance, 2 = Best performance, 3 = Custom


class VisualEffectsRule(OptimizationRule):
    id = "visual.best_performance"
    title = "Reduce Windows animations during Game Mode"
    category = "visual"
    what = (
        "Temporarily switches the 'Adjust for best performance' preset so "
        "fade/slide animations don't steal GPU cycles behind your game."
    )
    why = (
        "On integrated GPUs and older laptops, Windows animations can cost "
        "a few frames. The setting is fully reversible and user-visible."
    )
    risk = RISK_LOW
    impact = IMPACT_MINOR
    reversible = True
    requires_admin = False

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows-only rule.")
        current = self._read_current()
        if current == 2:
            return RuleEvaluation(False, "Already set to Best performance.")
        return RuleEvaluation(True, "Default appearance is active.", score=15, evidence={"current": current})

    def apply(self) -> RuleOutcome:
        previous = self._read_current()
        ok = self._write(2)
        if not ok:
            return RuleOutcome(False, "Could not write registry value.")
        return RuleOutcome(True, "Visual effects set to Best performance", backup_payload={"previous": previous})

    def restore(self, payload: Dict[str, Any]) -> None:
        prev = payload.get("previous", 0)
        self._write(int(prev))

    # ------------------------------------------------------------------ registry helpers
    @staticmethod
    def _read_current() -> int:
        if sys.platform != "win32":
            return 0
        try:
            import winreg  # type: ignore

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY_PATH) as key:
                value, _ = winreg.QueryValueEx(key, _VALUE_NAME)
                return int(value)
        except FileNotFoundError:
            return 0
        except Exception:
            log.debug("VisualFX read failed", exc_info=True)
            return 0

    @staticmethod
    def _write(value: int) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import winreg  # type: ignore

            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _KEY_PATH, 0,
                                    winreg.KEY_WRITE | winreg.KEY_READ) as key:
                winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_DWORD, int(value))
            return True
        except Exception:
            log.exception("VisualFX write failed")
            return False
