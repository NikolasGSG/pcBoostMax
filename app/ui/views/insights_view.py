"""Insights view — Auto-Troubleshooter + hardware findings + predictions."""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from ...diagnostics import Diagnosis, Symptom, Troubleshooter
from ...monitoring.analyzers.predictive_maintenance import MaintenancePrediction
from ...system.inspectors import Finding, FindingSeverity
from ...utils.logger import get_logger
from ..theme.palette import Palette
from ..theme.typography import Typography
from ..widgets.banner import Banner
from ..widgets.section import Card, SectionHeader

log = get_logger("ui.insights")

_SYMPTOMS = [
    ("Game stutters / micro-freezes", Symptom.GAME_STUTTERS),
    ("Low FPS in games", Symptom.LOW_FPS),
    ("High network latency / lag", Symptom.HIGH_LATENCY),
    ("Slow boot times", Symptom.SLOW_BOOT),
    ("System runs hot", Symptom.SYSTEM_HOT),
    ("Random freezes / crashes", Symptom.RANDOM_FREEZES),
]

_SEVERITY_BADGE = {
    FindingSeverity.CRITICAL: ("CRITICAL", "coral"),
    FindingSeverity.WARNING: ("WARNING", "amber"),
    FindingSeverity.SUGGESTION: ("SUGGEST", "neon_blue"),
    FindingSeverity.INFO: ("INFO", "text_secondary"),
}


class _Worker(QObject):
    diagnosis_ready = pyqtSignal(object)
    findings_ready = pyqtSignal(list)
    predictions_ready = pyqtSignal(list)
    finished = pyqtSignal()

    def __init__(self, ctrl, mode: str, symptom: Optional[Symptom] = None):
        super().__init__()
        self._ctrl = ctrl
        self._mode = mode
        self._symptom = symptom

    def run(self) -> None:
        try:
            if self._mode == "diagnose" and self._symptom is not None:
                t = Troubleshooter(
                    ram_inspector=self._ctrl.ram_inspector,
                    pcie_inspector=self._ctrl.pcie_inspector,
                    nvme_inspector=self._ctrl.nvme_inspector,
                    driver_auditor=self._ctrl.driver_auditor,
                    boot_service=self._ctrl.boot_time,
                    predictive=self._ctrl.predictive_maintenance,
                )
                self.diagnosis_ready.emit(t.diagnose(self._symptom))
            elif self._mode == "findings":
                fs: List[Finding] = []
                for ins in (self._ctrl.ram_inspector, self._ctrl.pcie_inspector,
                            self._ctrl.nvme_inspector, self._ctrl.driver_auditor):
                    try:
                        fs.extend(ins.inspect())
                    except Exception:
                        log.exception("inspector failed")
                self.findings_ready.emit(fs)
            elif self._mode == "predictions":
                self.predictions_ready.emit(self._ctrl.predictive_maintenance.predictions())
        except Exception:
            log.exception("worker failed")
        finally:
            self.finished.emit()


