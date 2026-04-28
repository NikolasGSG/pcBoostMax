"""Rollback engine.

Each reversible rule registers a pair of callables:

* ``capture() -> dict``            — captures state before apply (stored as backup)
* ``restore(data: dict) -> None``  — restores state from a previously captured backup

The engine only knows about :class:`BackupEntry` + :class:`ActionRecord`. It
looks up the correct rule by ``action`` name and asks it to restore.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from ..utils.logger import get_logger
from .action_history import ActionHistory, ActionRecord
from .backup_manager import BackupEntry, BackupManager

log = get_logger("safety.rollback")

RestoreFn = Callable[[dict], None]


@dataclass
class RollbackResult:
    succeeded: List[str]
    failed: List[tuple[str, str]]   # (action_id, reason)

    @property
    def ok(self) -> bool:
        return not self.failed


class RollbackEngine:
    """Coordinates ``BackupManager`` + ``ActionHistory`` to undo changes."""

    def __init__(self, backups: BackupManager, history: ActionHistory) -> None:
        self.backups = backups
        self.history = history
        self._restorers: Dict[str, RestoreFn] = {}

    # ------------------------------------------------------------------ registration
    def register(self, action_name: str, restore_fn: RestoreFn) -> None:
        self._restorers[action_name] = restore_fn
        log.debug("Registered restore for %s", action_name)

    # ------------------------------------------------------------------ execution
    def rollback_action(self, record: ActionRecord) -> bool:
        if record.status != "applied":
            log.info("Action %s already %s, skipping", record.id, record.status)
            return True
        if not record.reversible:
            log.warning("Action %s is marked non-reversible", record.id)
            return False
        if not record.rollback_ref:
            log.warning("Action %s has no backup reference", record.id)
            return False

        backup = self.backups.load(record.rollback_ref)
        if not backup:
            log.warning("Backup %s missing for action %s", record.rollback_ref, record.id)
            return False

        restorer = self._restorers.get(record.action)
        if not restorer:
            log.warning("No restorer registered for %s", record.action)
            return False

        try:
            restorer(backup.data)
            self.history.mark_status(record.id, "rolled_back")
            log.info("Rolled back action %s (%s)", record.id, record.action)
            return True
        except Exception:
            log.exception("Rollback failed for %s", record.action)
            return False

    def rollback_all_since(self, ts: float) -> RollbackResult:
        succeeded: List[str] = []
        failed: List[tuple[str, str]] = []
        # roll back in reverse chronological order
        to_rollback = [r for r in self.history.all() if r.ts >= ts and r.status == "applied" and r.reversible]
        for record in reversed(to_rollback):
            if self.rollback_action(record):
                succeeded.append(record.id)
            else:
                failed.append((record.id, "restore failed"))
        return RollbackResult(succeeded=succeeded, failed=failed)

    def available_for(self, record: ActionRecord) -> bool:
        return (
            record.reversible
            and record.status == "applied"
            and record.action in self._restorers
            and bool(record.rollback_ref)
        )
