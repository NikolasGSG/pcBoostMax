"""Backup manager.

Every reversible action writes a small JSON backup describing the *previous*
state. :class:`RollbackEngine` consumes those blobs to restore settings.

Backups live under ``backups/`` in the app data dir and are referenced by a
stable id (also stored on the corresponding :class:`ActionRecord`).
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..utils.logger import get_logger
from ..utils.paths import BACKUP_DIR, ensure_app_dirs

log = get_logger("safety.backup")


@dataclass
class BackupEntry:
    id: str
    ts: float
    kind: str                 # e.g. "registry", "service", "power_plan", "file"
    description: str
    data: Dict[str, Any]      # kind-specific payload


class BackupManager:
    """Persists ``BackupEntry`` objects as individual JSON files."""

    def __init__(self) -> None:
        ensure_app_dirs()
        self._dir = BACKUP_DIR
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ API
    def save(self, kind: str, description: str, data: Dict[str, Any]) -> str:
        entry = BackupEntry(
            id=uuid.uuid4().hex[:12],
            ts=time.time(),
            kind=kind,
            description=description,
            data=data,
        )
        path = self._dir / f"{entry.id}.json"
        with self._lock:
            path.write_text(json.dumps(asdict(entry), indent=2), encoding="utf-8")
        log.info("Backup saved: %s (%s)", entry.id, description)
        return entry.id

    def load(self, backup_id: str) -> Optional[BackupEntry]:
        path = self._dir / f"{backup_id}.json"
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return BackupEntry(**raw)
        except Exception:
            log.exception("Failed loading backup %s", backup_id)
            return None

    def delete(self, backup_id: str) -> None:
        path = self._dir / f"{backup_id}.json"
        with self._lock:
            if path.exists():
                path.unlink()
                log.info("Backup deleted: %s", backup_id)

    def list_all(self) -> list[BackupEntry]:
        entries: list[BackupEntry] = []
        for fp in sorted(self._dir.glob("*.json")):
            try:
                entries.append(BackupEntry(**json.loads(fp.read_text(encoding="utf-8"))))
            except Exception:
                log.warning("Skipping unreadable backup %s", fp.name)
        return entries
