"""Smoke-test the presets + Apply Report dialog rendering.

Mocks the OptimizationEngine.apply_plan() so we don't actually mutate the
system, then simulates a mixed report (applied / failed / needs_reboot)
so the dialog's visual layout is exercised.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from app.ui.theme import Theme
from app.ui.widgets.apply_report_dialog import ApplyReportDialog, RuleResult


def main() -> int:
    app = QApplication(sys.argv)
    theme = Theme()
    theme.apply(app)

    results = [
        RuleResult("power.ultimate_performance", "Unlock Ultimate Performance plan",
                   status="applied", detail="Ultimate Performance is now active.",
                   admin_required=True),
        RuleResult("cpu.no_core_parking", "Disable CPU core parking",
                   status="applied", detail="Core parking disabled.",
                   admin_required=True),
        RuleResult("gpu.hw_scheduling", "Enable Hardware-accelerated GPU Scheduling",
                   status="needs_reboot", detail="HAGS enabled — reboot required.",
                   admin_required=True),
        RuleResult("services.disable_telemetry", "Disable Telemetry",
                   status="failed", detail="sc config failed: access denied",
                   admin_required=True),
        RuleResult("power.dc_matches_ac", "Match battery settings to plugged-in",
                   status="applied", detail="Mirrored 4 DC settings to AC.",
                   admin_required=True),
        RuleResult("system.mmcss_responsiveness", "Max MMCSS responsiveness",
                   status="not_verified",
                   detail="Post-apply check: system still reports setting as not applied.",
                   admin_required=True),
    ]

    dlg = ApplyReportDialog(
        results=results,
        restore_point_created=True,
        restore_point_reason="",
        palette=theme.palette,
        typography=theme.type,
    )
    dlg.show()
    QTimer.singleShot(800, dlg.accept)
    code = app.exec()
    print("Apply report smoke OK")
    return code


if __name__ == "__main__":
    sys.exit(main())
