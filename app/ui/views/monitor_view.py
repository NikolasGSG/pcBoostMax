"""Monitor view — larger, persistent real-time graphs + per-core grid."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...monitoring.performance_monitor import MetricSample
from ...utils.formatting import human_bytes
from ..theme.palette import Palette
from ..theme.typography import Typography
from ..viewmodels.monitor_vm import MonitorViewModel
from ..widgets.graph_widget import LineGraph
from ..widgets.fps_panel import FpsPanel
from ..widgets.section import Card, SectionHeader


class MonitorView(QWidget):
    def __init__(
        self,
        vm: MonitorViewModel,
        palette: Palette,
        typography: Typography,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._pal = palette
        self._type = typography

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        root = QVBoxLayout(container)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(18)

        root.addWidget(SectionHeader(
            "LIVE MONITOR", "Performance over the last two minutes",
            palette=palette, typography=typography,
        ))

        # FPS / frame-time panel — pulls directly from the controller's tracker
        self.fps_panel = FpsPanel(vm.controller.fps, palette, typography)
        root.addWidget(self.fps_panel)

        # Main combined graph
        graph_card = Card(palette=palette, padding=18)
        self.main_graph = LineGraph(palette, capacity=240)
        self.main_graph.setMinimumHeight(260)
        self.main_graph.add_series("cpu", palette.chart_cpu, fill=True)
        self.main_graph.add_series("ram", palette.chart_ram)
        self.main_graph.add_series("disk", palette.chart_disk)
        self.main_graph.set_value_suffix("%")

        legend = QHBoxLayout()
        legend.setSpacing(18)
        legend.addWidget(_LegendDot("CPU", palette.chart_cpu, typography))
        legend.addWidget(_LegendDot("RAM", palette.chart_ram, typography))
        legend.addWidget(_LegendDot("DISK", palette.chart_disk, typography))
        legend.addStretch()

        graph_card.body().addWidget(self.main_graph)
        graph_card.body().addLayout(legend)
        root.addWidget(graph_card)

        # Per-core grid
        root.addWidget(SectionHeader(
            "PER CORE", "CPU load per logical core",
            palette=palette, typography=typography,
            eyebrow_color=palette.chart_cpu,
        ))

        self.core_grid_container = Card(palette=palette, padding=18)
        self.core_grid = QGridLayout()
        self.core_grid.setContentsMargins(0, 0, 0, 0)
        self.core_grid.setHorizontalSpacing(12)
        self.core_grid.setVerticalSpacing(12)
        self.core_grid_container.body().addLayout(self.core_grid)
        self._core_bars: list[_CoreBar] = []
        root.addWidget(self.core_grid_container)

        # Throughput card (net + disk IO)
        tput = Card(palette=palette, padding=18)
        tput.body().addWidget(SectionHeader(
            "I/O", "Throughput",
            palette=palette, typography=typography,
            eyebrow_color=palette.chart_gpu,
        ))
        row = QHBoxLayout()
        row.setSpacing(16)
        self.net_label = _BigStat("Network", palette.chart_gpu, palette, typography)
        self.disk_label = _BigStat("Disk", palette.chart_disk, palette, typography)
        row.addWidget(self.net_label)
        row.addWidget(self.disk_label)
        tput.body().addLayout(row)
        root.addWidget(tput)

        root.addStretch()

        vm.sampled.connect(self._on_sample)

    # ------------------------------------------------------------------ handlers
    def _on_sample(self, sample: MetricSample) -> None:
        self.main_graph.push_values({
            "cpu": sample.cpu_percent,
            "ram": sample.ram_percent,
            "disk": sample.disk_percent,
        })

        # Ensure per-core bars exist
        if len(self._core_bars) != len(sample.per_core):
            self._rebuild_cores(len(sample.per_core))
        for bar, value in zip(self._core_bars, sample.per_core):
            bar.set_value(value)

        self.net_label.set_value(
            f"↓ {human_bytes(sample.net_down_bps)}/s",
            f"↑ {human_bytes(sample.net_up_bps)}/s",
        )
        self.disk_label.set_value(
            f"↓ {human_bytes(sample.disk_read_bps)}/s",
            f"↑ {human_bytes(sample.disk_write_bps)}/s",
        )

    def _rebuild_cores(self, count: int) -> None:
        # clear
        for bar in self._core_bars:
            bar.deleteLater()
        self._core_bars.clear()
        if count <= 0:
            return
        cols = 4 if count >= 8 else max(1, count)
        for i in range(count):
            bar = _CoreBar(i, self._pal, self._type)
            self._core_bars.append(bar)
            self.core_grid.addWidget(bar, i // cols, i % cols)


# ------------------------------------------------------------------ helper widgets
class _LegendDot(QWidget):
    def __init__(self, text: str, color: str, typography: Typography, parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        dot = QFrame()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
        lay.addWidget(dot)
        label = QLabel(text)
        f = typography.micro()
        label.setFont(f)
        label.setStyleSheet(f"color: {color}; letter-spacing: 2px;")
        lay.addWidget(label)


class _BigStat(QWidget):
    def __init__(self, title: str, accent: str, palette: Palette, typography: Typography, parent=None) -> None:
        super().__init__(parent)
        self._pal = palette
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        wrap = QFrame(self)
        wrap.setProperty("role", "card-inset")
        wrap_lay = QVBoxLayout(wrap)
        wrap_lay.setContentsMargins(16, 14, 16, 14)
        wrap_lay.setSpacing(4)

        self._title = QLabel(title.upper())
        self._title.setFont(typography.micro())
        self._title.setStyleSheet(f"color: {accent}; letter-spacing: 2px;")
        wrap_lay.addWidget(self._title)

        self._down = QLabel("↓ 0 B/s")
        self._down.setFont(typography.body_strong())
        wrap_lay.addWidget(self._down)

        self._up = QLabel("↑ 0 B/s")
        self._up.setFont(typography.body_strong())
        wrap_lay.addWidget(self._up)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(wrap)

    def set_value(self, down: str, up: str) -> None:
        self._down.setText(down)
        self._up.setText(up)


class _CoreBar(QWidget):
    """One bar for one core, painted custom to avoid QProgressBar's limited styling."""

    def __init__(self, index: int, palette: Palette, typography: Typography, parent=None) -> None:
        super().__init__(parent)
        self._pal = palette
        self._index = index
        self._value = 0.0
        self.setMinimumHeight(36)
        self.setFont(typography.small())

    def set_value(self, value: float) -> None:
        self._value = max(0.0, min(100.0, float(value)))
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: D401
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect()
        # Track
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._pal.bg_sunken))
        p.drawRoundedRect(r, 6, 6)
        # Fill proportional
        fill_w = int(r.width() * (self._value / 100.0))
        if fill_w > 0:
            color = self._pal.accent if self._value < 70 else self._pal.amber if self._value < 90 else self._pal.coral
            p.setBrush(QColor(color))
            p.drawRoundedRect(r.x(), r.y(), fill_w, r.height(), 6, 6)
        # Labels
        p.setPen(QColor(self._pal.text_primary))
        p.drawText(r.adjusted(10, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   f"Core {self._index}")
        p.setPen(QColor(self._pal.text_secondary))
        p.drawText(r.adjusted(10, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   f"{int(self._value)}%")
