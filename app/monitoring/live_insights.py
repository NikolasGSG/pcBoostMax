"""Live Insights — translates rolling telemetry into actionable suggestions.

This sits one level above :class:`PerformanceMonitor`: the monitor gives
us *numbers*, this module turns those numbers into *advice* the user can
act on (e.g. "Your CPU has been pegged at >90% for the last 20s — consider
activating Game Mode" or "System RAM is 92% full — close background apps").

Design:

* Stateless evaluators. Each :class:`InsightRule` is a small pure
  function-like class with ``evaluate(window) -> Optional[Insight]``.
* A single :class:`LiveInsightEngine` subscribes to ``monitor.sample`` on
  the event bus, keeps a rolling window, and on every sample re-runs all
  evaluators, emitting ``insights.updated`` with the current set.
* The UI binds to ``insights.updated`` and renders the list.

The engine is completely read-only — it never modifies system state. It
only surfaces suggestions; the user still decides whether to act.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Sequence

from ..core.event_bus import EventBus
from ..utils.logger import get_logger
from .performance_monitor import MetricSample

log = get_logger("monitoring.insights")


# -------------------------------------------------------------------- model

# Severity tiers drive the card colour on the Dashboard.
SEVERITY_INFO = "info"       # general tip
SEVERITY_WATCH = "watch"     # mild pressure, worth noting
SEVERITY_WARN = "warn"       # user should consider acting
SEVERITY_CRIT = "critical"   # sustained problem

SEVERITY_ORDER = {SEVERITY_INFO: 0, SEVERITY_WATCH: 1, SEVERITY_WARN: 2, SEVERITY_CRIT: 3}


@dataclass(frozen=True)
class Insight:
    """A single live-adaptive suggestion."""

    id: str                        # stable key — lets the UI animate in/out
    severity: str                  # one of SEVERITY_*
    headline: str                  # short, bold line
    body: str                      # one-sentence elaboration
    action: str = ""               # optional, e.g. "Activate Game Mode"
    action_target: str = ""        # one of: "game_mode" | "optimize" | "cleanup" | ""
    evidence: dict = field(default_factory=dict)


# -------------------------------------------------------------------- evaluators

# Sliding-window helpers -----------------------------------------------------

def _avg(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _recent_window(samples: Sequence[MetricSample], seconds: float) -> List[MetricSample]:
    if not samples:
        return []
    cutoff = time.time() - seconds
    return [s for s in samples if s.ts >= cutoff]


# Individual evaluators ------------------------------------------------------

class InsightRule:
    """Subclass to add a new live rule."""

    id: str = ""

    def evaluate(self, window: List[MetricSample]) -> Optional[Insight]:  # pragma: no cover - abstract
        raise NotImplementedError


class SustainedCpuPressure(InsightRule):
    """Mean CPU ≥ 85% for >= 15s triggers a warn; ≥ 95% for 30s is critical."""

    id = "cpu.sustained_pressure"

    def evaluate(self, window: List[MetricSample]) -> Optional[Insight]:
        w15 = _recent_window(window, 15)
        if len(w15) < 6:
            return None
        cpu15 = _avg(s.cpu_percent for s in w15)
        w30 = _recent_window(window, 30)
        cpu30 = _avg(s.cpu_percent for s in w30) if len(w30) >= 12 else 0.0

        if cpu30 >= 95:
            return Insight(
                id=self.id, severity=SEVERITY_CRIT,
                headline="CPU is fully saturated",
                body=(
                    f"Averaging {cpu30:.0f}% over the last 30 seconds. Frame-time "
                    "spikes are very likely until a core frees up."
                ),
                action="Activate Game Mode", action_target="game_mode",
                evidence={"cpu_30s_avg": round(cpu30, 1)},
            )
        if cpu15 >= 85:
            return Insight(
                id=self.id, severity=SEVERITY_WARN,
                headline="CPU under heavy load",
                body=(
                    f"{cpu15:.0f}% sustained over the last 15 seconds. Closing "
                    "background apps or applying the Recommended plan may help."
                ),
                action="Open Optimize", action_target="optimize",
                evidence={"cpu_15s_avg": round(cpu15, 1)},
            )
        return None


class RamPressure(InsightRule):
    """RAM >= 88% for 20s is a warn; >= 95% is critical (paging risk)."""

    id = "ram.pressure"

    def evaluate(self, window: List[MetricSample]) -> Optional[Insight]:
        w = _recent_window(window, 20)
        if len(w) < 6:
            return None
        ram = _avg(s.ram_percent for s in w)
        if ram >= 95:
            return Insight(
                id=self.id, severity=SEVERITY_CRIT,
                headline="Memory is almost full",
                body=(
                    f"RAM at {ram:.0f}% — Windows may start swapping to disk, "
                    "which causes hitches mid-game."
                ),
                action="Close heavy apps", action_target="optimize",
                evidence={"ram_20s_avg": round(ram, 1)},
            )
        if ram >= 88:
            return Insight(
                id=self.id, severity=SEVERITY_WARN,
                headline="Memory getting tight",
                body=(
                    f"RAM at {ram:.0f}%. Consider closing a browser tab or two "
                    "before launching a demanding title."
                ),
                action="Open Optimize", action_target="optimize",
                evidence={"ram_20s_avg": round(ram, 1)},
            )
        return None


class DiskChurn(InsightRule):
    """Sustained disk I/O that tends to micro-stutter gameplay."""

    id = "disk.churn"
    _THRESHOLD_MBPS = 40  # total read+write

    def evaluate(self, window: List[MetricSample]) -> Optional[Insight]:
        w = _recent_window(window, 10)
        if len(w) < 6:
            return None
        mbps = _avg((s.disk_read_bps + s.disk_write_bps) for s in w) / (1024 * 1024)
        if mbps < self._THRESHOLD_MBPS:
            return None
        severity = SEVERITY_WARN if mbps < 120 else SEVERITY_CRIT
        return Insight(
            id=self.id, severity=severity,
            headline="Heavy disk activity",
            body=(
                f"Disk reading/writing at {mbps:.0f} MB/s on average. "
                "Something (Search Indexer, Defender scan, Windows Update?) "
                "is competing with your games for I/O."
            ),
            action="Open Optimize", action_target="optimize",
            evidence={"mbps_10s_avg": round(mbps, 1)},
        )


class GpuIdleWhileFullscreen(InsightRule):
    """GPU < 20% over 10s with >50% CPU hints at a CPU-bound fullscreen app."""

    id = "gpu.cpu_bound"

    def evaluate(self, window: List[MetricSample]) -> Optional[Insight]:
        w = _recent_window(window, 10)
        if len(w) < 6:
            return None
        gpu = _avg(s.gpu_percent for s in w)
        cpu = _avg(s.cpu_percent for s in w)
        if gpu == 0.0:
            return None  # GPU telemetry unavailable
        if gpu < 20 and cpu > 55:
            return Insight(
                id=self.id, severity=SEVERITY_WATCH,
                headline="GPU sitting idle",
                body=(
                    f"CPU at {cpu:.0f}% while GPU stays near {gpu:.0f}%. "
                    "Either the current app is CPU-bound or v-sync is clamping "
                    "the framerate. Disabling fullscreen optimizations often helps."
                ),
                action="Open Optimize", action_target="optimize",
                evidence={"cpu": round(cpu, 1), "gpu": round(gpu, 1)},
            )
        return None


class HealthyIdle(InsightRule):
    """Positive reinforcement — surfaces when the machine is calm."""

    id = "system.healthy_idle"

    def evaluate(self, window: List[MetricSample]) -> Optional[Insight]:
        w = _recent_window(window, 20)
        if len(w) < 10:
            return None
        cpu = _avg(s.cpu_percent for s in w)
        ram = _avg(s.ram_percent for s in w)
        disk_mbps = _avg((s.disk_read_bps + s.disk_write_bps) for s in w) / (1024 * 1024)
        if cpu < 25 and ram < 70 and disk_mbps < 10:
            return Insight(
                id=self.id, severity=SEVERITY_INFO,
                headline="System is running cool",
                body=(
                    f"CPU {cpu:.0f}%, RAM {ram:.0f}%, disk quiet. "
                    "This is a great moment to apply an optimization plan — "
                    "no heavy processes in the way."
                ),
                action="Open Optimize", action_target="optimize",
                evidence={"cpu": round(cpu, 1), "ram": round(ram, 1)},
            )
        return None


# -------------------------------------------------------------------- engine

# Default rules. Order is evaluation order and also tiebreak order for
# severity-equal insights.
DEFAULT_RULES: tuple[InsightRule, ...] = (
    SustainedCpuPressure(),
    RamPressure(),
    DiskChurn(),
    GpuIdleWhileFullscreen(),
    HealthyIdle(),
)


class LiveInsightEngine:
    """Subscribes to ``monitor.sample`` and publishes ``insights.updated``."""

    EVENT_TOPIC = "insights.updated"

    def __init__(
        self,
        bus: EventBus,
        *,
        rules: Iterable[InsightRule] = DEFAULT_RULES,
        evaluate_every_n_samples: int = 2,
    ) -> None:
        self.bus = bus
        self.rules: list[InsightRule] = list(rules)
        self._window: list[MetricSample] = []
        self._window_capacity = 600  # ~5 minutes at 2 Hz
        self._last_results: list[Insight] = []
        self._sample_counter = 0
        self._evaluate_every = max(1, evaluate_every_n_samples)
        bus.subscribe("monitor.sample", self._on_sample)

    # ------------------------------------------------------------------ api
    def latest(self) -> list[Insight]:
        """Thread-safe snapshot of the most recent set of insights."""
        return list(self._last_results)

    # ------------------------------------------------------------------ internals
    def _on_sample(self, sample: MetricSample) -> None:
        try:
            self._window.append(sample)
            if len(self._window) > self._window_capacity:
                # drop oldest in O(1) amortised
                del self._window[: len(self._window) - self._window_capacity]
            self._sample_counter += 1
            if self._sample_counter % self._evaluate_every != 0:
                return
            self._recompute()
        except Exception:
            log.exception("Insight engine sample processing failed")

    def _recompute(self) -> None:
        results: list[Insight] = []
        for rule in self.rules:
            try:
                out = rule.evaluate(self._window)
            except Exception:
                log.exception("Insight rule %s crashed", rule.id)
                continue
            if out is not None:
                results.append(out)
        # Stable ordering: severity DESC then rule declaration order.
        results.sort(
            key=lambda i: (-SEVERITY_ORDER.get(i.severity, 0),
                            [r.id for r in self.rules].index(i.id)),
        )
        # Drop HealthyIdle if any higher-severity insight is active.
        if any(i.severity in (SEVERITY_WARN, SEVERITY_CRIT) for i in results):
            results = [i for i in results if i.id != "system.healthy_idle"]

        self._last_results = results
        self.bus.publish(self.EVENT_TOPIC, results)
