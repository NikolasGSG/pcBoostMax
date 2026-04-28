"""Daily-open streak tracking. Persists to ``stats/streaks.json``."""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from ..utils.logger import get_logger
from ..utils.paths import STATS_DIR, ensure_app_dirs

log = get_logger("engagement.streaks")

_FILENAME = "streaks.json"


@dataclass
class StreakState:
    last_open: str = ""        # YYYY-MM-DD
    current_streak: int = 0
    longest_streak: int = 0
    total_days: int = 0


class StreakService:
    """Increments the streak when the app opens on a new local day."""

    def __init__(self, *, path: Optional[Path] = None) -> None:
        ensure_app_dirs()
        self._path = path or (STATS_DIR / _FILENAME)
        self._state = self._load()

    @property
    def state(self) -> StreakState:
        return StreakState(**asdict(self._state))

    def record_open(self) -> StreakState:
        today = dt.date.today().isoformat()
        if self._state.last_open == today:
            return self.state

        if self._state.last_open:
            try:
                last = dt.date.fromisoformat(self._state.last_open)
                gap = (dt.date.today() - last).days
            except ValueError:
                gap = 1
        else:
            gap = 1

        if gap == 1:
            self._state.current_streak += 1
        else:
            # Streak broken — start fresh at 1.
            self._state.current_streak = 1

        self._state.longest_streak = max(self._state.longest_streak, self._state.current_streak)
        self._state.total_days += 1
        self._state.last_open = today
        self._save()
        log.info(
            "streak: current=%d longest=%d total=%d",
            self._state.current_streak,
            self._state.longest_streak,
            self._state.total_days,
        )
        return self.state

    # ------------------------------------------------------------------ io
    def _load(self) -> StreakState:
        if not self._path.exists():
            return StreakState()
        try:
            return StreakState(**json.loads(self._path.read_text(encoding="utf-8")))
        except Exception:
            log.warning("Streak state unreadable; resetting")
            return StreakState()

    def _save(self) -> None:
        try:
            self._path.write_text(json.dumps(asdict(self._state), indent=2), encoding="utf-8")
        except Exception:
            log.exception("Failed to save streak state")
