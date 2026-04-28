"""Heuristic bottleneck analyser.

We deliberately avoid exotic claims. Only heuristics that are defensible:
sustained high CPU, memory pressure, disk saturation, very low free space,
very old hardware relative to RAM, etc.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from ..monitoring.performance_monitor import MetricSample
from .hardware_detector import HardwareSnapshot


@dataclass
class Bottleneck:
    component: str      # "CPU" | "RAM" | "DISK" | "SYSTEM"
    severity: str       # "info" | "warn" | "critical"
    headline: str
    detail: str


class BottleneckAnalyzer:
    """Pure function-style analyzer — no state. Feed a window of samples."""

    # thresholds in percent
    CPU_SUSTAINED = 85.0
    RAM_PRESSURE = 85.0
    DISK_PRESSURE = 90.0
    LOW_FREE_PCT = 10.0

    def analyze(
        self,
        hardware: HardwareSnapshot,
        samples: Sequence[MetricSample],
    ) -> List[Bottleneck]:
        findings: List[Bottleneck] = []
        if not samples:
            return findings

        window = samples[-min(30, len(samples)):]  # last ~15 seconds at 2 Hz

        # --------------- CPU ---------------
        cpu_avg = sum(s.cpu_percent for s in window) / len(window)
        if cpu_avg >= self.CPU_SUSTAINED:
            findings.append(Bottleneck(
                component="CPU",
                severity="critical" if cpu_avg > 95 else "warn",
                headline=f"CPU sustained at {cpu_avg:0.0f}%",
                detail=(
                    "Your CPU has been near its limit recently. Games that push CPU "
                    "(sim, strategy, competitive shooters) will see frame drops. "
                    "Closing background apps and enabling Game Mode typically helps."
                ),
            ))

        # --------------- RAM ---------------
        ram_avg = sum(s.ram_percent for s in window) / len(window)
        if ram_avg >= self.RAM_PRESSURE:
            findings.append(Bottleneck(
                component="RAM",
                severity="critical" if ram_avg > 95 else "warn",
                headline=f"RAM usage sustained at {ram_avg:0.0f}%",
                detail=(
                    "High memory pressure causes paging to disk and stutter. Close "
                    "browsers/chat apps before gaming or consider a RAM upgrade."
                ),
            ))

        # --------------- DISK (system drive only) ---------------
        latest = samples[-1]
        if latest.disk_percent >= self.DISK_PRESSURE:
            findings.append(Bottleneck(
                component="DISK",
                severity="warn",
                headline=f"Disk busy at {latest.disk_percent:0.0f}%",
                detail=(
                    "Heavy disk I/O hurts load times and causes hitches. Identify the "
                    "process responsible (Windows Search / Defender scan / cloud sync) "
                    "and pause it during play."
                ),
            ))

        # --------------- Free space ---------------
        sys_disk = next((d for d in hardware.disks if d.mountpoint in ("C:\\", "/")), None)
        if sys_disk and sys_disk.total_bytes:
            free_pct = (sys_disk.free_bytes / sys_disk.total_bytes) * 100
            if free_pct < self.LOW_FREE_PCT:
                findings.append(Bottleneck(
                    component="DISK",
                    severity="warn",
                    headline=f"System drive only {free_pct:0.0f}% free",
                    detail=(
                        "Windows uses the system drive for paging and shader caches. "
                        "Under 10% free space leads to stutter and slow updates. "
                        "Try the Cleanup tab or uninstall unused titles."
                    ),
                ))

        # --------------- RAM amount vs OS ---------------
        ram_gb = hardware.ram.total_bytes / (1024 ** 3) if hardware.ram.total_bytes else 0
        if ram_gb and ram_gb < 8:
            findings.append(Bottleneck(
                component="RAM",
                severity="info",
                headline=f"{ram_gb:0.0f} GB RAM is below modern baseline",
                detail=(
                    "Most modern games recommend 16 GB. Optimization can only go so "
                    "far against a hard capacity ceiling — a RAM upgrade is the most "
                    "impactful change for this system."
                ),
            ))

        # --------------- CPU core count ---------------
        if hardware.cpu.cores_physical and hardware.cpu.cores_physical < 4:
            findings.append(Bottleneck(
                component="CPU",
                severity="info",
                headline=f"{hardware.cpu.cores_physical} physical cores detected",
                detail=(
                    "Fewer than 4 cores is well below the modern baseline. Background "
                    "process reduction matters more on this system than on an 8-core."
                ),
            ))

        return findings
