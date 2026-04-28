"""ViewModel for Game Mode controls."""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from ...core.app_controller import AppController
from ...optimization.game_mode import GameModeSnapshot
from .base import ViewModel


class GameModeViewModel(ViewModel):
    activated = pyqtSignal(object)        # GameModeSnapshot
    deactivated = pyqtSignal(object)

    def __init__(self, controller: AppController, parent: QObject | None = None) -> None:
        super().__init__(controller, parent)
        controller.bus.subscribe("gamemode.activated", self.activated.emit)
        controller.bus.subscribe("gamemode.deactivated", self.deactivated.emit)

    @property
    def is_active(self) -> bool:
        return self.controller.game_mode.is_active

    @property
    def started_at(self) -> Optional[float]:
        return self.controller.game_mode.started_at

    def activate(
        self,
        *,
        suspend_targets: Optional[List[str]] = None,
        enable_power: bool = True,
        enable_visual: bool = True,
        enable_dvr: bool = True,
    ) -> GameModeSnapshot:
        return self.controller.game_mode.activate(
            suspend_targets=suspend_targets,
            enable_power=enable_power,
            enable_visual=enable_visual,
            enable_dvr=enable_dvr,
        )

    def deactivate(self) -> None:
        self.controller.game_mode.deactivate()
