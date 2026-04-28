"""Game library — model + the library that holds detected games.

A :class:`Game` is the unified record that comes back from any scanner.
We deliberately keep the model tiny so the same record works for Steam,
Epic, Battle.net, Xbox, etc. The launcher-specific quirks (where to run
the launch URI, how to find the cover art) are handled inside the
scanners and squashed down into this canonical record.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable, List, Optional

from ..utils.logger import get_logger
from ..utils.paths import APP_DATA_DIR

log = get_logger("games.library")


class Launcher(str, Enum):
    """Which launcher / store the game came from."""

    STEAM = "steam"
    EPIC = "epic"
    GOG = "gog"
    BATTLE_NET = "battlenet"
    RIOT = "riot"
    UBISOFT = "ubisoft"
    EA = "ea"
    XBOX = "xbox"
    STANDALONE = "standalone"
    MANUAL = "manual"

    @property
    def label(self) -> str:
        return {
            Launcher.STEAM: "Steam",
            Launcher.EPIC: "Epic",
            Launcher.GOG: "GOG",
            Launcher.BATTLE_NET: "Battle.net",
            Launcher.RIOT: "Riot",
            Launcher.UBISOFT: "Ubisoft",
            Launcher.EA: "EA",
            Launcher.XBOX: "Xbox",
            Launcher.STANDALONE: "Standalone",
            Launcher.MANUAL: "Manual",
        }[self]


@dataclass
class Game:
    """One game in the library."""

    id: str                                  # stable id, e.g. "steam:730"
    name: str
    launcher: Launcher
    install_dir: str = ""
    exe_path: str = ""                       # primary executable, if known
    launch_uri: str = ""                     # e.g. "steam://rungameid/730"
    appid: str = ""                          # launcher-native id (steam appid etc)
    cover_path: str = ""                     # local cached cover image
    last_played: float = 0.0
    size_bytes: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["launcher"] = self.launcher.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Game":
        d = dict(d)
        d["launcher"] = Launcher(d.get("launcher", "manual"))
        return cls(**{k: v for k, v in d.items() if k in {f.name for f in cls.__dataclass_fields__.values()}})


class GameLibrary:
    """Aggregated view of detected games across launchers.

    The library is persistent — we cache the last successful scan so the
    Game Hub view renders instantly on next launch even if the scanners
    are slow.
    """

    _CACHE_FILE = APP_DATA_DIR / "library_cache.json"

    def __init__(self) -> None:
        self._games: dict[str, Game] = {}
        self._last_scan_ts: float = 0.0
        self._load_cache()

    # ------------------------------------------------------------------ api
    @property
    def games(self) -> List[Game]:
        return sorted(
            self._games.values(),
            key=lambda g: (-g.last_played, g.name.lower()),
        )

    @property
    def last_scan_ts(self) -> float:
        return self._last_scan_ts

    def upsert(self, game: Game) -> None:
        existing = self._games.get(game.id)
        if existing:
            # Preserve last_played from previous record if scanner doesn't know.
            if not game.last_played and existing.last_played:
                game.last_played = existing.last_played
            if not game.cover_path and existing.cover_path:
                game.cover_path = existing.cover_path
        self._games[game.id] = game

    def remove(self, game_id: str) -> None:
        self._games.pop(game_id, None)

    def get(self, game_id: str) -> Optional[Game]:
        return self._games.get(game_id)

    def update_last_played(self, game_id: str) -> None:
        g = self._games.get(game_id)
        if g:
            g.last_played = time.time()
            self.save()

    def replace_all(self, games: Iterable[Game]) -> None:
        self._games = {g.id: g for g in games}
        self._last_scan_ts = time.time()
        self.save()

    # ------------------------------------------------------------------ persistence
    def _load_cache(self) -> None:
        if not self._CACHE_FILE.exists():
            return
        try:
            raw = json.loads(self._CACHE_FILE.read_text(encoding="utf-8"))
            self._last_scan_ts = float(raw.get("last_scan_ts", 0.0))
            for d in raw.get("games", []):
                try:
                    g = Game.from_dict(d)
                    self._games[g.id] = g
                except Exception:
                    log.warning("Skipping unreadable cached game: %r", d)
        except Exception:
            log.exception("Library cache unreadable, starting empty")

    def save(self) -> None:
        try:
            self._CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._CACHE_FILE.write_text(
                json.dumps({
                    "last_scan_ts": self._last_scan_ts,
                    "games": [g.to_dict() for g in self._games.values()],
                }, indent=2),
                encoding="utf-8",
            )
        except Exception:
            log.exception("Failed to save library cache")
