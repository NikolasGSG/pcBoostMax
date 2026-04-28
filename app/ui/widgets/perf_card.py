"""Performance card — headline number + live mini-graph for a single metric.

Used on the dashboard for CPU, RAM, Disk, Network. Designed to be dense but
readable: eyebrow label, big value, subtitle detail, and a live fill graph.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from ..theme.palette import Palette
from ..theme.typography import Typography
from .graph_widget import LineGraph


class PerfCard(QFrame):
    """One headline metric card with a small sparkline inside."""

    def __init__(
        self,
        *,
        palette: Palette,
        typography: Typography,
        eyebrow: str,
        accent: str,
        unit: str = "%",
        value_format: str = "{:0.0f}{}",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PerfCard")
        self.setProperty("role", "card")
        self._pal = palette
        self._accent = accent
        self._unit = unit
        self._value_format = value_format

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(2)

        # Header row: coloured dot + eyebrow + optional trend label
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        dot = _Dot(accent)
        dot.setFixedSize(10, 10)
        header.addWidget(dot)
        self._eyebrow = QLabel(eyebrow.upper())
        self._eyebrow.setFont(typography.micro())
        self._eyebrow.setProperty("role", "eyebrow")
        self._eyebrow.setStyleSheet(f"color: {accent}; letter-spacing: 1.5px;")
        header.addWidget(self._eyebrow)
        header.addStretch()
        self._trend = QLabel("")
        self._trend.setFont(typography.small())
        self._trend.setProperty("role", "muted")
        self._trend.setStyleSheet(f"color: {palette.text_tertiary};")
        header.addWidget(self._trend)
        root.addLayout(header)

        # Big value
        self._value = QLabel(self._value_format.format(0, unit))
        big = typography.display()
        big.setPointSize(26)
        self._value.setFont(big)
        root.addWidget(self._value)

        # Subtitle detail (e.g. "12.3 GB / 32 GB  ·  8 modules @ 3200 MT/s")
        self._subtitle = QLabel("—")
        self._subtitle.setFont(typography.small())
        self._subtitle.setProperty("role", "muted")
        self._subtitle.setStyleSheet(f"color: {palette.text_secondary};")
        self._subtitle.setWordWrap(True)
        root.addWidget(self._subtitle)

        # Mini graph
        self._graph = LineGraph(palette, capacity=120)
        self._graph.setMinimumHeight(70)
        self._graph.set_show_current(False)
        self._graph.add_series("value", accent, fill=True)
        root.addWidget(self._graph)

    # ------------------------------------------------------------------ API
    def set_value(self, value: float, *, subtitle: Optional[str] = None, trend: Optional[str] = None) -> None:
        self._value.setText(self._value_format.format(value, self._unit))
        if subtitle is not None:
            self._subtitle.setText(subtitle)
        if trend is not None:
            self._trend.setText(trend)
        self._graph.push("value", float(value))

    def set_text_value(self, text: str, *, graph_value: float,
                       subtitle: Optional[str] = None, trend: Optional[str] = None) -> None:
        """Set an arbitrary headline string (e.g. "1.2 MB/s") while still
        driving the sparkline with a numeric value."""
        self._value.setText(text)
        if subtitle is not None:
            self._subtitle.setText(subtitle)
        if trend is not None:
            self._trend.setText(trend)
        self._graph.push("value", float(graph_value))

    def set_subtitle(self, text: str) -> None:
        self._subtitle.setText(text)


class _Dot(QFrame):
    """Small coloured circle with a soft outer glow."""

    def __init__(self, color: str, parent=None) -> None:
        super().__init__(parent)
        self._color = color
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, _e) -> None:  # noqa: D401
        from PyQt6.QtGui import QColor, QPainter, QRadialGradient

        from PyQt6.QtCore import QPointF

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect()
        grad = QRadialGradient(QPointF(r.center()), r.width() * 0.9)
        color = QColor(self._color)
        glow = QColor(color)
        glow.setAlpha(60)
        grad.setColorAt(0.0, color)
        grad.setColorAt(0.6, glow)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(r)
