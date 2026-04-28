"""Track the foreground window and expose basic stats about its owning process.

Pure stdlib + psutil + ctypes — no external deps. Keeps a tiny rolling
cache so we don't hammer the Windows API.
"""
from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Optional

import psutil

from ..utils.logger import get_logger

log = get_logger("overlay.foreground")


@dataclass
class ForegroundApp:
    pid: int
    exe_name: str           # just the filename, e.g. "Cyberpunk2077.exe"
    window_title: str       # text of the foreground window
    cpu_percent: float      # 0..100 · 1 CPU == 100% (not divided by cores)
    ram_mb: float           # working set, MB
    is_fullscreen: bool     # True if covers the primary monitor


class ForegroundTracker:
    """Polls the foreground window and caches per-process stats."""

    def __init__(self) -> None:
        self._cache: dict[int, psutil.Process] = {}
        self._lock = threading.Lock()
        self._last: Optional[ForegroundApp] = None
        self._last_ts: float = 0.0
        self._available = sys.platform == "win32"

    # ------------------------------------------------------------------ public
    def sample(self) -> Optional[ForegroundApp]:
        if not self._available:
            return None
        now = time.time()
        # Don't poll faster than ~4 Hz regardless of caller
        if self._last and (now - self._last_ts) < 0.25:
            return self._last
        try:
            app = self._read()
        except Exception:
            log.debug("foreground read failed", exc_info=True)
            app = None
        self._last = app
        self._last_ts = now
        return app

    # ------------------------------------------------------------------ windows internals
    def _read(self) -> Optional[ForegroundApp]:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        GetForegroundWindow = user32.GetForegroundWindow
        GetWindowThreadProcessId = user32.GetWindowThreadProcessId
        GetWindowTextW = user32.GetWindowTextW
        GetWindowTextLengthW = user32.GetWindowTextLengthW
        GetWindowRect = user32.GetWindowRect
        GetSystemMetrics = user32.GetSystemMetrics

        hwnd = GetForegroundWindow()
        if not hwnd:
            return None

        pid = ctypes.c_ulong(0)
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None

        # Window title
        length = GetWindowTextLengthW(hwnd)
        title = ""
        if length:
            buf = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value

        # Rectangle → is it fullscreen?
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
        rect = RECT()
        GetWindowRect(hwnd, ctypes.byref(rect))
        screen_w = GetSystemMetrics(0)
        screen_h = GetSystemMetrics(1)
        is_fs = (rect.left <= 0 and rect.top <= 0 and
                 (rect.right - rect.left) >= screen_w and
                 (rect.bottom - rect.top) >= screen_h)

        # Process stats
        proc = self._cache.get(pid.value)
        if proc is None or not proc.is_running():
            try:
                proc = psutil.Process(pid.value)
                self._cache[pid.value] = proc
                # Prime the cpu_percent counter
                proc.cpu_percent(interval=None)
            except Exception:
                return None

        try:
            cpu_pct = proc.cpu_percent(interval=None)
        except Exception:
            cpu_pct = 0.0
        try:
            ram_bytes = proc.memory_info().rss
        except Exception:
            ram_bytes = 0
        try:
            exe_name = os.path.basename(proc.exe())
        except Exception:
            try:
                exe_name = proc.name()
            except Exception:
                exe_name = "unknown"

        return ForegroundApp(
            pid=pid.value,
            exe_name=exe_name,
            window_title=title,
            cpu_percent=float(cpu_pct),
            ram_mb=ram_bytes / (1024 * 1024),
            is_fullscreen=is_fs,
        )
