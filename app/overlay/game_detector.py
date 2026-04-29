"""Detect when a fullscreen game becomes the active window.

Polls the ``ForegroundTracker`` twice a second, applies a short debounce
(a fullscreen state must persist for ~2 samples before we flip) and emits
Qt signals:

* ``game_started``  — a new fullscreen foreground process just stabilised.
* ``game_stopped``  — the fullscreen process left focus (or closed).

The debounce prevents flicker when users briefly alt-tab out of a game
or when a loading splash covers the screen for a frame.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ..utils.logger import get_logger
from .foreground_tracker import ForegroundApp, ForegroundTracker

log = get_logger("overlay.game_detector")


# Titles we KNOW aren't games even when they're fullscreen.
_NON_GAME_EXES = {
    "explorer.exe",
    "taskmgr.exe",
    "gameboostapex.exe",   # us
    "pycharm64.exe",
    "code.exe",
    "winlogon.exe",
    "dwm.exe",
    "mmc.exe",
    "control.exe",
}


class GameDetector(QObject):
    """Emits ``game_started`` / ``game_stopped`` with debouncing."""

    game_started = pyqtSignal(object)   # ForegroundApp
    game_stopped = pyqtSignal(object)   # ForegroundApp (the one that ended)

    _DEBOUNCE_SAMPLES = 2               # samples in a row a state must hold

    def __init__(self, tracker: ForegroundTracker, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._tracker = tracker
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick)

        self._active_game: Optional[ForegroundApp] = None
        self._pending_start: Optional[ForegroundApp] = None
        self._pending_count: int = 0
        self._missing_count: int = 0

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if not self._timer.isActive():
            log.info("Game detector started (500 ms cadence)")
            self._timer.start()

    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            log.info("Game detector stopped")

    # ------------------------------------------------------------------ core loop
    def _tick(self) -> None:
        sample = self._tracker.sample()
        is_game = self._looks_like_a_game(sample)

        if is_game and sample:
            # If we're ALREADY tracking this game, keep going.
            if self._active_game and self._active_game.pid == sample.pid:
                self._missing_count = 0
                return
            # Candidate for a new game — require _DEBOUNCE_SAMPLES matches.
            if self._pending_start and self._pending_start.pid == sample.pid:
                self._pending_count += 1
                if self._pending_count >= self._DEBOUNCE_SAMPLES:
                    self._promote_pending_to_active()
            else:
                self._pending_start = sample
                self._pending_count = 1
            self._missing_count = 0
            return

        # Not a game this tick. If we were active, require a few misses
        # before emitting game_stopped (avoids a single stray alt-tab flipping us).
        self._pending_start = None
        self._pending_count = 0
        if self._active_game:
            self._missing_count += 1
            if self._missing_count >= self._DEBOUNCE_SAMPLES:
                ended = self._active_game
                self._active_game = None
                self._missing_count = 0
                log.info("Game ended: %s", ended.exe_name)
                self.game_stopped.emit(ended)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _looks_like_a_game(sample: Optional[ForegroundApp]) -> bool:
        if not sample or not sample.is_fullscreen:
            return False
        exe = (sample.exe_name or "").lower()
        if not exe or exe in _NON_GAME_EXES:
            return False
        # Anything else that is fullscreen and uses >40 MB RAM is very
        # likely to be a game, a media app, or a 3D tool. All benefit
        # from Game Mode being on anyway.
        return sample.ram_mb > 40

    def _promote_pending_to_active(self) -> None:
        pending = self._pending_start
        if not pending:
            return
        self._active_game = pending
        self._pending_start = None
        self._pending_count = 0
        log.info("Game started: %s (pid=%d)", pending.exe_name, pending.pid)
        self.game_started.emit(pending)

    # ------------------------------------------------------------------ introspection
    @property
    def active_game(self) -> Optional[ForegroundApp]:
        return self._active_game
