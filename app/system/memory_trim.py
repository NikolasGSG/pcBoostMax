"""Memory Trim service — frees up RAM by purging the standby list and
trimming working sets of background processes.

Two operations:

* **Trim working sets** — call ``EmptyWorkingSet`` on every non-system,
  non-game process. Always safe and reversible (Windows refills caches
  on demand).
* **Purge standby list** — calls ``NtSetSystemInformation`` with the
  ``SystemMemoryListInformation`` class to flush cold cache pages. Needs
  ``SeProfileSingleProcessPrivilege`` (admin only).

The service is **read-write**, but every action it takes is naturally
reversible by the OS — there is no rollback to perform. It records the
event in ``ActionHistory`` so the user can see "we freed 2.3 GB at 14:02".
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Set

import psutil

from ..core.event_bus import EventBus
from ..safety.action_history import ActionHistory, ActionRecord
from ..utils.admin_check import is_admin
from ..utils.logger import get_logger

log = get_logger("system.memory_trim")

# ---- Win32 / NT constants and helpers ---------------------------------
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_SET_QUOTA = 0x0100

_SYSTEM_MEMORY_LIST_INFORMATION = 80
_PURGE_STANDBY_LIST = 4
_PURGE_LOW_PRIORITY_STANDBY_LIST = 5

# Don't try to trim these — kernel/system processes will refuse and waste
# our time.
_PROTECTED = {
    "system idle process", "system", "registry", "memory compression",
    "smss.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe",
    "winlogon.exe", "fontdrvhost.exe", "dwm.exe",
}


@dataclass(frozen=True)
class TrimResult:
    """Snapshot of one trim run."""
    freed_mb: float
    trimmed_processes: int
    standby_purged: bool
    elapsed_ms: float
    requires_admin_for_full: bool   # True when we couldn't purge standby
    available_before_mb: float
    available_after_mb: float


class MemoryTrimService:
    """Manual + scheduled memory-trim operations.

    Listens for ``memory.trim_requested`` on the event bus so any UI bit
    can fire a trim without holding a reference. Publishes
    ``memory.trimmed`` with a :class:`TrimResult` after each run.
    """

    def __init__(self, bus: EventBus, history: Optional[ActionHistory] = None) -> None:
        self._bus = bus
        self._history = history
        self._k32 = ctypes.windll.kernel32 if hasattr(ctypes, "windll") else None
        self._psapi = ctypes.windll.psapi if hasattr(ctypes, "windll") else None
        self._ntdll = ctypes.windll.ntdll if hasattr(ctypes, "windll") else None
        self._bus.subscribe("memory.trim_requested", self._on_request)

    # ------------------------------------------------------------------ public
    def trim(self, *, purge_standby: bool = True, exclude_pids: Optional[Iterable[int]] = None) -> TrimResult:
        """Run a trim cycle synchronously and return the result."""
        start = time.perf_counter()
        before = psutil.virtual_memory().available / (1024 * 1024)

        skip: Set[int] = set(exclude_pids or ())
        skip.add(0)
        trimmed = self._trim_working_sets(skip=skip)
        purged = False
        if purge_standby and is_admin():
            purged = self._purge_standby_list()

        # Give Windows a tick to settle.
        time.sleep(0.05)
        after = psutil.virtual_memory().available / (1024 * 1024)
        freed = max(0.0, after - before)
        elapsed_ms = (time.perf_counter() - start) * 1000

        result = TrimResult(
            freed_mb=freed,
            trimmed_processes=trimmed,
            standby_purged=purged,
            elapsed_ms=elapsed_ms,
            requires_admin_for_full=not is_admin() and purge_standby,
            available_before_mb=before,
            available_after_mb=after,
        )
        self._record(result)
        self._bus.publish("memory.trimmed", result)
        log.info(
            "memory trim: freed=%.0f MB, trimmed=%d procs, standby=%s in %.0f ms",
            freed, trimmed, purged, elapsed_ms,
        )
        return result

    # ------------------------------------------------------------------ internals
    def _trim_working_sets(self, *, skip: Set[int]) -> int:
        """Call ``EmptyWorkingSet`` on every accessible process."""
        if self._psapi is None or self._k32 is None:
            return 0
        EmptyWorkingSet = self._psapi.EmptyWorkingSet
        EmptyWorkingSet.argtypes = [wt.HANDLE]
        EmptyWorkingSet.restype = wt.BOOL
        OpenProcess = self._k32.OpenProcess
        OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        OpenProcess.restype = wt.HANDLE
        CloseHandle = self._k32.CloseHandle

        count = 0
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pid = proc.info["pid"]
                if pid in skip:
                    continue
                name = (proc.info.get("name") or "").lower()
                if name in _PROTECTED:
                    continue
                handle = OpenProcess(
                    PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SET_QUOTA, False, pid
                )
                if not handle:
                    continue
                try:
                    if EmptyWorkingSet(handle):
                        count += 1
                finally:
                    CloseHandle(handle)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception:
                continue
        return count

    def _purge_standby_list(self) -> bool:
        """Flush the standby list. Requires admin + SeProfileSingleProcessPrivilege."""
        if self._ntdll is None:
            return False
        try:
            cmd = ctypes.c_int(_PURGE_STANDBY_LIST)
            status = self._ntdll.NtSetSystemInformation(
                _SYSTEM_MEMORY_LIST_INFORMATION, ctypes.byref(cmd), ctypes.sizeof(cmd)
            )
            if status != 0:
                log.debug("NtSetSystemInformation -> 0x%x", status & 0xFFFFFFFF)
                return False
            return True
        except Exception:
            log.debug("standby purge failed", exc_info=True)
            return False

    def _record(self, result: TrimResult) -> None:
        if self._history is None:
            return
        try:
            self._history.add(ActionRecord.new(
                category="memory",
                action="trim",
                summary=f"Freed {result.freed_mb:.0f} MB across {result.trimmed_processes} processes",
                risk="safe",
                reversible=False,   # Windows reclaims caches as needed; nothing to undo
                payload={
                    "freed_mb": round(result.freed_mb, 1),
                    "trimmed": result.trimmed_processes,
                    "standby_purged": result.standby_purged,
                    "elapsed_ms": round(result.elapsed_ms, 1),
                },
            ))
        except Exception:
            log.exception("failed to record memory.trim in history")

    def _on_request(self, *, purge_standby: bool = True, exclude_pids: Optional[List[int]] = None) -> None:
        try:
            self.trim(purge_standby=purge_standby, exclude_pids=exclude_pids)
        except Exception:
            log.exception("memory.trim_requested handler failed")
