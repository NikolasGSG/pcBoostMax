"""TickerBar — the live HUD strip across the top of the main window.

Subscribes to ``monitor.sample`` on the controller bus and continuously
updates a row of monospaced numerics. It's the "always-on" pulse of the
app — the user sees CPU%, RAM%, GPU%, FPS the whole time, regardless of
which view is open.

Each cell is a :class:`_TickerCell` painted with a tiny accent dot, an
all-caps label, and a big mono numeric. The cell turns lime/cyan/amber/
coral based on a per-metric pressure threshold.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...core.event_bus import EventBus
from ...monitoring.performance_monitor import MetricSample
from ..theme.palette import Palette
from ..theme.typography import Typography


@dataclass
class TickerMetric:
    """Declarative description of one cell."""

    key: str                                # e.g. "cpu"
    label: str                              # eyebrow text
    unit: str                               # "%" / "FPS" / "MB"
    extract: Callable[[MetricSample], float]
    warn_at: float = 70.0
    crit_at: float = 90.0


def _color_for(value: float, m: TickerMetric, pal: Palette) -> str:
    if value >= m.crit_at:
        return pal.coral
    if value >= m.warn_at:
        return pal.amber
    return pal.accent


class _TickerCell(QFrame):
    """One column in the ticker bar."""

    def __init__(
        self,
        metric: TickerMetric,
        palette: Palette,
        typography: Typography,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._metric = metric
        self._pal = palette
        self.setObjectName("TickerCell")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        col = QVBoxLayout(self)
        col.setContentsMargins(18, 8, 18, 8)
        col.setSpacing(2)

        # Top row: indicator dot + eyebrow label
        top = QHBoxLayout()
        top.setSpacing(8)
        self._dot = QLabel("●")
        df = QFont(typography.family)
        df.setPointSize(8)
        self._dot.setFont(df)
        self._dot.setStyleSheet(f"color: {palette.accent};")
        top.addWidget(self._dot)

        self._label = QLabel(metric.label)
        self._label.setFont(typography.eyebrow())
        self._label.setStyleSheet(f"color: {palette.text_tertiary};")
        top.addWidget(self._label)
        top.addStretch()
        col.addLayout(top)

        # Numeric row
        row = QHBoxLayout()
        row.setSpacing(4)
        row.setAlignment(Qt.AlignmentFlag.AlignBottom)
        self._value = QLabel("—")
        self._value.setFont(typography.mono_hud(20))
        self._value.setStyleSheet(f"color: {palette.text_primary};")
        row.addWidget(self._value)

        self._unit = QLabel(metric.unit)
        self._unit.setFont(typography.mono(10))
        self._unit.setStyleSheet(f"color: {palette.text_tertiary};")
        row.addWidget(self._unit, alignment=Qt.AlignmentFlag.AlignBottom)
        row.addStretch()
        col.addLayout(row)

    # ------------------------------------------------------------------ api
    def update_value(self, sample: MetricSample) -> None:
        try:
            v = float(self._metric.extract(sample))
        except Exception:
            return
        if self._metric.unit == "%":
            self._value.setText(f"{v:5.1f}".strip())
        elif self._metric.unit == "FPS":
            self._value.setText(f"{v:5.0f}".strip())
        else:
            self._value.setText(f"{v:5.1f}".strip())
        color = _color_for(v, self._metric, self._pal)
        self._dot.setStyleSheet(f"color: {color};")
        self._value.setStyleSheet(f"color: {color};")


class TickerBar(QFrame):
    """The full ticker — a horizontal row of cells across the window top."""

    def __init__(
        self,
        bus: EventBus,
        palette: Palette,
        typography: Typography,
        *,
        metrics: Optional[List[TickerMetric]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("TickerBar")
        self.setFixedHeight(54)
        self._pal = palette

        # Default metrics if caller didn't supply
        self._metrics = metrics or [
            TickerMetric("cpu", "CPU LOAD", "%",
                         lambda s: s.cpu_percent,
                         warn_at=70, crit_at=90),
            TickerMetric("ram", "MEMORY", "%",
                         lambda s: s.ram_percent,
                         warn_at=78, crit_at=92),
            TickerMetric("gpu", "GPU", "%",
                         lambda s: s.gpu_percent,
                         warn_at=80, crit_at=95),
            TickerMetric("disk", "DISK I/O", "MB/s",
                         lambda s: (s.disk_read_bps + s.disk_write_bps) / (1024 * 1024),
                         warn_at=80, crit_at=200),
            TickerMetric("net", "NETWORK", "MB/s",
                         lambda s: (s.net_recv_bps + s.net_sent_bps) / (1024 * 1024),
                         warn_at=20, crit_at=80),
        ]

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self._cells: dict[str, _TickerCell] = {}
        for m in self._metrics:
            cell = _TickerCell(m, palette, typography, parent=self)
            self._cells[m.key] = cell
            row.addWidget(cell, 1)

        # Internal signal so we can hop bus events onto the GUI thread
        # (PerformanceMonitor publishes from a worker).
        self._sample_received.connect(self._on_sample)
        bus.subscribe("monitor.sample", self._sample_received.emit)

    # -- thread-safe hop ----------------------------------------------------
    _sample_received = pyqtSignal(object)

    def _on_sample(self, sample: MetricSample) -> None:
        for cell in self._cells.values():
            cell.update_value(sample)
