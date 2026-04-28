"""Tools view — Process Hunter, Network tools, Macros."""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from ...automation.macro_recorder import Macro, MacroLibrary, MacroRunResult, MacroRunner
from ...monitoring.network.dns_benchmark import DnsBenchmark, DnsResult
from ...monitoring.network.ping_tester import PingResult, PingTester
from ...system.process_tools import ProcessHunter, ProcessSummary
from ...utils.logger import get_logger
from ..theme.palette import Palette
from ..theme.typography import Typography
from ..widgets.banner import Banner
from ..widgets.section import Card, SectionHeader

log = get_logger("ui.tools")


# ----------------------------------------------------------------------
# Worker — runs blocking probes off the UI thread
# ----------------------------------------------------------------------
class _Probe(QObject):
    processes_ready = pyqtSignal(list)
    dns_ready = pyqtSignal(list)
    ping_ready = pyqtSignal(list)
    macro_done = pyqtSignal(object)
    finished = pyqtSignal()

    def __init__(self, mode: str, *, ctrl=None, macro: Optional[Macro] = None) -> None:
        super().__init__()
        self._mode = mode
        self._ctrl = ctrl
        self._macro = macro

    def run(self) -> None:
        try:
            if self._mode == "processes":
                hunter = ProcessHunter()
                self.processes_ready.emit(hunter.snapshot())
            elif self._mode == "dns":
                self.dns_ready.emit(DnsBenchmark().run())
            elif self._mode == "ping":
                self.ping_ready.emit(PingTester().run())
            elif self._mode == "macro" and self._macro is not None:
                runner: MacroRunner = self._ctrl.macro_runner
                self.macro_done.emit(runner.run(self._macro))
        except Exception:
            log.exception("Tools probe failed: %s", self._mode)
        finally:
            self.finished.emit()


