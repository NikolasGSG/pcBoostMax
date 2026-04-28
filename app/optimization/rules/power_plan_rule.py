"""Power plan rule — switch to High Performance before a game session.

Uses ``powercfg`` which is always present on Windows. Reversible: we capture
the current active plan's GUID and restore it on rollback.
"""
from __future__ import annotations

import re
import sys
from typing import Any, Dict, Optional

from ...core.constants import IMPACT_MODERATE, RISK_LOW
from ...system.hardware_detector import HardwareSnapshot
from ...utils.logger import get_logger
from ...utils.subprocess_helper import run as _run_silent
from .base_rule import OptimizationRule, RuleEvaluation, RuleOutcome

log = get_logger("opt.power_plan")

# Well-known GUIDs built-in to every Windows install
HIGH_PERFORMANCE = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
ULTIMATE_PERFORMANCE = "e9a42b02-d5df-448d-aa00-03f14749eb61"


class PowerPlanRule(OptimizationRule):
    id = "power.high_performance"
    title = "Switch to High Performance power plan"
    category = "power"
    what = (
        "Temporarily sets Windows to the High Performance power plan. "
        "This removes CPU frequency throttling when idle for short periods."
    )
    why = (
        "The default 'Balanced' plan can cause short frame dips when the CPU "
        "scales back down between busy moments. High Performance keeps cores "
        "responsive — particularly noticeable in competitive games."
    )
    risk = RISK_LOW
    impact = IMPACT_MODERATE
    reversible = True
    requires_admin = False

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Power plan rule only runs on Windows.")
        current = self._current_plan_guid()
        if not current:
            return RuleEvaluation(True, "Current plan unknown — recommending High Performance.", score=40)
        if current.lower() in (HIGH_PERFORMANCE, ULTIMATE_PERFORMANCE):
            return RuleEvaluation(
                False,
                "Already on High Performance / Ultimate plan.",
                evidence={"current": current},
            )
        return RuleEvaluation(
            True,
            "Balanced plan is active — High Performance reduces micro-stutter.",
            score=55,
            evidence={"current": current},
        )

    def apply(self) -> RuleOutcome:
        current = self._current_plan_guid()
        if not current:
            return RuleOutcome(False, "Could not read current power plan.")
        ok, err = self._set_plan(HIGH_PERFORMANCE)
        if not ok:
            # Ultimate may not exist; HighPerf almost always does. If it fails, fall back gracefully.
            return RuleOutcome(False, f"powercfg failed: {err}")
        return RuleOutcome(True, "Switched to High Performance", backup_payload={"previous_guid": current})

    def restore(self, payload: Dict[str, Any]) -> None:
        prev = payload.get("previous_guid")
        if prev:
            ok, err = self._set_plan(prev)
            if not ok:
                raise RuntimeError(f"Failed to restore previous power plan: {err}")

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _current_plan_guid() -> Optional[str]:
        return PowerPlanService.active_plan_guid_static()

    @staticmethod
    def _set_plan(guid: str) -> tuple[bool, str]:
        rc, out, err = _run_silent(["powercfg", "/setactive", guid], timeout=10)
        if rc == 0:
            return True, ""
        return False, (err or out).strip()


class PowerPlanService:
    """Reusable wrapper around ``powercfg`` for code outside the rules engine.

    The Game Profile service uses this to swap power plans for the
    duration of a game session and restore on exit, completely
    independent of the rule-based optimization flow.
    """

    _ALIASES = {
        "high":      HIGH_PERFORMANCE,
        "ultimate":  ULTIMATE_PERFORMANCE,
        "balanced":  "381b4222-f694-41f0-9685-ff5bb260df2e",
        "powersaver":"a1841308-3541-4fab-bc81-f71556f20b4a",
    }

    def active_plan_guid(self) -> Optional[str]:
        return self.active_plan_guid_static()

    @staticmethod
    def active_plan_guid_static() -> Optional[str]:
        rc, out, _ = _run_silent(["powercfg", "/getactivescheme"], timeout=10)
        if rc != 0:
            return None
        m = re.search(r"([0-9a-fA-F\-]{36})", out)
        return m.group(1) if m else None

    def guid_for_alias(self, alias: str) -> Optional[str]:
        return self._ALIASES.get((alias or "").lower())

    def activate(self, guid: str) -> bool:
        rc, _out, _err = _run_silent(["powercfg", "/setactive", guid], timeout=10)
        return rc == 0
