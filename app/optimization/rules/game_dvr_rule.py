"""Xbox Game DVR / background recording rule.

Many users don't realise Game Bar's background recording costs a few percent
of GPU time. This rule disables it only on apply, fully reversible.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, Optional

from ...core.constants import IMPACT_MODERATE, RISK_LOW
from ...system.hardware_detector import HardwareSnapshot
from ...utils.logger import get_logger
from .base_rule import OptimizationRule, RuleEvaluation, RuleOutcome

log = get_logger("opt.game_dvr")

_KEY_GAMECFG = r"System\GameConfigStore"
_KEY_GAMEBAR = r"Software\Microsoft\GameBar"


class GameDVRRule(OptimizationRule):
    id = "game_dvr.disable"
    title = "Disable Game DVR background recording"
    category = "visual"
    what = (
        "Turns off Xbox Game Bar's always-on background recording "
        "(GameDVR_Enabled / AllowAutoGameMode). The Game Bar overlay itself "
        "keeps working if you still want to press Win+G."
    )
    why = (
        "Background DVR captures your screen whether you ever use the clip "
        "or not — a constant drain on GPU and disk. Disabling it has no "
        "visible effect for most players."
    )
    risk = RISK_LOW
    impact = IMPACT_MODERATE
    reversible = True

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Windows-only feature.")
        current = self._read_dvr()
        if current == 0:
            return RuleEvaluation(False, "Game DVR already disabled.")
        return RuleEvaluation(True, "Game DVR is active.", score=30)

    def apply(self) -> RuleOutcome:
        previous_dvr = self._read_dvr()
        previous_bar = self._read_gamebar()
        ok_a = self._write(_KEY_GAMECFG, "GameDVR_Enabled", 0)
        ok_b = self._write(_KEY_GAMEBAR, "AllowAutoGameMode", 0)
        if not (ok_a or ok_b):
            return RuleOutcome(False, "Could not update Game DVR registry values.")
        return RuleOutcome(
            True,
            "Game DVR disabled.",
            backup_payload={"dvr_prev": previous_dvr, "bar_prev": previous_bar},
        )

    def restore(self, payload: Dict[str, Any]) -> None:
        dvr_prev = payload.get("dvr_prev")
        bar_prev = payload.get("bar_prev")
        if dvr_prev is not None:
            self._write(_KEY_GAMECFG, "GameDVR_Enabled", int(dvr_prev))
        if bar_prev is not None:
            self._write(_KEY_GAMEBAR, "AllowAutoGameMode", int(bar_prev))

    # ------------------------------------------------------------------ registry helpers
    @staticmethod
    def _read_dvr() -> Optional[int]:
        return _read_dword(_KEY_GAMECFG, "GameDVR_Enabled")

    @staticmethod
    def _read_gamebar() -> Optional[int]:
        return _read_dword(_KEY_GAMEBAR, "AllowAutoGameMode")

    @staticmethod
    def _write(key_path: str, value_name: str, value: int) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import winreg  # type: ignore

            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0,
                                    winreg.KEY_WRITE | winreg.KEY_READ) as key:
                winreg.SetValueEx(key, value_name, 0, winreg.REG_DWORD, int(value))
            return True
        except Exception:
            log.exception("Failed writing %s\\%s", key_path, value_name)
            return False


def _read_dword(key_path: str, value_name: str) -> Optional[int]:
    if sys.platform != "win32":
        return None
    try:
        import winreg  # type: ignore

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            val, _ = winreg.QueryValueEx(key, value_name)
            return int(val)
    except FileNotFoundError:
        return None
    except Exception:
        return None
