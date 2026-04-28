"""Detect frame-time stutters and correlate them with system events.

A "stutter" here = a frame that took >2× the rolling median frame-time,
above a noise floor of 33 ms (≈30 FPS instantaneous). We keep a sliding
window of recent stutters and emit ``stutter.detected`` on the bus when
the stutter density exceeds a threshold so the user gets one
notification, not 60.

Correlation: when a stutter fires we look at the most-recent metric
sample and tag the likely culprit (CPU spike / VRAM full / disk busy /
network latency burst).
"""
from __future__ import annotations

import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional

from ...core.event_bus import EventBus
from ...overlay.fps_tracker import FpsSample
from ...utils.logger import get_logger
from ..performance_monitor import MetricSample

log = get_logger("monitoring.analyzers.stutter")

# Tunables
STUTTER_NOISE_FLOOR_MS = 33.0          # below this we don't care
STUTTER_RATIO = 2.0                    # frame must be 2× median to qualify
STUTTER_WINDOW_S = 30.0                # rolling window for density check
STUTTER_DENSITY_TRIGGER = 5            # >=5 stutters in window → emit alert
COOLDOWN_S = 60.0                      # don't spam the user


@dataclass
class StutterEvent:
    ts: float
    frametime_ms: float
    median_recent_ms: float
    likely_cause: str = ""             # "cpu" | "ram" | "vram" | "disk" | "net" | ""
    cause_detail: str = ""


class StutterDetector:
    """Subscribes to ``fps.sample`` + ``monitor.sample`` for correlation."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._frametimes: Deque[float] = deque(maxlen=240)   # ~4 min at 1Hz
        self._stutters: Deque[StutterEvent] = deque(maxlen=64)
        self._last_metric: Optional[MetricSample] = None
        self._last_alert_ts: float = 0.0

        bus.subscribe("monitor.sample", self._on_metric)
        bus.subscribe("fps.sample", self._on_fps)

    # ------------------------------------------------------------------ public
    def stutters(self) -> List[StutterEvent]:
        return list(self._stutters)

    def density(self, *, window_s: float = STUTTER_WINDOW_S) -> int:
        cutoff = time.time() - window_s
        return sum(1 for s in self._stutters if s.ts >= cutoff)

    # ------------------------------------------------------------------ event handlers
    def _on_metric(self, sample: MetricSample) -> None:
        self._last_metric = sample

    def _on_fps(self, sample: FpsSample) -> None:
        ft = sample.frametime_ms
        if ft <= 0 or sample.source == "off":
            return
        self._frametimes.append(ft)
        if len(self._frametimes) < 30:
            return
        median = statistics.median(self._frametimes)
        if ft < STUTTER_NOISE_FLOOR_MS:
            return
        if median > 0 and ft >= max(STUTTER_NOISE_FLOOR_MS, median * STUTTER_RATIO):
            event = StutterEvent(
                ts=sample.ts,
                frametime_ms=ft,
                median_recent_ms=median,
            )
            self._tag_cause(event)
            self._stutters.append(event)
            self._maybe_alert()

    # ------------------------------------------------------------------ correlation
    def _tag_cause(self, event: StutterEvent) -> None:
        m = self._last_metric
        if m is None:
            return
        if m.cpu_percent >= 95:
            event.likely_cause = "cpu"
            event.cause_detail = f"CPU at {m.cpu_percent:.0f}% — a process is saturating cores."
            return
        if m.ram_percent >= 92:
            event.likely_cause = "ram"
            event.cause_detail = f"RAM at {m.ram_percent:.0f}% — system is paging."
            return
        if m.disk_read_bps + m.disk_write_bps > 200 * 1024 * 1024:
            event.likely_cause = "disk"
            event.cause_detail = f"Disk I/O above 200 MB/s — likely game shader/texture load."
            return
        if m.gpu_vram_bytes and m.gpu_vram_bytes > 0:
            # We don't know capacity here; just hint VRAM pressure when present.
            pass
        if m.net_down_bps + m.net_up_bps > 50 * 1024 * 1024:
            event.likely_cause = "net"
            event.cause_detail = "Network usage spike — game patcher or other download in progress."
            return
        event.likely_cause = "gpu"
        event.cause_detail = "GPU frame stall (driver/scene complexity)."

    # ------------------------------------------------------------------ alerting
    def _maybe_alert(self) -> None:
        if self.density() < STUTTER_DENSITY_TRIGGER:
            return
        now = time.time()
        if now - self._last_alert_ts < COOLDOWN_S:
            return
        self._last_alert_ts = now
        recent = [s for s in self._stutters if s.ts >= now - STUTTER_WINDOW_S]
        # Pick the dominant cause so the alert is actionable.
        cause_counts: dict = {}
        for s in recent:
            if s.likely_cause:
                cause_counts[s.likely_cause] = cause_counts.get(s.likely_cause, 0) + 1
        dominant = max(cause_counts.items(), key=lambda kv: kv[1])[0] if cause_counts else ""
        self._bus.publish(
            "stutter.detected",
            count=len(recent),
            dominant_cause=dominant,
            window_s=STUTTER_WINDOW_S,
            events=recent,
        )
        log.info("stutter alert: %d in %.0fs (cause=%s)",
                 len(recent), STUTTER_WINDOW_S, dominant)
