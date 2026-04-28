"""Base ViewModel class.

ViewModels are thin wrappers around the controller. They hold no widgets —
they only expose Qt signals that views connect to, and translate bus events
to those signals on the Qt main thread.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from ...core.app_controller import AppController


class ViewModel(QObject):
    """Subclass and add signals as needed."""

    def __init__(self, controller: AppController, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
