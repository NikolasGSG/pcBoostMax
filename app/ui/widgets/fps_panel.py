"""Live FPS panel — big mono numerals + 1% / 0.1% lows + frame-time graph.

Shown on the Monitor view. Polls :class:`FpsTracker` once per second on a
``QTimer`` so the panel works regardless of whether PresentMon or the GPU
proxy is feeding data.

Layout::

    +---------- HudFrame ----------+
    | EYEBROW                      |
    | 144  fps    │  AVG  142.3    |
    |             │  1%LOW  92.0   |
    |             │  0.1%LOW 71.0  |
    | [frame time graph]           |
    +------------------------------+
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...overlay.fps_tracker import FpsTracker
from ..theme.palette import Palette
from ..theme.typography import Typography
from .graph_widget import LineGraph
from .hex_panel import HudFrame


class FpsPanel(HudFrame):
    """Live FPS readout with averages, lows and a frame-time graph."""

    def __init__(
        self,
        tracker: FpsTracker,
        palette: Palette,
        typography: Typography,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            palette,
            corner=22,
            thickness=2,
            accent=palette.accent,
            label="GB-FPS",
            with_hex=True,
            parent=parent,
        )
        self._tracker = tracker
        self._pal = palette
        self._type = typography
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(280)

        body = self.content_layout()

        # Eyebrow + title
        eyebrow = QLabel("REALTIME FPS")
        eyebrow.setFont(typography.eyebrow())
        eyebrow.setStyleSheet(f"color: {palette.accent};")
        body.addWidget(eyebrow)

        title = QLabel("Frame-rate")
        title.setFont(typography.display_h1())
        title.setStyleSheet(f"color: {palette.text_primary};")
        body.addWidget(title)

        # Numerics row
        row = QHBoxLayout()
        row.setSpacing(28)

        # Hero current FPS
        hero = QVBoxLayout()
        hero.setSpacing(2)
        hero.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._fps_value = QLabel("—")
        f = typography.hero()
        f.setPointSize(56)
        self._fps_value.setFont(f)
        self._fps_value.setStyleSheet(f"color: {palette.accent};")
        self._fps_value.setMinimumWidth(120)
        hero.addWidget(self._fps_value)
        unit = QLabel("FPS")
        unit.setFont(typography.eyebrow())
        unit.setStyleSheet(f"color: {palette.text_tertiary};")
        hero.addWidget(unit)
        row.addLayout(hero)

        # Divider
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet(f"background-color: {palette.border_hairline};")
        row.addWidget(divider)

        # Stats column — explicit per-row HBoxes (one row = label + value).
        # We compute a guaranteed row height from the value-font metrics so
        # adjacent rows can never overlap, regardless of the hero column's
        # height or the embedded mono font's reported sizeHint.
        stats = QVBoxLayout()
        stats.setSpacing(10)
        stats.setContentsMargins(0, 6, 0, 6)

        value_metrics = QFontMetrics(typography.mono_hud(18))
        row_height = value_metrics.height() + 6

        self._avg       = self._stat_pair("AVG (60s)",  palette.neon_blue, typography)
        self._low_1     = self._stat_pair("1% LOW",     palette.amber,     typography)
        self._low_01    = self._stat_pair("0.1% LOW",   palette.coral,     typography)
        self._frametime = self._stat_pair("FRAME TIME", palette.violet,    typography, unit="ms")

        for label_w, value_w in (self._avg, self._low_1, self._low_01, self._frametime):
            stats.addLayout(self._build_stat_row(label_w, value_w, row_height))

        stats.addStretch(1)
        row.addLayout(stats, 1)

        body.addLayout(row)

        # Frame-time graph
        body.addSpacing(8)
        ft_label = QLabel("FRAME TIME (ms)")
        ft_label.setFont(typography.eyebrow())
        ft_label.setStyleSheet(f"color: {palette.text_tertiary};")
        body.addWidget(ft_label)
        self._graph = LineGraph(palette, capacity=180)
        self._graph.add_series("ft", palette.violet, fill=True)
        self._graph.set_value_suffix("ms")
        self._graph.setMinimumHeight(120)
        body.addWidget(self._graph)

        # Source caption
        self._source_caption = QLabel(self._source_text())
        self._source_caption.setFont(typography.small())
        self._source_caption.setStyleSheet(f"color: {palette.text_tertiary};")
        body.addWidget(self._source_caption)

        # Tick the panel once a second
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        QTimer.singleShot(50, self._refresh)

    # ------------------------------------------------------------------ helpers
    def _stat_pair(self, label: str, color: str,
                   typography: Typography, *, unit: str = "fps"):
        l = QLabel(label)
        l.setFont(typography.eyebrow())
        l.setStyleSheet(f"color: {self._pal.text_tertiary};")
        l.setMinimumWidth(86)
        l.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        v = QLabel(f"— {unit}")
        v.setFont(typography.mono_hud(18))
        v.setStyleSheet(f"color: {color};")
        v.setProperty("_unit", unit)
        v.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        v.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        return l, v

    def _build_stat_row(self, label_w: QLabel, value_w: QLabel, row_height: int) -> QHBoxLayout:
        """Pair a label + value in a single horizontal row with a guaranteed height."""
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(14)
        label_w.setMinimumHeight(row_height)
        value_w.setMinimumHeight(row_height)
        h.addWidget(label_w)
        h.addWidget(value_w, stretch=1)
        return h

    def _set_stat(self, pair, value: float) -> None:
        unit = pair[1].property("_unit") or "fps"
        if unit == "ms":
            pair[1].setText(f"{value:.2f} {unit}")
        else:
            pair[1].setText(f"{value:.1f} {unit}")

    def _source_text(self) -> str:
        src = self._tracker.source
        if src == "presentmon":
            return "Source · PresentMon (true per-frame timing)"
        if src == "proxy":
            return "Source · GPU activity proxy. Install PresentMon for true per-frame FPS."
        return "Source · idle"

    # ------------------------------------------------------------------ refresh
    def _refresh(self) -> None:
        latest = self._tracker.latest()
        stats = self._tracker.percentile_stats(window_seconds=60)

        if latest is None or latest.fps <= 0:
            self._fps_value.setText("—")
            self._set_stat(self._avg, 0.0)
            self._set_stat(self._low_1, 0.0)
            self._set_stat(self._low_01, 0.0)
            self._set_stat(self._frametime, 0.0)
            return

        self._fps_value.setText(f"{latest.fps:5.0f}".strip())
        self._set_stat(self._avg, stats["avg"])
        self._set_stat(self._low_1, stats["low_1pct"])
        self._set_stat(self._low_01, stats["low_0p1pct"])
        self._set_stat(self._frametime, latest.frametime_ms)
        self._graph.push_values({"ft": latest.frametime_ms})

        self._source_caption.setText(self._source_text())
