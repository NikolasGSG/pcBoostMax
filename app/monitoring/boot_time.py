"""Boot Time Benchmark — track how long the user's PC takes to boot.

Reads Windows' "BootEventCollector" entries from the Diagnostics-
Performance event log (event id 100). Each entry has a
``BootMainPathTime`` and ``BootPostBootTime`` (in milliseconds).

We also fall back to ``LastBootUpTime`` from WMI/psutil if the event log
is unreadable (admin-restricted or wiped).

Persistence: ``stats/boot_times.jsonl`` — one JSON line per boot.
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

import psutil

from ..utils.logger import get_logger
from ..utils.paths import STATS_DIR, ensure_app_dirs

log = get_logger("monitoring.boot_time")

_FILENAME = "boot_times.jsonl"


@dataclass
class BootRecord:
    """One observed boot event."""
    ts: float                    # unix ts of the boot
    main_path_ms: int            # kernel + driver init (typical 5-20s)
    post_boot_ms: int            # services + autostart (typical 10-60s)
    total_ms: int                # main_path + post_boot
    source: str = "event_log"    # "event_log" | "wmi" | "psutil"


class BootTimeService:
    """Reads + persists boot metrics. Cheap; just reads on demand."""

    def __init__(self, *, path: Optional[Path] = None) -> None:
        ensure_app_dirs()
        self._path = path or (STATS_DIR / _FILENAME)
        self._records: List[BootRecord] = self._load()

    # ------------------------------------------------------------------ public
    def latest(self) -> Optional[BootRecord]:
        return self._records[-1] if self._records else None

    def history(self, limit: int = 30) -> List[BootRecord]:
        return list(self._records[-limit:])

    def average_total_ms(self, *, last: int = 7) -> Optional[float]:
        recent = self._records[-last:]
        if not recent:
            return None
        return sum(r.total_ms for r in recent) / len(recent)

    def delta_vs_baseline(self) -> Optional[float]:
        """Returns delta (ms) of latest vs avg of the prior 7 boots.
        Negative = faster than baseline."""
        if len(self._records) < 2:
            return None
        latest = self._records[-1]
        baseline = self._records[-8:-1]
        if not baseline:
            return None
        avg = sum(r.total_ms for r in baseline) / len(baseline)
        return latest.total_ms - avg

    def refresh(self) -> Optional[BootRecord]:
        """Look up the latest boot from Windows; persist if new."""
        rec = self._read_latest_boot()
        if rec is None:
            return None
        # Skip if we've already recorded this exact boot
        if self._records and abs(self._records[-1].ts - rec.ts) < 30:
            return self._records[-1]
        self._records.append(rec)
        self._append(rec)
        return rec

    # ------------------------------------------------------------------ readers
    def _read_latest_boot(self) -> Optional[BootRecord]:
        # 1. Try the Windows Event Log via PowerShell. The Diagnostics-
        # Performance log id 100 carries main-path + post-boot times.
        rec = self._read_via_powershell()
        if rec is not None:
            return rec
        # 2. Fallback — psutil/boot_time gives us the boot timestamp; we
        # don't have phase splits but we can record uptime as total.
        try:
            boot_ts = psutil.boot_time()
            uptime_now = time.time() - boot_ts
            return BootRecord(
                ts=boot_ts,
                main_path_ms=0,
                post_boot_ms=0,
                total_ms=int(uptime_now * 1000),
                source="psutil",
            )
        except Exception:
            log.debug("psutil boot_time fallback failed", exc_info=True)
            return None

    def _read_via_powershell(self) -> Optional[BootRecord]:
        if not self._is_windows():
            return None
        ps = (
            "Get-WinEvent -ProviderName Microsoft-Windows-Diagnostics-Performance"
            " -MaxEvents 1 -FilterXPath \"*[System[(EventID=100)]]\""
            " -ErrorAction Stop | Select-Object @{N='ts';E={$_.TimeCreated.ToFileTime()}},"
            " @{N='main';E={$_.Properties[7].Value}},"
            " @{N='post';E={$_.Properties[8].Value}} | ConvertTo-Json -Compress"
        )
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True, text=True, timeout=8, check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return None
        if out.returncode != 0 or not out.stdout.strip():
            return None
        try:
            data = json.loads(out.stdout)
        except json.JSONDecodeError:
            return None
        try:
            # ts is a Windows file time (100ns intervals since 1601-01-01)
            file_time = int(data["ts"])
            unix_ts = (file_time - 116444736000000000) / 10_000_000
            main = int(data["main"]) if data.get("main") is not None else 0
            post = int(data["post"]) if data.get("post") is not None else 0
            return BootRecord(
                ts=unix_ts,
                main_path_ms=main,
                post_boot_ms=post,
                total_ms=main + post,
                source="event_log",
            )
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _is_windows() -> bool:
        import sys
        return sys.platform == "win32"

    # ------------------------------------------------------------------ io
    def _load(self) -> List[BootRecord]:
        if not self._path.exists():
            return []
        recs: List[BootRecord] = []
        try:
            for line in self._path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                recs.append(BootRecord(**json.loads(line)))
        except Exception:
            log.exception("Failed to load boot history; starting fresh")
            return []
        return recs

    def _append(self, rec: BootRecord) -> None:
        try:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(rec)) + "\n")
        except Exception:
            log.exception("Failed to append boot record")
