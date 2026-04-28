"""Animated ring gauge — the hero visual on the dashboard hero card.

Paints a 270-degree arc with a smoothly animated value. Used for the
"Readiness score" at the top of the dashboard.
"""
from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from ..theme.palette import Palette


class RingGauge(QWidget):
    def __init__(
        self,
        palette: Palette,
        *,
        size: int = 180,
        label: str = "READINESS",
        suffix: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._pal = palette
        self._target = 0.0
        self._value = 0.0
        self._label = label
        self._suffix = suffix
        self.setFixedSize(size, size)
        self._anim = QPropertyAnimation(self, b"value", self)
        self._anim.setDuration(700)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ------------------------------------------------------------------ value property
    def _get_value(self) -> float:
        return self._value

    def _set_value(self, v: float) -> None:
        self._value = max(0.0, min(100.0, float(v)))
        self.update()

    value = pyqtProperty(float, _get_value, _set_value)

    def set_target(self, target: float) -> None:
        self._target = max(0.0, min(100.0, float(target)))
        self._anim.stop()
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(self._target)
        self._anim.start()

    def setLabel(self, text: str) -> None:
        self._label = text
        self.update()

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _e) -> None:  # noqa: D401
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(12, 12, -12, -12)
        pen_w = 12.0
        rect.adjust(pen_w / 2, pen_w / 2, -pen_w / 2, -pen_w / 2)

        track_pen = QPen(QColor(self._pal.border))
        track_pen.setWidthF(pen_w)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(track_pen)
        p.drawArc(rect, 225 * 16, -270 * 16)

        # Dynamic color based on value
        if self._value >= 70:
            color = self._pal.accent
        elif self._value >= 40:
            color = self._pal.amber
        else:
            color = self._pal.coral
        fill_pen = QPen(QColor(color))
        fill_pen.setWidthF(pen_w)
        fill_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(fill_pen)
        span = int(-270 * (self._value / 100.0) * 16)
        p.drawArc(rect, 225 * 16, span)

        # Centre text: value + label
        p.setPen(QColor(self._pal.text_primary))
        val_font = QFont(self.font())
        val_font.setPointSize(28)
        val_font.setWeight(QFont.Weight.DemiBold)
        p.setFont(val_font)
        p.drawText(
            QRectF(self.rect()).adjusted(0, -10, 0, -10),
            Qt.AlignmentFlag.AlignCenter,
            f"{int(self._value)}{self._suffix}",
        )

        p.setPen(QColor(self._pal.text_tertiary))
        lbl_font = QFont(self.font())
        lbl_font.setPointSize(8)
        lbl_font.setWeight(QFont.Weight.DemiBold)
        lbl_font.setCapitalization(QFont.Capitalization.AllUppercase)
        lbl_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 130)
        p.setFont(lbl_font)
        p.drawText(
            QRectF(self.rect()).adjusted(0, 30, 0, 30),
            Qt.AlignmentFlag.AlignCenter,
            self._label,
        )
