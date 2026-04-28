"""Lightweight real-time line graph.

Painted with QPainter directly — no pyqtgraph dependency needed for this
use case, which keeps the PyInstaller bundle smaller and rendering snappy.
Supports multiple series, smooth curves, gridlines, and a soft fill under
the primary series.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

from ..theme.palette import Palette


@dataclass
class Series:
    name: str
    color: str
    values: Deque[float]
    fill: bool = False

    @classmethod
    def create(cls, name: str, color: str, capacity: int, fill: bool = False) -> "Series":
        return cls(name=name, color=color, values=deque(maxlen=capacity), fill=fill)


class LineGraph(QWidget):
    """0..100% line graph with a grid, optional fill, and a current-value label."""

    def __init__(
        self,
        palette: Palette,
        *,
        capacity: int = 120,
        y_min: float = 0.0,
        y_max: float = 100.0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._pal = palette
        self._capacity = capacity
        self._y_min = y_min
        self._y_max = y_max
        self._series: List[Series] = []
        self._value_suffix = "%"
        self._show_current = True
        self.setMinimumHeight(80)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    # ------------------------------------------------------------------ API
    def add_series(self, name: str, color: str, *, fill: bool = False) -> Series:
        series = Series.create(name=name, color=color, capacity=self._capacity, fill=fill)
        self._series.append(series)
        return series

    def push(self, series_name: str, value: float) -> None:
        for s in self._series:
            if s.name == series_name:
                s.values.append(max(self._y_min, min(self._y_max, value)))
                break
        self.update()

    def push_values(self, mapping: dict[str, float]) -> None:
        for s in self._series:
            if s.name in mapping:
                s.values.append(max(self._y_min, min(self._y_max, mapping[s.name])))
        self.update()

    def clear(self) -> None:
        for s in self._series:
            s.values.clear()
        self.update()

    def set_value_suffix(self, suffix: str) -> None:
        self._value_suffix = suffix
        self.update()

    def set_show_current(self, show: bool) -> None:
        self._show_current = show
        self.update()

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _e) -> None:  # noqa: D401
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        r = QRectF(self.rect())
        r.adjust(8, 8, -8, -8)

        # Background well
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._pal.bg_sunken))
        p.drawRoundedRect(r, 10, 10)

        # Gridlines (horizontal at 25/50/75)
        grid_pen = QPen(QColor(self._pal.chart_grid))
        grid_pen.setWidthF(1.0)
        grid_pen.setStyle(Qt.PenStyle.DotLine)
        p.setPen(grid_pen)
        for frac in (0.25, 0.5, 0.75):
            y = r.y() + r.height() * frac
            p.drawLine(QPointF(r.x() + 8, y), QPointF(r.right() - 8, y))

        # Each series
        for series in self._series:
            self._draw_series(p, r, series)

        # Current-value label (top-right) — picks the first series by default
        if self._show_current and self._series and self._series[0].values:
            latest = self._series[0].values[-1]
            text = f"{latest:0.0f}{self._value_suffix}"
            font = p.font()
            font.setPointSizeF(font.pointSizeF() + 2)
            font.setBold(True)
            p.setFont(font)
            p.setPen(QColor(self._pal.text_primary))
            p.drawText(
                QRectF(r.x() + 4, r.y() + 4, r.width() - 8, 22),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                text,
            )

    def _draw_series(self, p: QPainter, r: QRectF, series: Series) -> None:
        values = list(series.values)
        if len(values) < 2:
            return
        color = QColor(series.color)

        # Map value -> point
        def _point(i: int, v: float) -> QPointF:
            x = r.x() + (i / max(1, self._capacity - 1)) * r.width()
            # Clamp, with a touch of padding so the line isn't glued to the top
            norm = (v - self._y_min) / max(1e-6, (self._y_max - self._y_min))
            y = r.bottom() - norm * (r.height() - 4) - 2
            return QPointF(x, y)

        # Shift to right-align when buffer not full yet
        offset = self._capacity - len(values)
        pts = [_point(offset + i, v) for i, v in enumerate(values)]

        # Fill under curve
        if series.fill:
            fill_path = QPainterPath()
            fill_path.moveTo(QPointF(pts[0].x(), r.bottom() - 2))
            for pt in pts:
                fill_path.lineTo(pt)
            fill_path.lineTo(QPointF(pts[-1].x(), r.bottom() - 2))
            fill_path.closeSubpath()
            grad = QLinearGradient(QPointF(r.x(), r.y()), QPointF(r.x(), r.bottom()))
            top = QColor(color)
            top.setAlphaF(0.28)
            bot = QColor(color)
            bot.setAlphaF(0.02)
            grad.setColorAt(0.0, top)
            grad.setColorAt(1.0, bot)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(grad)
            p.drawPath(fill_path)

        # Line
        line_pen = QPen(color)
        line_pen.setWidthF(2.0)
        line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(line_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(pts[0])
        for pt in pts[1:]:
            path.lineTo(pt)
        p.drawPath(path)