class InsightsView(QWidget):
    def __init__(self, controller, palette: Palette, typography: Typography, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._pal = palette
        self._type = typography
        self._threads: list[QThread] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, stretch=1)

        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(20)

        root.addWidget(SectionHeader(
            "INSIGHTS", "Diagnose & forecast",
            palette=palette, typography=typography,
        ))
        root.addWidget(Banner(
            "All analysis runs locally on your PC. Nothing is uploaded.",
            palette=palette, typography=typography, role="info",
        ))
        root.addWidget(self._build_troubleshooter())
        root.addWidget(self._build_findings())
        root.addWidget(self._build_predictions())
        root.addStretch(1)

    # ---------------------------------------------------------------- helpers
    def _h2(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(self._type.h2())
        lbl.setStyleSheet(f"color: {self._pal.text_primary};")
        return lbl

    def _muted(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(self._type.body())
        lbl.setStyleSheet(f"color: {self._pal.text_secondary};")
        lbl.setWordWrap(True)
        return lbl

    def _spawn(self, mode: str, on_ok, *, symptom: Optional[Symptom] = None) -> None:
        thread = QThread(self)
        worker = _Worker(self._ctrl, mode, symptom)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        if mode == "diagnose":
            worker.diagnosis_ready.connect(on_ok)
        elif mode == "findings":
            worker.findings_ready.connect(on_ok)
        elif mode == "predictions":
            worker.predictions_ready.connect(on_ok)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._threads.remove(thread) if thread in self._threads else None)
        self._threads.append(thread)
        thread.start()

    # ---------------------------------------------------------------- panels
    def _build_troubleshooter(self) -> QWidget:
        card = Card(palette=self._pal)
        body = card.body()
        body.addWidget(self._h2("Auto-Troubleshooter"))
        body.addWidget(self._muted(
            "Pick what's bothering you and we'll map symptoms to specific fixes."
        ))

        row = QHBoxLayout()
        row.setSpacing(10)
        self._symptom_combo = QComboBox()
        for label, _sym in _SYMPTOMS:
            self._symptom_combo.addItem(label)
        row.addWidget(self._symptom_combo, stretch=1)

        self._diagnose_btn = QPushButton("Diagnose")
        self._diagnose_btn.setProperty("variant", "primary")
        self._diagnose_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._diagnose_btn.clicked.connect(self._on_diagnose)
        row.addWidget(self._diagnose_btn)
        body.addLayout(row)

        self._diagnose_results = QVBoxLayout()
        self._diagnose_results.setSpacing(8)
        body.addLayout(self._diagnose_results)
        return card

    def _build_findings(self) -> QWidget:
        card = Card(palette=self._pal)
        body = card.body()
        head = QHBoxLayout()
        head.addWidget(self._h2("Hardware findings"), stretch=1)
        self._refresh_findings_btn = QPushButton("Re-scan")
        self._refresh_findings_btn.setProperty("variant", "ghost")
        self._refresh_findings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_findings_btn.clicked.connect(self._on_findings)
        head.addWidget(self._refresh_findings_btn)
        body.addLayout(head)

        body.addWidget(self._muted(
            "RAM speed, PCIe link, NVMe wear, and outdated drivers — checked together."
        ))
        self._findings_box = QVBoxLayout()
        self._findings_box.setSpacing(6)
        body.addLayout(self._findings_box)
        self._findings_empty = self._muted("Click Re-scan to inspect your hardware.")
        self._findings_box.addWidget(self._findings_empty)
        return card

    def _build_predictions(self) -> QWidget:
        card = Card(palette=self._pal)
        body = card.body()
        head = QHBoxLayout()
        head.addWidget(self._h2("Predictive maintenance"), stretch=1)
        btn = QPushButton("Refresh")
        btn.setProperty("variant", "ghost")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._on_predictions)
        head.addWidget(btn)
        body.addLayout(head)

        body.addWidget(self._muted(
            "Forecasts SSD end-of-life and boot-time regressions from your history."
        ))
        self._predictions_box = QVBoxLayout()
        self._predictions_box.setSpacing(6)
        body.addLayout(self._predictions_box)
        self._predictions_empty = self._muted(
            "Click Refresh after using the app for a few days to build a baseline."
        )
        self._predictions_box.addWidget(self._predictions_empty)
        return card

    # ---------------------------------------------------------------- handlers
    def _on_diagnose(self) -> None:
        idx = self._symptom_combo.currentIndex()
        symptom = _SYMPTOMS[idx][1] if 0 <= idx < len(_SYMPTOMS) else Symptom.GAME_STUTTERS
        self._diagnose_btn.setEnabled(False)
        self._diagnose_btn.setText("Analysing...")
        self._spawn("diagnose", self._show_diagnosis, symptom=symptom)

    def _show_diagnosis(self, diag: Diagnosis) -> None:
        self._diagnose_btn.setEnabled(True)
        self._diagnose_btn.setText("Diagnose")
        # clear previous
        while self._diagnose_results.count():
            item = self._diagnose_results.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if diag.summary:
            summary = QLabel(diag.summary)
            summary.setFont(self._type.body())
            summary.setStyleSheet(
                f"color: {self._pal.accent}; padding: 8px 12px; "
                f"background: {self._pal.accent_dim}; border-radius: 6px;"
            )
            summary.setWordWrap(True)
            self._diagnose_results.addWidget(summary)
        for i, step in enumerate(diag.steps, 1):
            self._diagnose_results.addWidget(self._step_row(i, step))

    def _step_row(self, n: int, step) -> QWidget:
        wrap = QFrame()
        wrap.setStyleSheet(
            f"QFrame {{ background: {self._pal.bg_sunken}; "
            f"border: 1px solid {self._pal.border}; border-radius: 6px; }}"
        )
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)
        suffix = " · manual" if step.manual else ""
        title = QLabel(f"{n}. {step.title}{suffix}  ({step.confidence}% confidence)")
        title.setFont(self._type.body())
        title.setStyleSheet(f"color: {self._pal.text_primary};")
        title.setWordWrap(True)
        lay.addWidget(title)
        if step.detail:
            sub = QLabel(step.detail)
            sub.setFont(self._type.small())
            sub.setStyleSheet(f"color: {self._pal.text_secondary};")
            sub.setWordWrap(True)
            lay.addWidget(sub)
        return wrap

    def _on_findings(self) -> None:
        self._refresh_findings_btn.setEnabled(False)
        self._refresh_findings_btn.setText("Scanning...")
        self._spawn("findings", self._show_findings)

    def _show_findings(self, findings: List[Finding]) -> None:
        self._refresh_findings_btn.setEnabled(True)
        self._refresh_findings_btn.setText("Re-scan")
        while self._findings_box.count():
            item = self._findings_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if not findings:
            self._findings_box.addWidget(self._muted("No hardware issues detected. Nice rig!"))
            return
        for f in findings:
            self._findings_box.addWidget(self._finding_row(f))

    def _finding_row(self, f: Finding) -> QWidget:
        wrap = QFrame()
        wrap.setStyleSheet(
            f"QFrame {{ background: {self._pal.bg_sunken}; "
            f"border: 1px solid {self._pal.border}; border-radius: 6px; }}"
        )
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(8)
        label, color_attr = _SEVERITY_BADGE.get(f.severity, ("INFO", "text_secondary"))
        badge = QLabel(label)
        badge.setFont(self._type.micro())
        color = getattr(self._pal, color_attr, self._pal.text_secondary)
        badge.setStyleSheet(
            f"color: {color}; letter-spacing: 1.4px; "
            f"border: 1px solid {color}; border-radius: 4px; padding: 1px 6px;"
        )
        head.addWidget(badge)
        title = QLabel(f.title)
        title.setFont(self._type.body())
        title.setStyleSheet(f"color: {self._pal.text_primary};")
        title.setWordWrap(True)
        head.addWidget(title, stretch=1)
        lay.addLayout(head)
        if f.detail:
            d = QLabel(f.detail)
            d.setFont(self._type.small())
            d.setStyleSheet(f"color: {self._pal.text_secondary};")
            d.setWordWrap(True)
            lay.addWidget(d)
        if f.fix_hint:
            hint = QLabel(f"Fix: {f.fix_hint}")
            hint.setFont(self._type.small())
            hint.setStyleSheet(f"color: {self._pal.accent};")
            hint.setWordWrap(True)
            lay.addWidget(hint)
        return wrap

    def _on_predictions(self) -> None:
        self._spawn("predictions", self._show_predictions)

    def _show_predictions(self, preds: List[MaintenancePrediction]) -> None:
        while self._predictions_box.count():
            item = self._predictions_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if not preds:
            self._predictions_box.addWidget(
                self._muted("All clear — no failures predicted in the next 12 months.")
            )
            return
        for p in preds:
            self._predictions_box.addWidget(self._prediction_row(p))

    def _prediction_row(self, p: MaintenancePrediction) -> QWidget:
        wrap = QFrame()
        color = {
            "critical": self._pal.coral,
            "warning":  self._pal.amber,
            "info":     self._pal.neon_blue,
        }.get(p.severity, self._pal.text_secondary)
        wrap.setStyleSheet(
            f"QFrame {{ background: {self._pal.bg_sunken}; "
            f"border: 1px solid {color}; border-radius: 6px; }}"
        )
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)
        title = QLabel(p.title)
        title.setFont(self._type.body())
        title.setStyleSheet(f"color: {color};")
        title.setWordWrap(True)
        lay.addWidget(title)
        d = QLabel(p.detail)
        d.setFont(self._type.small())
        d.setStyleSheet(f"color: {self._pal.text_secondary};")
        d.setWordWrap(True)
        lay.addWidget(d)
        if p.fix_hint:
            hint = QLabel(p.fix_hint)
            hint.setFont(self._type.small())
            hint.setStyleSheet(f"color: {self._pal.accent};")
            hint.setWordWrap(True)
            lay.addWidget(hint)
        return wrap
