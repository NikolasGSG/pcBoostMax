"""ViewModel for anything that consumes live metric samples.

Subscribes to the bus and re-emits on the main thread via a Qt signal.
Views only need to ``connect`` to ``sampled``.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, Qt, pyqtSignal

from ...core.app_controller import AppController
from ...monitoring.performance_monitor import MetricSample
from .base import ViewModel


class MonitorViewModel(ViewModel):
    sampled = pyqtSignal(object)          # MetricSample
    hardware_ready = pyqtSignal(object)   # HardwareSnapshot

    def __init__(self, controller: AppController, parent: QObject | None = None) -> None:
        super().__init__(controller, parent)
        controller.bus.subscribe("monitor.sample", self._on_sample)
        controller.bus.subscribe("hardware.detected", self._on_hw)

    # ------------------------------------------------------------------ subscribers
    def _on_sample(self, sample: MetricSample) -> None:
        # Marshal to the main thread: signals emitted from other threads are
        # queued automatically if the receivers live on the main thread.
        self.sampled.emit(sample)

    def _on_hw(self, snapshot) -> None:
        self.hardware_ready.emit(snapshot)