# ----------------------------------------------------------------------
# Main view
# ----------------------------------------------------------------------
class ToolsView(QWidget):
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
            "TOOLS", "Power-user toolbox",
            palette=palette, typography=typography,
        ))
        root.addWidget(Banner(
            "Heavy actions (kill / suspend) require admin privileges.",
            palette=palette, typography=typography, role="warn",
        ))

        tabs = QTabWidget()
        tabs.addTab(self._build_hunter_tab(), "Process Hunter")
        tabs.addTab(self._build_network_tab(), "Network")
        tabs.addTab(self._build_macros_tab(), "Macros")
        root.addWidget(tabs, stretch=1)

    # -------------------------------------------------------------- helpers
    def _spawn(self, mode: str, on_ok, *, macro: Optional[Macro] = None) -> None:
        thread = QThread(self)
        worker = _Probe(mode, ctrl=self._ctrl, macro=macro)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        if mode == "processes":
            worker.processes_ready.connect(on_ok)
        elif mode == "dns":
            worker.dns_ready.connect(on_ok)
        elif mode == "ping":
            worker.ping_ready.connect(on_ok)
        elif mode == "macro":
            worker.macro_done.connect(on_ok)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._threads.remove(thread) if thread in self._threads else None)
        self._threads.append(thread)
        thread.start()

    def _muted(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(self._type.body())
        lbl.setStyleSheet(f"color: {self._pal.text_secondary};")
        lbl.setWordWrap(True)
        return lbl

    # -------------------------------------------------------------- Process Hunter
    def _build_hunter_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.addWidget(self._muted(
            "Top resource hogs running right now. Suggested action shown when we know the app."
        ), stretch=1)
        self._hunter_btn = QPushButton("Scan now")
        self._hunter_btn.setProperty("variant", "primary")
        self._hunter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hunter_btn.clicked.connect(self._on_hunt)
        head.addWidget(self._hunter_btn)
        lay.addLayout(head)

        self._hunter_table = QTableWidget(0, 5)
        self._hunter_table.setHorizontalHeaderLabels(
            ["Process", "CPU %", "RAM (MB)", "Net conns", "Suggestion"]
        )
        self._hunter_table.verticalHeader().setVisible(False)
        self._hunter_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._hunter_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._hunter_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for col in (1, 2, 3):
            self._hunter_table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self._hunter_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self._hunter_table.setAlternatingRowColors(True)
        self._hunter_table.setMinimumHeight(360)
        lay.addWidget(self._hunter_table, stretch=1)

        return tab

    def _on_hunt(self) -> None:
        self._hunter_btn.setEnabled(False)
        self._hunter_btn.setText("Scanning...")
        self._spawn("processes", self._show_processes)

    def _show_processes(self, items: List[ProcessSummary]) -> None:
        self._hunter_btn.setEnabled(True)
        self._hunter_btn.setText("Scan now")
        self._hunter_table.setRowCount(0)
        for s in items[:50]:
            row = self._hunter_table.rowCount()
            self._hunter_table.insertRow(row)
            self._hunter_table.setItem(row, 0, QTableWidgetItem(s.name or "?"))
            self._hunter_table.setItem(row, 1, QTableWidgetItem(f"{s.cpu_percent:.1f}"))
            self._hunter_table.setItem(row, 2, QTableWidgetItem(f"{s.ram_mb:.0f}"))
            self._hunter_table.setItem(row, 3, QTableWidgetItem(str(s.network_connections)))
            sug = s.suggestion or "—"
            sug_item = QTableWidgetItem(sug)
            if s.suggestion == "kill":
                sug_item.setForeground(self._color(self._pal.coral))
            elif s.suggestion == "suspend":
                sug_item.setForeground(self._color(self._pal.amber))
            elif s.suggestion == "lower_priority":
                sug_item.setForeground(self._color(self._pal.neon_blue))
            self._hunter_table.setItem(row, 4, sug_item)

    @staticmethod
    def _color(hex_str: str):
        from PyQt6.QtGui import QColor
        return QColor(hex_str)

    # -------------------------------------------------------------- Network
    def _build_network_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(14)

        # ----- DNS card
        dns = Card(palette=self._pal)
        dns_body = dns.body()
        dns_head = QHBoxLayout()
        t1 = QLabel("DNS resolver benchmark")
        t1.setFont(self._type.h2())
        t1.setStyleSheet(f"color: {self._pal.text_primary};")
        dns_head.addWidget(t1, stretch=1)
        self._dns_btn = QPushButton("Run benchmark")
        self._dns_btn.setProperty("variant", "primary")
        self._dns_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dns_btn.clicked.connect(self._on_dns)
        dns_head.addWidget(self._dns_btn)
        dns_body.addLayout(dns_head)
        dns_body.addWidget(self._muted(
            "Times eight popular public resolvers vs your current DNS. "
            "Switching can shave 10-40 ms off matchmaking."
        ))
        self._dns_box = QVBoxLayout()
        self._dns_box.setSpacing(4)
        dns_body.addLayout(self._dns_box)
        lay.addWidget(dns)

        # ----- Ping card
        ping = Card(palette=self._pal)
        ping_body = ping.body()
        ping_head = QHBoxLayout()
        t2 = QLabel("Game server ping")
        t2.setFont(self._type.h2())
        t2.setStyleSheet(f"color: {self._pal.text_primary};")
        ping_head.addWidget(t2, stretch=1)
        self._ping_btn = QPushButton("Test regions")
        self._ping_btn.setProperty("variant", "primary")
        self._ping_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ping_btn.clicked.connect(self._on_ping)
        ping_head.addWidget(self._ping_btn)
        ping_body.addLayout(ping_head)
        ping_body.addWidget(self._muted(
            "TCP handshake latency to common matchmaking endpoints. "
            "Pick the lowest region in your game's server menu."
        ))
        self._ping_box = QVBoxLayout()
        self._ping_box.setSpacing(4)
        ping_body.addLayout(self._ping_box)
        lay.addWidget(ping)

        lay.addStretch(1)
        return tab

    def _on_dns(self) -> None:
        self._dns_btn.setEnabled(False)
        self._dns_btn.setText("Testing...")
        self._spawn("dns", self._show_dns)

    def _show_dns(self, results: List[DnsResult]) -> None:
        self._dns_btn.setEnabled(True)
        self._dns_btn.setText("Run benchmark")
        while self._dns_box.count():
            item = self._dns_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if not results:
            self._dns_box.addWidget(self._muted("No reachable resolvers — check your network."))
            return
        for r in results[:8]:
            self._dns_box.addWidget(self._dns_row(r))

    def _dns_row(self, r: DnsResult) -> QWidget:
        wrap = QFrame()
        accent = self._pal.accent if r.is_current else self._pal.text_primary
        wrap.setStyleSheet(
            f"QFrame {{ background: {self._pal.bg_sunken}; "
            f"border: 1px solid {self._pal.border}; border-radius: 6px; }}"
        )
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        name = QLabel(r.label)
        name.setFont(self._type.body_strong())
        name.setStyleSheet(f"color: {accent};")
        lay.addWidget(name, stretch=1)

        if r.reachable:
            ms = QLabel(f"{r.mean_ms:.1f} ms")
            ms_color = (
                self._pal.accent if r.mean_ms < 25 else
                self._pal.neon_blue if r.mean_ms < 60 else
                self._pal.amber if r.mean_ms < 100 else self._pal.coral
            )
            ms.setStyleSheet(f"color: {ms_color};")
        else:
            ms = QLabel("unreachable")
            ms.setStyleSheet(f"color: {self._pal.text_tertiary};")
        ms.setFont(self._type.body_strong())
        lay.addWidget(ms)
        return wrap

    def _on_ping(self) -> None:
        self._ping_btn.setEnabled(False)
        self._ping_btn.setText("Pinging...")
        self._spawn("ping", self._show_ping)

    def _show_ping(self, results: List[PingResult]) -> None:
        self._ping_btn.setEnabled(True)
        self._ping_btn.setText("Test regions")
        while self._ping_box.count():
            item = self._ping_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if not results:
            self._ping_box.addWidget(self._muted("No regions reachable — check your network."))
            return
        for r in results[:12]:
            self._ping_box.addWidget(self._ping_row(r))

    def _ping_row(self, r: PingResult) -> QWidget:
        wrap = QFrame()
        wrap.setStyleSheet(
            f"QFrame {{ background: {self._pal.bg_sunken}; "
            f"border: 1px solid {self._pal.border}; border-radius: 6px; }}"
        )
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        name = QLabel(r.target.label)
        name.setFont(self._type.body_strong())
        name.setStyleSheet(f"color: {self._pal.text_primary};")
        lay.addWidget(name, stretch=1)

        if r.reachable:
            ms = QLabel(f"{r.mean_ms:.0f} ms")
            ms_color = {
                "excellent": self._pal.accent,
                "good": self._pal.neon_blue,
                "fair": self._pal.amber,
                "poor": self._pal.coral,
            }.get(r.quality_band(), self._pal.text_secondary)
            ms.setStyleSheet(f"color: {ms_color};")
        else:
            ms = QLabel("unreachable")
            ms.setStyleSheet(f"color: {self._pal.text_tertiary};")
        ms.setFont(self._type.body_strong())
        lay.addWidget(ms)
        return wrap

    # -------------------------------------------------------------- Macros
    def _build_macros_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(10)

        lay.addWidget(self._muted(
            "One-click macro chains: trim memory, tame background apps, apply a plan, "
            "boost — all wrapped in a named recipe."
        ))

        self._macros_box = QVBoxLayout()
        self._macros_box.setSpacing(8)
        lay.addLayout(self._macros_box)
        self._render_macros()

        lay.addStretch(1)
        return tab

    def _render_macros(self) -> None:
        while self._macros_box.count():
            item = self._macros_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        lib: MacroLibrary = self._ctrl.macro_library
        macros = lib.all()
        if not macros:
            self._macros_box.addWidget(self._muted("No macros defined yet."))
            return
        for m in macros:
            self._macros_box.addWidget(self._macro_row(m))

    def _macro_row(self, m: Macro) -> QWidget:
        wrap = QFrame()
        wrap.setStyleSheet(
            f"QFrame {{ background: {self._pal.bg_sunken}; "
            f"border: 1px solid {self._pal.border}; border-radius: 6px; }}"
        )
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        text = QVBoxLayout()
        text.setSpacing(2)
        t = QLabel(m.name)
        t.setFont(self._type.body_strong())
        t.setStyleSheet(f"color: {self._pal.text_primary};")
        text.addWidget(t)
        d = QLabel(m.description or f"{len(m.actions)} step macro")
        d.setFont(self._type.small())
        d.setStyleSheet(f"color: {self._pal.text_secondary};")
        d.setWordWrap(True)
        text.addWidget(d)
        lay.addLayout(text, stretch=1)

        run_btn = QPushButton("Run")
        run_btn.setProperty("variant", "primary")
        run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        run_btn.clicked.connect(lambda _checked=False, mac=m: self._run_macro(mac, run_btn))
        lay.addWidget(run_btn)
        return wrap

    def _run_macro(self, m: Macro, btn: QPushButton) -> None:
        btn.setEnabled(False)
        btn.setText("Running...")

        def _on_done(result: MacroRunResult) -> None:
            btn.setEnabled(True)
            ok_count = sum(1 for s in result.steps if s.ok)
            btn.setText(f"Done · {ok_count}/{len(result.steps)} OK")
        self._spawn("macro", _on_done, macro=m)
