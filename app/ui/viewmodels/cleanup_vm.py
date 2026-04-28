"""ViewModel for the Cleanup view."""
from __future__ import annotations

from typing import Iterable, List, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from ...cleanup.cleaner import CleanupDeleteResult, CleanupFile, CleanupScanResult
from ...core.app_controller import AppController
from .base import ViewModel


class _ScanWorker(QThread):
    finished_with = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(str, int)

    def __init__(self, service, ids: Optional[Iterable[str]], parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._ids = ids

    def run(self) -> None:
        try:
            result = self._service.scan(self._ids, progress_cb=self._emit_progress)
            self.finished_with.emit(result)
        except Exception as exc:  # pragma: no cover
            self.failed.emit(str(exc))

    def _emit_progress(self, path: str, scanned: int) -> None:
        self.progress.emit(path, scanned)


class CleanupViewModel(ViewModel):
    scan_finished = pyqtSignal(object)       # CleanupScanResult
    scan_failed = pyqtSignal(str)
    scan_progress = pyqtSignal(str, int)
    deleted = pyqtSignal(object)             # CleanupDeleteResult

    def __init__(self, controller: AppController, parent: QObject | None = None) -> None:
        super().__init__(controller, parent)
        self._worker: Optional[_ScanWorker] = None

    @property
    def categories(self):
        return self.controller.cleanup.categories

    def scan(self, category_ids: Optional[List[str]] = None) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._worker = _ScanWorker(self.controller.cleanup, category_ids, parent=self)
        self._worker.finished_with.connect(self.scan_finished.emit)
        self._worker.failed.connect(self.scan_failed.emit)
        self._worker.progress.connect(self.scan_progress.emit)
        self._worker.start()

    def delete(self, files: List[CleanupFile]) -> CleanupDeleteResult:
        result = self.controller.cleanup.delete(files)
        self.deleted.emit(result)
        return result
