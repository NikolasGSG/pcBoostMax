"""Achievements / badges. Subscribes to event bus topics and awards
trophies when criteria are met.

The catalogue is declarative — adding a new achievement is one line.

Persistence: ``stats/achievements.json``. Each unlocked achievement
records its id, unlock timestamp, and the snapshot value that triggered it.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..core.event_bus import EventBus
from ..utils.logger import get_logger
from ..utils.paths import STATS_DIR, ensure_app_dirs

log = get_logger("engagement.achievements")

_FILENAME = "achievements.json"


@dataclass
class Achievement:
    """A single trophy."""
    id: str
    title: str
    description: str
    icon: str = "trophy"          # logical name; UI maps to a glyph
    tier: str = "bronze"          # "bronze" | "silver" | "gold" | "platinum"
    target: int = 1
    unit: str = ""                # display unit, e.g. "MB", "h", ""


@dataclass
class AchievementProgress:
    achievement_id: str
    progress: float = 0.0
    unlocked_at: float = 0.0      # unix ts; 0 = locked


class AchievementService:
    """Tracks progress, awards, and persists.

    Adding a new achievement: extend :data:`DEFAULT_ACHIEVEMENTS` and
    register a tally function via :meth:`register_counter`.
    """

    def __init__(
        self,
        bus: EventBus,
        *,
        catalog: Optional[List[Achievement]] = None,
        path: Optional[Path] = None,
    ) -> None:
        ensure_app_dirs()
        self._bus = bus
        self._catalog: Dict[str, Achievement] = {a.id: a for a in (catalog or DEFAULT_ACHIEVEMENTS)}
        self._path = path or (STATS_DIR / _FILENAME)
        self._lock = threading.RLock()
        self._progress: Dict[str, AchievementProgress] = self._load()
        self._counters: Dict[str, Callable[[float], None]] = {}
        self._wire_default_counters()

    # ------------------------------------------------------------------ public
    def all(self) -> List[Achievement]:
        return list(self._catalog.values())

    def progress(self, achievement_id: str) -> AchievementProgress:
        with self._lock:
            return self._progress.get(achievement_id, AchievementProgress(achievement_id=achievement_id))

    def progress_all(self) -> Dict[str, AchievementProgress]:
        with self._lock:
            return {aid: self.progress(aid) for aid in self._catalog}

    def unlocked(self) -> List[Achievement]:
        with self._lock:
            return [self._catalog[aid] for aid, p in self._progress.items()
                    if p.unlocked_at and aid in self._catalog]

    def increment(self, achievement_id: str, by: float = 1.0) -> AchievementProgress:
        """Bump progress; auto-unlocks once :attr:`Achievement.target` is hit."""
        ach = self._catalog.get(achievement_id)
        if ach is None:
            log.debug("Unknown achievement id %r", achievement_id)
            return AchievementProgress(achievement_id=achievement_id)
        with self._lock:
            cur = self._progress.setdefault(achievement_id, AchievementProgress(achievement_id=achievement_id))
            cur.progress += by
            newly_unlocked = False
            if cur.unlocked_at == 0 and cur.progress >= ach.target:
                cur.unlocked_at = time.time()
                cur.progress = float(ach.target)  # cap
                newly_unlocked = True
            self._save()
        if newly_unlocked:
            self._bus.publish("achievement.unlocked", ach, cur)
            log.info("achievement unlocked: %s (%s)", ach.id, ach.title)
        return cur

    # ------------------------------------------------------------------ default wiring
    def _wire_default_counters(self) -> None:
        # Plan applied → "first-plan", "ten-plans"
        def _on_plan_applied(*_a, **_kw) -> None:
            self.increment("first_plan")
            self.increment("ten_plans")

        def _on_cleanup_done(*_a, **kw) -> None:
            mb = float(kw.get("mb_freed", 0.0)) if kw else 0.0
            if mb <= 0:
                return
            self.increment("clean_5gb", by=mb)
            self.increment("clean_50gb", by=mb)

        def _on_memory_trim(result: object) -> None:
            mb = float(getattr(result, "freed_mb", 0.0))
            self.increment("trim_100mb", by=mb)
            self.increment("trim_10gb", by=mb)

        def _on_boost_started(_duration_s: int) -> None:
            self.increment("first_boost")

        def _on_gamemode_off(*_a, **kw) -> None:
            duration_s = float(kw.get("duration_s", 0.0)) if kw else 0.0
            hours = duration_s / 3600.0
            self.increment("game_mode_1h", by=hours)
            self.increment("game_mode_100h", by=hours)

        self._bus.subscribe("opt.plan_applied", _on_plan_applied)
        self._bus.subscribe("cleanup.done", _on_cleanup_done)
        self._bus.subscribe("memory.trimmed", _on_memory_trim)
        self._bus.subscribe("boost.started", _on_boost_started)
        self._bus.subscribe("gamemode.deactivated", _on_gamemode_off)

    # ------------------------------------------------------------------ io
    def _load(self) -> Dict[str, AchievementProgress]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return {k: AchievementProgress(**v) for k, v in raw.items()}
        except Exception:
            log.warning("Achievement state unreadable; resetting")
            return {}

    def _save(self) -> None:
        try:
            data = {k: asdict(v) for k, v in self._progress.items()}
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            log.exception("Failed to save achievement state")


# ---------------------------------------------------------------- catalogue
DEFAULT_ACHIEVEMENTS: List[Achievement] = [
    # Plans
    Achievement("first_plan", "First Tune-Up", "Apply your first optimization plan", "bolt", "bronze", 1),
    Achievement("ten_plans", "Tinkerer", "Apply 10 optimization plans", "bolt", "silver", 10),
    # Cleanup
    Achievement("clean_5gb", "Spring Cleaning", "Clean 5 GB of junk", "broom", "bronze", 5 * 1024, "MB"),
    Achievement("clean_50gb", "Marathon Cleaner", "Clean 50 GB of junk total", "broom", "gold", 50 * 1024, "MB"),
    # Memory
    Achievement("trim_100mb", "Quick Boost", "Trim 100 MB of RAM", "memory", "bronze", 100, "MB"),
    Achievement("trim_10gb", "RAM Wrangler", "Trim 10 GB of RAM total", "memory", "silver", 10 * 1024, "MB"),
    # Boost
    Achievement("first_boost", "Press to Win", "Trigger Press-to-Boost for the first time", "rocket", "bronze", 1),
    # Game Mode
    Achievement("game_mode_1h", "Warmed Up", "1 hour with Game Mode active", "gamepad", "bronze", 1, "h"),
    Achievement("game_mode_100h", "Pro Gamer", "100 hours with Game Mode active", "gamepad", "platinum", 100, "h"),
    # Streaks (incremented manually by StreakService listeners)
    Achievement("streak_7", "Week One", "Open GameBoost 7 days in a row", "calendar", "silver", 7),
    Achievement("streak_30", "Habit Formed", "Open GameBoost 30 days in a row", "calendar", "gold", 30),
]
