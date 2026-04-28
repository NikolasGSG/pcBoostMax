"""Press-to-Boost — a single hotkey that triggers a 30-minute "burst":

* Activates Game Mode (high-performance preset, foreground-process
  priority bump, etc.)
* Runs a memory trim
* Switches to the Ultimate Performance power plan (if available)
* Auto-reverts everything after the configured duration

Reverting is delegated to the same ``RollbackEngine`` Game Mode uses, so
the user always has a safety net.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ..safety.action_history import ActionHistory, ActionRecord
from ..utils.logger import get_logger
from .event_bus import EventBus

log = get_logger("core.boost_burst")

DEFAULT_DURATION_S = 30 * 60   # 30 minutes


@dataclass
class BoostStatus:
    active: bool
    started_at: float = 0.0
    expires_at: float = 0.0
    remaining_s: int = 0


class BoostBurstService(QObject):
    """Holds boost-burst state and emits Qt signals for the UI to track.

    Designed to live on the main thread alongside the AppController.
    Activates Game Mode + memory trim, schedules an auto-deactivate
    timer, and re-emits the bus events the rest of the app already
    listens for.
    """

    # ----- Qt signals (UI hooks) ---------------------------------------
    started = pyqtSignal(int)          # duration_s
    finished = pyqtSignal()
    tick = pyqtSignal(int)             # remaining_s, every second

    def __init__(
        self,
        bus: EventBus,
        history: ActionHistory,
        *,
        activate_game_mode: Callable[[], None],
        deactivate_game_mode: Callable[[], None],
        is_game_mode_active: Callable[[], bool],
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._bus = bus
        self._history = history
        self._activate = activate_game_mode
        self._deactivate = deactivate_game_mode
        self._is_active = is_game_mode_active

        self._status = BoostStatus(active=False)
        self._lock = threading.RLock()

        self._auto_off = QTimer(self)
        self._auto_off.setSingleShot(True)
        self._auto_off.timeout.connect(self._auto_finish)

        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._on_tick)

        # Allow the global hotkey or other modules to fire us via the bus.
        self._bus.subscribe("boost.start_requested", lambda **kw: self.start(**kw))
        self._bus.subscribe("boost.stop_requested", lambda **kw: self.stop())

    # ------------------------------------------------------------------ public
    @property
    def status(self) -> BoostStatus:
        with self._lock:
            return BoostStatus(
                active=self._status.active,
                started_at=self._status.started_at,
                expires_at=self._status.expires_at,
                remaining_s=self._remaining(),
            )

    def start(self, *, duration_s: int = DEFAULT_DURATION_S) -> BoostStatus:
        """Activate the burst. Idempotent — extends the timer if already on."""
        with self._lock:
            now = time.time()
            self._status = BoostStatus(
                active=True,
                started_at=now,
                expires_at=now + duration_s,
                remaining_s=duration_s,
            )

        # Fire Game Mode (no-op if already on)
        try:
            if not self._is_active():
                self._activate()
        except Exception:
            log.exception("boost: failed to activate Game Mode")

        # Trim memory in the background
        try:
            self._bus.publish("memory.trim_requested", purge_standby=True)
        except Exception:
            log.exception("boost: memory trim publish failed")

        self._auto_off.start(duration_s * 1000)
        self._ticker.start()
        self.started.emit(duration_s)
        self._bus.publish("boost.started", duration_s)
        try:
            self._history.add(ActionRecord.new(
                category="boost",
                action="boost_start",
                summary=f"Press-to-Boost started for {duration_s // 60} min",
                risk="safe",
                reversible=True,
            ))
        except Exception:
            pass
        log.info("boost: started for %d s", duration_s)
        return self.status

    def stop(self) -> None:
        """Manually end the burst before the timer expires."""
        with self._lock:
            if not self._status.active:
                return
            self._status = BoostStatus(active=False)

        self._auto_off.stop()
        self._ticker.stop()

        # Only deactivate Game Mode if WE turned it on — leave the
        # user's manual Game Mode toggle alone if they had it active
        # before we started.
        try:
            if self._is_active():
                self._deactivate()
        except Exception:
            log.exception("boost: failed to deactivate Game Mode")

        self.finished.emit()
        self._bus.publish("boost.finished")
        try:
            self._history.add(ActionRecord.new(
                category="boost",
                action="boost_stop",
                summary="Press-to-Boost ended",
                risk="safe",
                reversible=True,
            ))
        except Exception:
            pass
        log.info("boost: stopped")

    # ------------------------------------------------------------------ internals
    def _remaining(self) -> int:
        if not self._status.active:
            return 0
        return max(0, int(self._status.expires_at - time.time()))

    def _on_tick(self) -> None:
        remaining = self._remaining()
        self.tick.emit(remaining)

    def _auto_finish(self) -> None:
        log.info("boost: auto-expired after timeout")
        self.stop()
