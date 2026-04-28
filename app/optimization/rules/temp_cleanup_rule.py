"""Windows temp-folder preview rule.

This rule does NOT delete anything — it surfaces how much space is recoverable
in ``%TEMP%`` and ``C:\\Windows\\Temp``. Actual deletion happens in the Cleanup
tab where the user sees exact files and confirms. Still exposed as a rule so
it shows up in the optimization plan.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

from ...core.constants import IMPACT_MINOR, RISK_SAFE
from ...system.hardware_detector import HardwareSnapshot
from ...utils.logger import get_logger
from .base_rule import OptimizationRule, RuleEvaluation, RuleOutcome

log = get_logger("opt.temp_cleanup")


class TempCleanupRule(OptimizationRule):
    id = "cleanup.temp_files_preview"
    title = "Preview recoverable temp files"
    category = "cleanup"
    what = (
        "Scans common Windows temporary folders and reports how much space "
        "could be reclaimed. Deletion happens only in the Cleanup tab with "
        "a file-level confirmation prompt."
    )
    why = (
        "Low system-drive free space increases shader stutter and paging. "
        "Recovering a few GB of temp data is an immediate, risk-free win."
    )
    risk = RISK_SAFE
    impact = IMPACT_MINOR
    reversible = False   # nothing applied; this is an advisory rule
    advisory = True

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        if sys.platform != "win32":
            return RuleEvaluation(False, "Temp folders for other platforms aren't inspected.")
        total = 0
        for p in self._paths():
            total += self._dir_size(p)
        if total < 50 * 1024 * 1024:  # below 50 MB, don't bother
            return RuleEvaluation(False, f"Only {total // (1024*1024)} MB recoverable — skip.")
        score = min(80, int(total / (1024 * 1024 * 64)))   # ~1 point per 64 MB, capped
        return RuleEvaluation(
            True,
            f"About {total // (1024 * 1024)} MB of temp files detected.",
            score=max(score, 20),
            evidence={"bytes": total},
        )

    def apply(self) -> RuleOutcome:
        # This rule is advisory — actual deletion is a separate, explicit flow.
        return RuleOutcome(True, "Recommendation recorded; run Cleanup tab to delete.")

    def restore(self, payload: Dict[str, Any]) -> None:  # pragma: no cover
        return None

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _paths() -> list[Path]:
        out: list[Path] = []
        tmp = os.environ.get("TEMP")
        if tmp:
            out.append(Path(tmp))
        sysroot = os.environ.get("SystemRoot", r"C:\Windows")
        out.append(Path(sysroot) / "Temp")
        return out

    @staticmethod
    def _dir_size(path: Path) -> int:
        total = 0
        if not path.exists():
            return 0
        try:
            for root, _, files in os.walk(path):
                for name in files:
                    fp = Path(root) / name
                    try:
                        total += fp.stat().st_size
                    except OSError:
                        continue
        except Exception:
            log.debug("dir_size failed for %s", path, exc_info=True)
        return total
