"""GPU utilisation / VRAM via Windows performance counters.

We query ``\\GPU Engine(*)\\Utilization Percentage`` which every modern
Windows build maintains automatically for all GPUs. No NVML / ADL / vendor
SDKs required.

If the counters aren't available (non-Windows, ancient Win10 build, etc.) we
silently fall back to zero so the rest of the app works unmodified.
"""
from __future__ import annotations

import sys
import threading
from typing import Optional

from ..utils.logger import get_logger

log = get_logger("monitoring.gpu")


class GpuMonitor:
    """Lazy, thread-safe wrapper around win32pdh counters."""

    def __init__(self) -> None:
        self._query = None
        self._engine_counters: list = []
        self._mem_counter = None
        self._lock = threading.RLock()
        self._initialized = False
        self._failed = False
        self._last_utilization = 0.0
        self._last_vram_used = 0

    # ------------------------------------------------------------------ lifecycle
    def _ensure_init(self) -> bool:
        if self._initialized:
            return True
        if self._failed:
            return False
        if sys.platform != "win32":
            self._failed = True
            return False

        try:
            import win32pdh  # type: ignore

            self._win32pdh = win32pdh
            with self._lock:
                self._query = win32pdh.OpenQuery()

                # Enumerate every GPU engine instance and add its utilisation counter.
                _, instances = win32pdh.EnumObjectItems(
                    None, None, "GPU Engine", win32pdh.PERF_DETAIL_WIZARD
                )
                seen = set()
                for instance in instances:
                    if instance in seen:
                        continue
                    seen.add(instance)
                    path = win32pdh.MakeCounterPath(
                        (None, "GPU Engine", instance, None, 0, "Utilization Percentage")
                    )
                    try:
                        handle = win32pdh.AddCounter(self._query, path)
                        self._engine_counters.append(handle)
                    except Exception:  # pragma: no cover - counter may vanish
                        pass

                # Total VRAM in use — enumerate every process and we'll sum per sample.
                try:
                    _, mem_instances = win32pdh.EnumObjectItems(
                        None, None, "GPU Process Memory", win32pdh.PERF_DETAIL_WIZARD
                    )
                    self._mem_counters: list = []
                    seen_mem = set()
                    for instance in mem_instances:
                        if instance in seen_mem:
                            continue
                        seen_mem.add(instance)
                        path = win32pdh.MakeCounterPath(
                            (None, "GPU Process Memory", instance, None, 0, "Dedicated Usage")
                        )
                        try:
                            h = win32pdh.AddCounter(self._query, path)
                            self._mem_counters.append(h)
                        except Exception:
                            pass
                    self._mem_counter = bool(self._mem_counters)
                except Exception:
                    self._mem_counter = None
                    self._mem_counters = []

                # First collect primes the counters; second gives real values.
                win32pdh.CollectQueryData(self._query)
                self._initialized = True
            return True
        except Exception as exc:
            log.debug("GPU monitor unavailable: %s", exc)
            self._failed = True
            return False

    # ------------------------------------------------------------------ sampling
    def sample(self) -> tuple[float, int]:
        """Return (utilisation_percent, vram_bytes_used). Returns cached values on failure."""
        if not self._ensure_init():
            return 0.0, 0

        try:
            with self._lock:
                self._win32pdh.CollectQueryData(self._query)
                # GPU Engine utilisation is the SUM across all engines (3D + copy + compute…)
                # but we cap at 100 to match the reading shown by Task Manager.
                total = 0.0
                for c in self._engine_counters:
                    try:
                        _t, val = self._win32pdh.GetFormattedCounterValue(
                            c, self._win32pdh.PDH_FMT_DOUBLE
                        )
                        total += float(val)
                    except Exception:
                        pass
                self._last_utilization = min(100.0, total)

                if self._mem_counters:
                    vram_total = 0
                    for h in self._mem_counters:
                        try:
                            _t, val = self._win32pdh.GetFormattedCounterValue(
                                h, self._win32pdh.PDH_FMT_LARGE
                            )
                            vram_total += int(val)
                        except Exception:
                            pass
                    self._last_vram_used = vram_total
        except Exception:
            log.debug("GPU counter sample failed", exc_info=True)

        return self._last_utilization, self._last_vram_used

    def close(self) -> None:
        if not self._initialized:
            return
        try:
            with self._lock:
                self._win32pdh.CloseQuery(self._query)
        except Exception:
            pass
        self._initialized = False
