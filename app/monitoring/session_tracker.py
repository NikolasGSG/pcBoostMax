"""Session tracking for Game Mode and before/after comparisons.

A "session" is a window of samples (e.g. during Game Mode) with a baseline
captured before it started. :class:`SessionTracker` exposes helpers to
summarise averages so the UI can draw clean comparisons.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from ..core.event_bus import EventBus
from ..utils.logger import get_logger
from .performance_monitor import MetricSample

log = get_logger("monitoring.session")


@dataclass
class SessionSummary:
    label: str
    started_at: float
    ended_at: Optional[float] = None
    avg_cpu: float = 0.0
    avg_ram: float = 0.0
    peak_cpu: float = 0.0
    peak_ram: float = 0.0
    samples: int = 0

    @property
    def duration(self) -> float:
        return (self.ended_at or time.time()) - self.started_at


@dataclass
class _RunningSession:
    label: str
    started_at: float
    cpu_total: float = 0.0
    ram_total: float = 0.0
    peak_cpu: float = 0.0
    peak_ram: float = 0.0
    samples: int = 0


class SessionTracker:
    """Records a baseline and subsequent session; subscribes to monitor samples."""

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._baseline: Optional[SessionSummary] = None
        self._active: Optional[_RunningSession] = None
        self._history: List[SessionSummary] = []
        self._unsub = bus.subscribe("monitor.sample", self._on_sample)

    # ------------------------------------------------------------------ public
    def start(self, label: str) -> None:
        self._active = _RunningSession(label=label, started_at=time.time())
        log.info("Session started: %s", label)
        self.bus.publish("session.started", label)

    def stop(self) -> Optional[SessionSummary]:
        if not self._active:
            return None
        s = self._active
        summary = SessionSummary(
            label=s.label,
            started_at=s.started_at,
            ended_at=time.time(),
            avg_cpu=(s.cpu_total / s.samples) if s.samples else 0.0,
            avg_ram=(s.ram_total / s.samples) if s.samples else 0.0,
            peak_cpu=s.peak_cpu,
            peak_ram=s.peak_ram,
            samples=s.samples,
        )
        self._history.append(summary)
        self._active = None
        log.info("Session ended: %s (%.1fs, avg CPU %.0f%%, avg RAM %.0f%%)",
                 summary.label, summary.duration, summary.avg_cpu, summary.avg_ram)
        self.bus.publish("session.ended", summary)
        return summary

    def capture_baseline(self, samples: List[MetricSample], label: str = "Baseline") -> SessionSummary:
        if not samples:
            base = SessionSummary(label=label, started_at=time.time(), ended_at=time.time())
        else:
            base = SessionSummary(
                label=label,
                started_at=samples[0].ts,
                ended_at=samples[-1].ts,
                avg_cpu=sum(s.cpu_percent for s in samples) / len(samples),
                avg_ram=sum(s.ram_percent for s in samples) / len(samples),
                peak_cpu=max(s.cpu_percent for s in samples),
                peak_ram=max(s.ram_percent for s in samples),
                samples=len(samples),
            )
        self._baseline = base
        self.bus.publish("session.baseline", base)
        return base

    @property
    def baseline(self) -> Optional[SessionSummary]:
        return self._baseline

    @property
    def history(self) -> List[SessionSummary]:
        return list(self._history)

    @property
    def is_active(self) -> bool:
        return self._active is not None

    # ------------------------------------------------------------------ internal
    def _on_sample(self, sample: MetricSample) -> None:
        if not self._active:
            return
        a = self._active
        a.samples += 1
        a.cpu_total += sample.cpu_percent
        a.ram_total += sample.ram_percent
        a.peak_cpu = max(a.peak_cpu, sample.cpu_percent)
        a.peak_ram = max(a.peak_ram, sample.ram_percent)
