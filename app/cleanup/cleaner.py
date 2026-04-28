"""Cleanup service.

Two-phase: scan → preview → delete. The preview always shows the full list
of target files and aggregate size before anything is removed. The UI
mirrors this flow (Cleanup tab shows a table; user confirms).
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from ..core.config import AppConfig
from ..core.event_bus import EventBus
from ..safety.action_history import ActionHistory, ActionRecord
from ..utils.logger import get_logger

log = get_logger("cleanup.service")


# ----------------------------------------------------------------------- models
@dataclass
class CleanupCategory:
    id: str
    label: str
    description: str
    paths: List[Path] = field(default_factory=list)
    # limit scanning depth to avoid stalling on massive trees
    max_depth: int = 6
    # never delete items modified within this many seconds (protect recent data)
    min_age_seconds: int = 3600


@dataclass
class CleanupFile:
    path: Path
    size: int
    category_id: str
    mtime: float


@dataclass
class CleanupScanResult:
    files: List[CleanupFile] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(f.size for f in self.files)

    def by_category(self) -> Dict[str, List[CleanupFile]]:
        out: Dict[str, List[CleanupFile]] = {}
        for f in self.files:
            out.setdefault(f.category_id, []).append(f)
        return out


@dataclass
class CleanupDeleteResult:
    deleted: int = 0
    bytes_freed: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)


# ----------------------------------------------------------------------- service
class CleanupService:
    """Builds default categories for Windows and exposes scan/delete."""

    def __init__(self, bus: EventBus, history: ActionHistory, config: AppConfig) -> None:
        self.bus = bus
        self.history = history
        self.config = config
        self.categories: List[CleanupCategory] = self._default_categories()

    # ------------------------------------------------------------------ defaults
    @staticmethod
    def _default_categories() -> List[CleanupCategory]:
        temp = os.environ.get("TEMP")
        localappdata = os.environ.get("LOCALAPPDATA")
        sysroot = os.environ.get("SystemRoot", r"C:\Windows")

        user_temp = [Path(temp)] if temp else []
        win_temp = [Path(sysroot) / "Temp"]
        prefetch = [Path(sysroot) / "Prefetch"]
        crash_dumps = []
        if localappdata:
            crash_dumps.append(Path(localappdata) / "CrashDumps")

        return [
            CleanupCategory(
                id="user_temp",
                label="Your user temp folder",
                description="Per-user throwaway files from installers, unpacked archives and apps.",
                paths=user_temp,
                min_age_seconds=3600,
            ),
            CleanupCategory(
                id="windows_temp",
                label="Windows system temp",
                description="System-wide temp folder. Safe to remove files not locked by running apps.",
                paths=win_temp,
                min_age_seconds=3600,
            ),
            CleanupCategory(
                id="prefetch",
                label="Prefetch cache",
                description="Windows rebuilds this over time. Useful to clear after major app removals.",
                paths=prefetch,
                min_age_seconds=7 * 24 * 3600,
            ),
            CleanupCategory(
                id="crash_dumps",
                label="Crash dumps",
                description="Diagnostic dumps from crashed apps. Usually safe to remove once you've reported the bug.",
                paths=crash_dumps,
                min_age_seconds=24 * 3600,
            ),
        ]

    # ------------------------------------------------------------------ scan
    def scan(
        self,
        category_ids: Optional[Iterable[str]] = None,
        progress_cb: Optional[Callable[[str, int], None]] = None,
    ) -> CleanupScanResult:
        result = CleanupScanResult()
        wanted = {c for c in (category_ids or [])} or {c.id for c in self.categories}
        now = time.time()
        scanned = 0

        for category in self.categories:
            if category.id not in wanted:
                continue
            for root in category.paths:
                if not root.exists():
                    continue
                try:
                    for file_entry in self._walk(root, category.max_depth):
                        scanned += 1
                        try:
                            stat = file_entry.stat()
                        except (OSError, PermissionError):
                            continue
                        if now - stat.st_mtime < category.min_age_seconds:
                            continue
                        result.files.append(CleanupFile(
                            path=file_entry,
                            size=stat.st_size,
                            category_id=category.id,
                            mtime=stat.st_mtime,
                        ))
                        if progress_cb and scanned % 250 == 0:
                            progress_cb(str(file_entry), scanned)
                except Exception as exc:
                    log.warning("Scan failed at %s: %s", root, exc)
                    result.errors.append(f"{root}: {exc}")

        self.bus.publish("cleanup.scan_done", result)
        log.info("Cleanup scan: %d files, %d MB", len(result.files), result.total_bytes // (1024 * 1024))
        return result

    # ------------------------------------------------------------------ delete
    def delete(self, files: List[CleanupFile]) -> CleanupDeleteResult:
        res = CleanupDeleteResult()
        for cf in files:
            try:
                if cf.path.is_file():
                    cf.path.unlink(missing_ok=True)
                    res.deleted += 1
                    res.bytes_freed += cf.size
                else:
                    res.skipped += 1
            except PermissionError:
                res.skipped += 1
                res.errors.append(f"Locked: {cf.path}")
            except Exception as exc:
                res.skipped += 1
                res.errors.append(f"{cf.path}: {exc}")

        self.history.add(ActionRecord.new(
            category="cleanup",
            action="cleanup.delete",
            summary=f"Deleted {res.deleted} files, freed {res.bytes_freed // (1024 * 1024)} MB",
            risk="safe",
            reversible=False,
            status="applied",
            payload={
                "deleted": res.deleted,
                "skipped": res.skipped,
                "bytes_freed": res.bytes_freed,
                "errors": res.errors[:10],
            },
        ))
        self.bus.publish("cleanup.deleted", res)
        return res

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _walk(root: Path, max_depth: int) -> Iterable[Path]:
        base_parts = len(root.parts)
        for dirpath, _dirs, files in os.walk(root, onerror=lambda _e: None):
            try:
                current = Path(dirpath)
                depth = len(current.parts) - base_parts
                if depth > max_depth:
                    continue
                for fname in files:
                    yield current / fname
            except Exception:
                continue
