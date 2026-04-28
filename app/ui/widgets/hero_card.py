"""Dashboard hero card.

A full-width banner anchored by the readiness :class:`RingGauge` on the
left, a greeting headline in the centre, and a primary action ("Analyze"
or "Activate Game Mode") on the right.
"""
from __future__ import annotations

import datetime
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from ..theme.palette import Palette
from ..theme.typography import Typography
from .ring_gauge import RingGauge


class HeroCard(QFrame):
    primary_clicked = pyqtSignal()
    secondary_clicked = pyqtSignal()

    def __init__(
        self,
        *,
        palette: Palette,
        typography: Typography,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._pal = palette
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(220)

        root = QHBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(28)

        # Left: gauge
        self.gauge = RingGauge(palette, size=170, label="READINESS")
        root.addWidget(self.gauge, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Middle: greeting + headline + tagline
        middle = QVBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(6)

        self._eyebrow = QLabel(self._time_of_day_greeting())
        self._eyebrow.setFont(typography.micro())
        self._eyebrow.setStyleSheet(f"color: {palette.accent}; letter-spacing: 2.2px;")
        middle.addWidget(self._eyebrow)

        self._headline = QLabel("Your machine is ready to play.")
        h_font = typography.display()
        h_font.setPointSize(24)
        self._headline.setFont(h_font)
        self._headline.setWordWrap(True)
        middle.addWidget(self._headline)

        self._tagline = QLabel(
            "Run a fresh analysis to surface bottlenecks, review suggested "
            "optimizations, or jump straight into Game Mode."
        )
        self._tagline.setWordWrap(True)
        self._tagline.setFont(typography.body())
        self._tagline.setStyleSheet(f"color: {palette.text_secondary};")
        middle.addWidget(self._tagline)

        # Meta row: last-analyzed chip + mini hint chips
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 8, 0, 0)
        meta_row.setSpacing(8)
        self._chip_last = _Chip("· Last analysis: never", palette, typography)
        self._chip_gm = _Chip("· Game Mode: idle", palette, typography)
        meta_row.addWidget(self._chip_last)
        meta_row.addWidget(self._chip_gm)
        meta_row.addStretch()
        middle.addLayout(meta_row)

        middle.addSpacing(6)

        # Buttons
        row = QHBoxLayout()
        row.setSpacing(10)
        self.primary = QPushButton("Analyze System")
        self.primary.setProperty("variant", "primary")
        self.primary.setCursor(Qt.CursorShape.PointingHandCursor)
        self.primary.clicked.connect(self.primary_clicked)

        self.secondary = QPushButton("Activate Game Mode")
        self.secondary.setProperty("variant", "violet")
        self.secondary.setCursor(Qt.CursorShape.PointingHandCursor)
        self.secondary.clicked.connect(self.secondary_clicked)

        row.addWidget(self.primary)
        row.addWidget(self.secondary)
        row.addStretch()
        middle.addLayout(row)

        root.addLayout(middle, 1)

    # ------------------------------------------------------------------ API
    def set_readiness(self, score: float) -> None:
        self.gauge.set_target(score)
        # Switch headline wording based on score
        if score >= 80:
            self._headline.setText("Your machine is ready to play.")
        elif score >= 60:
            self._headline.setText("Your machine is in good shape — a few wins left.")
        elif score >= 40:
            self._headline.setText("Your machine could use some tuning.")
        else:
            self._headline.setText("Several fixable issues are holding you back.")

    def set_last_analysis(self, label: str) -> None:
        self._chip_last.setText(f"· Last analysis: {label}")

    def set_game_mode_state(self, active: bool, detail: str = "") -> None:
        if active:
            self._chip_gm.setText(f"· Game Mode: active {detail}".rstrip())
            self._chip_gm.setAccent(self._pal.violet)
        else:
            self._chip_gm.setText("· Game Mode: idle")
            self._chip_gm.setAccent(self._pal.text_tertiary)

    def refresh_greeting(self) -> None:
        self._eyebrow.setText(self._time_of_day_greeting())

    @staticmethod
    def _time_of_day_greeting() -> str:
        h = datetime.datetime.now().hour
        if 5 <= h < 12:
            return "GOOD MORNING"
        if 12 <= h < 18:
            return "GOOD AFTERNOON"
        if 18 <= h < 22:
            return "GOOD EVENING"
        return "WELCOME BACK"

    # ------------------------------------------------------------------ paint
    def paintEvent(self, event) -> None:  # noqa: D401
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect()
        # Two-tone diagonal gradient for extra polish (distinct from flat cards)
        grad = QLinearGradient(r.topLeft().toPointF(), r.bottomRight().toPointF())
        grad.setColorAt(0.0, QColor(self._pal.bg_elevated))
        grad.setColorAt(1.0, QColor(self._pal.bg_surface))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(r, 16, 16)
        # Thin accent line on the left edge
        accent = QColor(self._pal.accent)
        accent.setAlpha(80)
        p.setBrush(accent)
        p.drawRoundedRect(0, 0, 3, r.height(), 2, 2)
        super().paintEvent(event)


class _Chip(QLabel):
    """Small muted text chip used in the hero meta row."""

    def __init__(self, text: str, palette: Palette, typography: Typography, parent=None) -> None:
        super().__init__(text, parent)
        self._pal = palette
        self.setFont(typography.small())
        self._accent = palette.text_tertiary
        self._apply_style()

    def setAccent(self, color: str) -> None:
        self._accent = color
        self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"color: {self._accent}; background: transparent; padding: 2px 4px;"
        )
