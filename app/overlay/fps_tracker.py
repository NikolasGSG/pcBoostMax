"""Frame-rate tracker.

True per-game FPS on Windows requires either DLL-injection (RTSS / MSI
Afterburner) or an ETW consumer (PresentMon). We ship a tiny PresentMon
integration that activates if the binary is found in PATH or alongside our
exe — otherwise we fall back to a **GPU-activity proxy** derived from the
Windows GPU Engine counter. The proxy isn't a true FPS but correlates with
frame workload, so the HUD always has something to display.
"""
from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Optional

from ..utils.logger import get_logger

log = get_logger("overlay.fps")


@dataclass
class FpsSample:
    ts: float
    fps: float
    frametime_ms: float
    source: str        # "presentmon" | "proxy" | "off"
    target_pid: Optional[int] = None


class FpsTracker:
    """Runs a background thread, exposes the latest FpsSample + a short window."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: Deque[FpsSample] = deque(maxlen=120)   # ~2 minutes at 1Hz
        self._last: Optional[FpsSample] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._presentmon_path: Optional[str] = self._find_presentmon()
        self._target_pid: Optional[int] = None
        self._proc: Optional[subprocess.Popen] = None

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="gb-fps", daemon=True)
        self._thread.start()
        log.info("FPS tracker started (source=%s)",
                 "presentmon" if self._presentmon_path else "proxy")

    def stop(self) -> None:
        self._stop.set()
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None

    # ------------------------------------------------------------------ data
    @property
    def source(self) -> str:
        return "presentmon" if self._presentmon_path else "proxy"

    def set_target_pid(self, pid: Optional[int]) -> None:
        """Limit FPS readings to a specific PID (e.g. current foreground game)."""
        self._target_pid = pid

    def latest(self) -> Optional[FpsSample]:
        with self._lock:
            return self._last

    def history(self) -> list[FpsSample]:
        """Snapshot of the rolling FPS sample window."""
        with self._lock:
            return list(self._history)

    def percentile_stats(self, window_seconds: float = 60.0) -> dict:
        """Compute avg, 1% low, 0.1% low across the last N seconds.

        Returns a dict with keys ``avg``, ``low_1pct``, ``low_0p1pct``,
        ``min``, ``max``, ``count``. Empty / insufficient history returns
        zeros so the UI can render a "no data" state without branching.
        """
        cutoff = time.time() - window_seconds
        with self._lock:
            window = [s.fps for s in self._history if s.ts >= cutoff and s.fps > 0]
        if not window:
            return {"avg": 0.0, "low_1pct": 0.0, "low_0p1pct": 0.0,
                    "min": 0.0, "max": 0.0, "count": 0}
        window.sort()
        n = len(window)
        idx_1 = max(0, int(n * 0.01) - 1)
        idx_01 = max(0, int(n * 0.001) - 1)
        return {
            "avg": sum(window) / n,
            "low_1pct": window[idx_1],
            "low_0p1pct": window[idx_01],
            "min": window[0],
            "max": window[-1],
            "count": n,
        }

    def push_proxy(self, gpu_percent: float) -> None:
        """Feed a GPU-activity sample so the proxy has a signal even when no
        game is running."""
        if self._presentmon_path:
            return
        # Heuristic: we assume 100 Hz as ceiling; scale GPU activity → pseudo-fps
        # This is NOT a true frame rate; it is an activity indicator that
        # matches the user's visual expectation (higher GPU = more frames).
        pseudo = max(0.0, min(240.0, gpu_percent * 2.4))
        with self._lock:
            sample = FpsSample(
                ts=time.time(),
                fps=pseudo,
                frametime_ms=0.0 if pseudo <= 0 else 1000.0 / pseudo,
                source="proxy",
                target_pid=self._target_pid,
            )
            self._history.append(sample)
            self._last = sample

    # ------------------------------------------------------------------ internals
    def _find_presentmon(self) -> Optional[str]:
        # 1. Shipped next to our exe? 2. On PATH? 3. Common install dirs?
        candidates: list[Path] = []
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).with_name("PresentMon.exe"))
            candidates.append(Path(sys.executable).parent / "tools" / "PresentMon.exe")
        here = Path(__file__).resolve().parent.parent.parent
        candidates.append(here / "tools" / "PresentMon.exe")
        candidates.append(here / "PresentMon.exe")

        which = shutil.which("PresentMon")
        if which:
            candidates.append(Path(which))
        which2 = shutil.which("PresentMon.exe")
        if which2:
            candidates.append(Path(which2))

        for c in candidates:
            if c and c.exists():
                log.info("PresentMon found at %s", c)
                return str(c)
        return None

    def _run(self) -> None:
        if self._presentmon_path:
            try:
                self._run_presentmon()
                return
            except Exception:
                log.exception("PresentMon failed; falling back to proxy.")
                self._presentmon_path = None
        # Proxy loop — nothing to do but idle; samples arrive via push_proxy()
        while not self._stop.is_set():
            self._stop.wait(0.5)

    def _run_presentmon(self) -> None:
        """Spawn PresentMon with CSV to stdout and parse in real time."""
        assert self._presentmon_path
        # --output_stdout: CSV on stdout; --no_csv keeps CSV but no file;
        # -stop_existing_session avoids conflicts.
        from ..utils.subprocess_helper import popen as _popen_silent
        cmd = [self._presentmon_path, "-output_stdout", "-stop_existing_session"]
        self._proc = _popen_silent(cmd)
        reader = csv.reader(self._proc.stdout)
        header: list[str] = []
        for row in reader:
            if self._stop.is_set():
                break
            if not row:
                continue
            if not header:
                header = row
                continue
            try:
                data = dict(zip(header, row))
                pid_str = data.get("ProcessID", "")
                pid = int(pid_str) if pid_str.isdigit() else None
                if self._target_pid and pid != self._target_pid:
                    continue
                fps_str = data.get("msBetweenPresents", "")
                ms = float(fps_str) if fps_str else 0.0
                if ms <= 0:
                    continue
                fps = 1000.0 / ms
            except Exception:
                continue
            with self._lock:
                sample = FpsSample(
                    ts=time.time(), fps=fps, frametime_ms=ms,
                    source="presentmon", target_pid=pid,
                )
                self._history.append(sample)
                self._last = sample
