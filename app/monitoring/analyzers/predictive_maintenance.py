"""Predictive Maintenance — extrapolate from health-history time-series.

We project SSD wear forward to estimate "days until 100% wear" using a
simple linear regression on the daily SMART history captured by
:class:`NvmeHealthInspector`. We also flag boot-time regressions
(>30 % slower than the 7-day mean from :class:`BootTimeService`).

Output: a list of :class:`MaintenancePrediction` records, severity
ranked. Cheap to compute (linear pass), so the UI calls it on demand.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ...system.inspectors.nvme_health import NvmeHealthInspector, NvmeHealthRecord
from ...utils.logger import get_logger
from ..boot_time import BootTimeService

log = get_logger("monitoring.analyzers.predictive")


@dataclass
class MaintenancePrediction:
    """One forward-looking warning."""
    id: str
    severity: str           # "info" | "warning" | "critical"
    title: str
    detail: str
    fix_hint: str = ""
    evidence: Dict[str, float] = field(default_factory=dict)


class PredictiveMaintenance:
    """Read-only analyzer.

    Composed with :class:`NvmeHealthInspector` and
    :class:`BootTimeService` because they own the time-series.
    """

    def __init__(
        self,
        *,
        nvme: Optional[NvmeHealthInspector] = None,
        boot: Optional[BootTimeService] = None,
    ) -> None:
        self._nvme = nvme or NvmeHealthInspector()
        self._boot = boot or BootTimeService()

    def predictions(self) -> List[MaintenancePrediction]:
        out: List[MaintenancePrediction] = []
        out.extend(self._ssd_wear_predictions())
        out.extend(self._boot_time_predictions())
        return out

    # ------------------------------------------------------------------ SSD wear
    def _ssd_wear_predictions(self) -> List[MaintenancePrediction]:
        # Group history by device.
        history = self._nvme.history(days=180)
        by_device: Dict[str, List[NvmeHealthRecord]] = {}
        for rec in history:
            by_device.setdefault(rec.device, []).append(rec)

        out: List[MaintenancePrediction] = []
        for device, recs in by_device.items():
            if len(recs) < 7:
                continue
            recs.sort(key=lambda r: r.ts)
            first, last = recs[0], recs[-1]
            elapsed_days = max(1.0, (last.ts - first.ts) / 86400.0)
            wear_delta = last.wear_percent - first.wear_percent
            if wear_delta <= 0.0:
                continue
            wear_per_day = wear_delta / elapsed_days
            remaining = max(0.0, 100.0 - last.wear_percent)
            days_to_eol = remaining / wear_per_day if wear_per_day > 0 else float("inf")

            if days_to_eol < 90:
                severity = "critical"
            elif days_to_eol < 365:
                severity = "warning"
            elif days_to_eol < 365 * 2:
                severity = "info"
            else:
                continue

            eol_date = (dt.date.today() + dt.timedelta(days=int(days_to_eol))).isoformat()
            model = last.model or device
            out.append(MaintenancePrediction(
                id=f"ssd_eol_{device}",
                severity=severity,
                title=f"{model} projected end-of-life: {eol_date}",
                detail=(
                    f"At the current wear rate (+{wear_per_day:.2f}% / day), this drive "
                    f"will reach 100% rated wear in approximately {int(days_to_eol)} days."
                ),
                fix_hint="Plan a replacement before performance degrades.",
                evidence={
                    "wear_per_day": wear_per_day,
                    "current_wear": last.wear_percent,
                    "days_to_eol": days_to_eol,
                },
            ))
        return out

    # ------------------------------------------------------------------ Boot regression
    def _boot_time_predictions(self) -> List[MaintenancePrediction]:
        latest = self._boot.latest()
        baseline_avg = self._boot.average_total_ms(last=7)
        if not latest or not baseline_avg or latest.total_ms <= 0:
            return []
        ratio = latest.total_ms / baseline_avg if baseline_avg else 1.0
        if ratio < 1.30:
            return []
        out = [MaintenancePrediction(
            id="boot_slowdown",
            severity="warning" if ratio < 1.6 else "critical",
            title=f"Boot is {((ratio - 1) * 100):.0f}% slower than your baseline",
            detail=(
                f"Latest boot took {latest.total_ms / 1000:.0f} s vs your 7-day "
                f"mean of {baseline_avg / 1000:.0f} s. Common causes: a new "
                f"startup app, a stuck driver, or a failing drive."
            ),
            fix_hint="Open Optimize → Startup Programs and remove anything new.",
            evidence={
                "latest_ms": float(latest.total_ms),
                "baseline_ms": baseline_avg,
                "ratio": ratio,
            },
        )]
        return out
