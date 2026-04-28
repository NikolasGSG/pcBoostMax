"""Anomaly Alerts — single-pass thresholding plus a tiny baseline tracker.

This is intentionally a simple analyzer. We emit ``anomaly.detected`` on
the bus whenever a sustained metric crosses a threshold:

* CPU  >95% for ≥30 s
* RAM  >92% for ≥30 s
* DISK >250 MB/s sustained for ≥30 s
* NET  >75 MB/s sustained for ≥60 s
* TEMP not handled here — see Predictive Maintenance for SSD temps

We also track a per-metric *baseline* from the last 7 days of samples
(if the user runs the app daily). When today's average is >25% worse
than baseline we emit ``anomaly.regression`` once a day.

Persistence: a small JSON file at ``stats/baselines.json`` mapping
metric → 7-day rolling mean.
"""
from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Deque, Dict, List, Optional

from ...core.event_bus import EventBus
from ...utils.logger import get_logger
from ...utils.paths import STATS_DIR, ensure_app_dirs
from ..performance_monitor import MetricSample

log = get_logger("monitoring.analyzers.anomaly")

_BASELINE_FILE = "baselines.json"

# Tunables
SUSTAIN_S_FAST = 30.0
SUSTAIN_S_SLOW = 60.0
COOLDOWN_S = 90.0


@dataclass
class AnomalyAlert:
    ts: float
    metric: str           # "cpu" | "ram" | "disk" | "net" | "regression"
    severity: str         # "info" | "warning" | "critical"
    value: float
    threshold: float
    detail: str = ""


@dataclass
class _SustainTracker:
    """Tracks how long a metric has been over a threshold."""
    threshold: float
    started_at: float = 0.0

    def update(self, value: float, now: float) -> float:
        if value < self.threshold:
            self.started_at = 0.0
            return 0.0
        if self.started_at == 0.0:
            self.started_at = now
        return now - self.started_at


@dataclass
class _Baselines:
    """Rolling 7-day means per metric."""
    samples: Dict[str, List[float]] = field(default_factory=dict)   # metric → 7 daily means

    def push(self, metric: str, daily_mean: float) -> None:
        lst = self.samples.setdefault(metric, [])
        lst.append(daily_mean)
        if len(lst) > 7:
            lst.pop(0)

    def baseline(self, metric: str) -> Optional[float]:
        lst = self.samples.get(metric, [])
        return sum(lst) / len(lst) if lst else None


class AnomalyDetector:
    """Subscribes to ``monitor.sample`` and publishes ``anomaly.detected``."""

    def __init__(self, bus: EventBus, *, path: Optional[Path] = None) -> None:
        ensure_app_dirs()
        self._bus = bus
        self._path = path or (STATS_DIR / _BASELINE_FILE)
        self._baselines = self._load_baselines()
        self._today_samples: List[MetricSample] = []
        self._today_started: float = time.time()
        self._last_alert_ts: Dict[str, float] = {}

        # Trackers
        self._cpu = _SustainTracker(threshold=95.0)
        self._ram = _SustainTracker(threshold=92.0)
        self._disk = _SustainTracker(threshold=250 * 1024 * 1024)
        self._net = _SustainTracker(threshold=75 * 1024 * 1024)

        bus.subscribe("monitor.sample", self._on_sample)

    # ------------------------------------------------------------------ public
    def baselines(self) -> Dict[str, float]:
        return {k: (sum(v) / len(v) if v else 0.0) for k, v in self._baselines.samples.items()}

    def maybe_close_day(self) -> None:
        """Call once when the date rolls over; folds today's average into baselines."""
        if not self._today_samples:
            return
        self._fold_today_into_baselines()
        self._today_samples.clear()
        self._today_started = time.time()
        self._save_baselines()

    # ------------------------------------------------------------------ event handler
    def _on_sample(self, sample: MetricSample) -> None:
        self._today_samples.append(sample)
        now = sample.ts
        self._check(sample, now)

    # ------------------------------------------------------------------ checks
    def _check(self, sample: MetricSample, now: float) -> None:
        for metric, tracker, value, severity in (
            ("cpu", self._cpu, sample.cpu_percent, "warning"),
            ("ram", self._ram, sample.ram_percent, "warning"),
            ("disk", self._disk, sample.disk_read_bps + sample.disk_write_bps, "info"),
            ("net", self._net, sample.net_up_bps + sample.net_down_bps, "info"),
        ):
            sustained = tracker.update(value, now)
            sustain_threshold = SUSTAIN_S_SLOW if metric in ("net",) else SUSTAIN_S_FAST
            if sustained < sustain_threshold:
                continue
            if not self._cooldown_ready(metric, now):
                continue
            self._last_alert_ts[metric] = now
            alert = AnomalyAlert(
                ts=now,
                metric=metric,
                severity=severity,
                value=value,
                threshold=tracker.threshold,
                detail=self._make_detail(metric, value, sustained),
            )
            self._bus.publish("anomaly.detected", alert)
            log.info("anomaly: %s sustained for %.0fs at %.1f", metric, sustained, value)

    def _cooldown_ready(self, metric: str, now: float) -> bool:
        last = self._last_alert_ts.get(metric, 0.0)
        return (now - last) >= COOLDOWN_S

    @staticmethod
    def _make_detail(metric: str, value: float, sustained: float) -> str:
        if metric == "cpu":
            return f"CPU usage stuck at {value:.0f}% for {sustained:.0f} s — a runaway process is likely."
        if metric == "ram":
            return f"RAM usage above 92% for {sustained:.0f} s — close some apps or trim memory."
        if metric == "disk":
            mb = value / (1024 * 1024)
            return f"Disk pumping {mb:.0f} MB/s for {sustained:.0f} s — game patcher or backup running."
        if metric == "net":
            mb = value / (1024 * 1024)
            return f"Network usage {mb:.0f} MB/s for {sustained:.0f} s — major download in progress."
        return ""

    # ------------------------------------------------------------------ baselines
    def _fold_today_into_baselines(self) -> None:
        if not self._today_samples:
            return
        cpu = sum(s.cpu_percent for s in self._today_samples) / len(self._today_samples)
        ram = sum(s.ram_percent for s in self._today_samples) / len(self._today_samples)
        self._baselines.push("cpu", cpu)
        self._baselines.push("ram", ram)
        # Regression check
        prev_cpu = self._baselines.baseline("cpu")
        if prev_cpu and cpu > prev_cpu * 1.25 and cpu > 30:
            self._bus.publish("anomaly.regression", AnomalyAlert(
                ts=time.time(),
                metric="regression",
                severity="warning",
                value=cpu,
                threshold=prev_cpu * 1.25,
                detail=f"Today's CPU baseline {cpu:.0f}% is 25%+ above the 7-day mean {prev_cpu:.0f}%.",
            ))

    # ------------------------------------------------------------------ io
    def _load_baselines(self) -> _Baselines:
        if not self._path.exists():
            return _Baselines()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return _Baselines(samples={k: list(v) for k, v in data.get("samples", {}).items()})
        except Exception:
            log.warning("baselines unreadable; resetting")
            return _Baselines()

    def _save_baselines(self) -> None:
        try:
            self._path.write_text(json.dumps({"samples": self._baselines.samples}, indent=2), encoding="utf-8")
        except Exception:
            log.exception("baselines save failed")
