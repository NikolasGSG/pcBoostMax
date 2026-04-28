"""iOS-style toggle switch with animated knob — a complete replacement for QCheckBox.

Painted from scratch so it matches the Nocturne palette exactly. Uses
``QPropertyAnimation`` on a private ``_position`` property to tween the knob
between off (0.0) and on (1.0).
"""
from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QAbstractButton

from ..theme.palette import Palette


class ToggleSwitch(QAbstractButton):
    """A painted, animated toggle. Same API surface as QCheckBox.

    NOTE: do NOT redeclare ``toggled`` here. The base ``QAbstractButton``
    already provides a ``toggled(bool)`` signal that fires on every state
    change (click, setChecked). Shadowing it with a new ``pyqtSignal``
    silently breaks every external connection — that was the cause of all
    the Settings toggles appearing to "do nothing".
    """

    def __init__(self, palette: Palette, parent=None, *, width: int = 44, height: int = 24) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._palette = palette
        self._w = width
        self._h = height
        self._position = 0.0
        self._anim = QPropertyAnimation(self, b"position", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        # Base class emits ``toggled`` on every state change — drive the
        # animation off the same signal so callers can simply do
        # ``toggle.toggled.connect(handler)``.
        self.toggled.connect(self._on_toggled)

    def sizeHint(self) -> QSize:  # noqa: D401
        return QSize(self._w, self._h)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    # ------------------------------------------------------------------ property
    def _get_position(self) -> float:
        return self._position

    def _set_position(self, value: float) -> None:
        self._position = max(0.0, min(1.0, float(value)))
        self.update()

    position = pyqtProperty(float, _get_position, _set_position)

    # ------------------------------------------------------------------ events
    def _on_toggled(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._position)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def setChecked(self, checked: bool) -> None:  # noqa: D401
        super().setChecked(checked)
        self._position = 1.0 if checked else 0.0
        self.update()

    # ------------------------------------------------------------------ painting
    def paintEvent(self, _event) -> None:  # noqa: D401
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w, h = self.width(), self.height()
        radius = h / 2.0

        # Track interpolation off → on
        off = QColor(self._palette.border_strong)
        on = QColor(self._palette.accent)
        track = QColor.fromRgbF(
            off.redF() + (on.redF() - off.redF()) * self._position,
            off.greenF() + (on.greenF() - off.greenF()) * self._position,
            off.blueF() + (on.blueF() - off.blueF()) * self._position,
        )
        if not self.isEnabled():
            track.setAlpha(80)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(0, 0, w, h, radius, radius)

        # Knob
        knob_margin = 2
        knob_diameter = h - knob_margin * 2
        travel = w - knob_diameter - knob_margin * 2
        x = knob_margin + travel * self._position
        knob_color = QColor("#0A0E14") if self._position > 0.5 else QColor("#F2F6FB")
        painter.setBrush(knob_color)
        painter.drawEllipse(QRect(int(x), knob_margin, knob_diameter, knob_diameter))
