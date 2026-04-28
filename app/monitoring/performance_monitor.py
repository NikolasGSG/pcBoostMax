"""Live performance sampler (CPU, RAM, Disk I/O, network).

Runs in its own thread at a fixed cadence so the UI stays silky-smooth.
Every sample is pushed onto the event bus under ``"monitor.sample"``.
The monitor also keeps the last ~N seconds in-memory for graphs.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Iterable, Optional

import psutil

from ..core.constants import MONITOR_HISTORY_SECONDS, MONITOR_SAMPLE_HZ
from ..core.event_bus import EventBus
from ..utils.logger import get_logger
from .gpu_monitor import GpuMonitor

log = get_logger("monitoring.performance")


@dataclass
class MetricSample:
    """One sample of the machine at a moment in time."""

    ts: float
    cpu_percent: float = 0.0
    cpu_freq_mhz: float = 0.0
    ram_percent: float = 0.0
    ram_used_bytes: int = 0
    disk_percent: float = 0.0           # system-drive queue utilisation, approximated
    disk_read_bps: float = 0.0
    disk_write_bps: float = 0.0
    net_up_bps: float = 0.0
    net_down_bps: float = 0.0
    process_count: int = 0
    per_core: tuple[float, ...] = field(default_factory=tuple)
    gpu_percent: float = 0.0
    gpu_vram_bytes: int = 0


class PerformanceMonitor:
    """Background sampler using a daemon thread."""

    def __init__(self, bus: EventBus, sample_hz: int = MONITOR_SAMPLE_HZ) -> None:
        self.bus = bus
        self.sample_hz = max(1, sample_hz)
        self._interval = 1.0 / self.sample_hz
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

        capacity = MONITOR_HISTORY_SECONDS * self.sample_hz
        self._history: Deque[MetricSample] = deque(maxlen=capacity)
        self._lock = threading.RLock()

        # Rolling byte counters (for delta-based rates)
        self._last_disk_bytes: Optional[tuple[int, int]] = None
        self._last_net_bytes: Optional[tuple[int, int]] = None
        self._last_ts: Optional[float] = None

        self._gpu = GpuMonitor()

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="gb-monitor", daemon=True)
        self._thread.start()
        log.info("Performance monitor started @ %d Hz", self.sample_hz)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None
        log.info("Performance monitor stopped")

    # ------------------------------------------------------------------ data
    def history(self) -> list[MetricSample]:
        with self._lock:
            return list(self._history)

    def latest(self) -> Optional[MetricSample]:
        with self._lock:
            return self._history[-1] if self._history else None

    def recent(self, seconds: float) -> Iterable[MetricSample]:
        cutoff = time.time() - seconds
        with self._lock:
            return [s for s in self._history if s.ts >= cutoff]

    # ------------------------------------------------------------------ internals
    def _run(self) -> None:
        # psutil.cpu_percent needs priming so the first reading isn't 0.0
        psutil.cpu_percent(interval=None, percpu=True)
        while not self._stop.is_set():
            try:
                sample = self._collect()
                with self._lock:
                    self._history.append(sample)
                self.bus.publish("monitor.sample", sample)
            except Exception:
                log.exception("Sampling failure")
            self._stop.wait(self._interval)

    def _collect(self) -> MetricSample:
        now = time.time()
        cpu_all = psutil.cpu_percent(interval=None, percpu=True)
        cpu_avg = sum(cpu_all) / len(cpu_all) if cpu_all else 0.0

        cpu_freq = 0.0
        try:
            f = psutil.cpu_freq()
            if f:
                cpu_freq = float(f.current)
        except Exception:
            pass

        vm = psutil.virtual_memory()

        # Disk I/O rates (delta since last sample)
        disk_read_bps = disk_write_bps = 0.0
        try:
            io = psutil.disk_io_counters()
            if io and self._last_disk_bytes and self._last_ts:
                dt = max(now - self._last_ts, 1e-6)
                disk_read_bps = max(0.0, (io.read_bytes - self._last_disk_bytes[0]) / dt)
                disk_write_bps = max(0.0, (io.write_bytes - self._last_disk_bytes[1]) / dt)
            if io:
                self._last_disk_bytes = (io.read_bytes, io.write_bytes)
        except Exception:
            pass

        # Disk "percent busy" is not directly exposed — we use queue length as a proxy
        disk_percent = 0.0
        try:
            io2 = psutil.disk_io_counters(perdisk=False)
            if io2 and hasattr(io2, "busy_time"):
                # ~ rough normalisation; clamp 0..100
                disk_percent = min(100.0, (io2.busy_time % 1000) / 10.0)
        except Exception:
            pass

        # Net rates
        net_up_bps = net_down_bps = 0.0
        try:
            n = psutil.net_io_counters()
            if n and self._last_net_bytes and self._last_ts:
                dt = max(now - self._last_ts, 1e-6)
                net_up_bps = max(0.0, (n.bytes_sent - self._last_net_bytes[0]) / dt)
                net_down_bps = max(0.0, (n.bytes_recv - self._last_net_bytes[1]) / dt)
            if n:
                self._last_net_bytes = (n.bytes_sent, n.bytes_recv)
        except Exception:
            pass

        self._last_ts = now

        gpu_pct, gpu_vram = 0.0, 0
        try:
            gpu_pct, gpu_vram = self._gpu.sample()
        except Exception:
            pass

        return MetricSample(
            ts=now,
            cpu_percent=cpu_avg,
            cpu_freq_mhz=cpu_freq,
            ram_percent=vm.percent,
            ram_used_bytes=vm.used,
            disk_percent=disk_percent,
            disk_read_bps=disk_read_bps,
            disk_write_bps=disk_write_bps,
            net_up_bps=net_up_bps,
            net_down_bps=net_down_bps,
            process_count=len(psutil.pids()),
            per_core=tuple(cpu_all),
            gpu_percent=gpu_pct,
            gpu_vram_bytes=gpu_vram,
        )
