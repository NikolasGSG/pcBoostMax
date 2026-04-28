"""ViewModel for the Game Hub view."""
from __future__ import annotations

import threading
from typing import List

from PyQt6.QtCore import QObject, pyqtSignal

from ...core.app_controller import AppController
from ...games.library import Game, GameLibrary
from ...games.profiles import GameProfile, GameProfileService
from ...utils.logger import get_logger
from ...utils.subprocess_helper import popen as _popen_silent
from .base import ViewModel

log = get_logger("vm.game_hub")


class GameHubViewModel(ViewModel):
    library_changed = pyqtSignal(list)        # list[Game]
    scanning_changed = pyqtSignal(bool)
    profile_applied = pyqtSignal(object)      # GameProfile

    def __init__(self, controller: AppController, parent: QObject | None = None) -> None:
        super().__init__(controller, parent)
        self._library = GameLibrary()
        self._profiles = GameProfileService.get(controller)
        self._scanning = False

        controller.bus.subscribe("game_profile.applied", self.profile_applied.emit)

    # ------------------------------------------------------------------ api
    @property
    def library(self) -> GameLibrary:
        return self._library

    @property
    def profiles(self) -> GameProfileService:
        return self._profiles

    @property
    def games(self) -> List[Game]:
        return self._library.games

    @property
    def is_scanning(self) -> bool:
        return self._scanning

    def rescan(self) -> None:
        if self._scanning:
            return
        self._scanning = True
        self.scanning_changed.emit(True)
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self) -> None:
        try:
            from ...games.scanners import scan_all
            games = scan_all()
            self._library.replace_all(games)
        except Exception:
            log.exception("Game library scan failed")
        finally:
            self._scanning = False
            self.scanning_changed.emit(False)
            self.library_changed.emit(self._library.games)

    def launch(self, game_id: str) -> bool:
        g = self._library.get(game_id)
        if g is None:
            return False
        try:
            if g.launch_uri:
                # URI scheme: hand to OS via 'start'
                _popen_silent(["cmd", "/c", "start", "", g.launch_uri])
            elif g.exe_path:
                _popen_silent([g.exe_path])
            else:
                return False
            self._library.update_last_played(game_id)
            return True
        except Exception:
            log.exception("Game launch failed for %s", g.name)
            return False

    def get_or_create_profile(self, game_id: str) -> GameProfile | None:
        g = self._library.get(game_id)
        if g is None:
            return None
        existing = self._profiles.get_for_id(game_id)
        if existing:
            return existing
        new = GameProfile.default_for(game_id, g.name, g.exe_path)
        self._profiles.save(new)
        return new

    def apply_profile_now(self, game_id: str) -> bool:
        p = self.get_or_create_profile(game_id)
        if p is None:
            return False
        g = self._library.get(game_id)
        return self._profiles.apply(p, exe=(g.exe_path if g else ""))
