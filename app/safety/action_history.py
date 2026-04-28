"""Append-only action history.

Every meaningful state change (optimization applied, cleanup executed, Game
Mode toggled) is recorded here. The UI surfaces this so the user always
understands "what did this tool just do to my machine?".
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, List, Optional

from ..utils.logger import get_logger
from ..utils.paths import HISTORY_DIR, ensure_app_dirs

log = get_logger("safety.history")


@dataclass
class ActionRecord:
    id: str
    ts: float
    category: str             # "optimize" | "cleanup" | "gamemode" | "rollback"
    action: str               # rule id / cleaner id / event name
    summary: str              # short, human-readable
    risk: str = "safe"
    reversible: bool = True
    status: str = "applied"   # "applied" | "rolled_back" | "failed" | "skipped"
    payload: dict[str, Any] = field(default_factory=dict)   # arbitrary detail
    rollback_ref: Optional[str] = None                      # backup id

    @classmethod
    def new(cls, **kwargs: Any) -> "ActionRecord":
        return cls(id=uuid.uuid4().hex[:12], ts=time.time(), **kwargs)


class ActionHistory:
    """JSON-lines store at ``history/actions.jsonl`` (rotated daily-ish).

    Thread-safe; the file is rewritten only on :meth:`mark_status` updates,
    otherwise appended to.
    """

    _FILENAME = "actions.jsonl"

    def __init__(self) -> None:
        ensure_app_dirs()
        self._path = HISTORY_DIR / self._FILENAME
        self._lock = threading.RLock()
        self._records: List[ActionRecord] = self._load()

    # ------------------------------------------------------------------ io
    def _load(self) -> List[ActionRecord]:
        if not self._path.exists():
            return []
        records: List[ActionRecord] = []
        try:
            for line in self._path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                data = json.loads(line)
                records.append(ActionRecord(**data))
        except Exception:
            log.exception("Failed to load action history; starting fresh")
            records = []
        return records

    def _rewrite(self) -> None:
        with self._path.open("w", encoding="utf-8") as fh:
            for rec in self._records:
                fh.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ api
    def add(self, record: ActionRecord) -> None:
        with self._lock:
            self._records.append(record)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        log.info("Action recorded: [%s] %s -> %s", record.category, record.action, record.status)

    def mark_status(self, action_id: str, status: str) -> None:
        with self._lock:
            for rec in self._records:
                if rec.id == action_id:
                    rec.status = status
                    self._rewrite()
                    log.info("Action %s → %s", action_id, status)
                    return

    def recent(self, limit: int = 100) -> List[ActionRecord]:
        with self._lock:
            return list(reversed(self._records[-limit:]))

    def all(self) -> List[ActionRecord]:
        with self._lock:
            return list(self._records)

    def export(self, destination) -> int:
        """Export history to the given path (JSON array). Returns count written."""
        from pathlib import Path

        dest = Path(destination)
        with self._lock:
            data = [asdict(r) for r in self._records]
        dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return len(data)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            if self._path.exists():
                self._path.unlink()
