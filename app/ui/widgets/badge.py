"""Small, coloured tag widgets (risk badge, category pill, kbd chip).

Badges are painted manually rather than composed from QLabel + QSS so the
colour can change in-flight without a stylesheet rebuild.
"""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import QWidget

from ..theme.palette import Palette


class Badge(QWidget):
    """Pill-shaped label. Can switch colours at runtime."""

    def __init__(
        self,
        text: str,
        *,
        palette: Palette,
        fg: str = "",
        bg: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._palette = palette
        self._text = text.upper()
        self._fg = QColor(fg or palette.text_primary)
        self._bg = QColor(bg or palette.border)
        self._font = QFont()
        self._font.setPointSize(8)
        self._font.setWeight(QFont.Weight.DemiBold)
        self._font.setCapitalization(QFont.Capitalization.AllUppercase)
        self._font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 112)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedHeight(20)
        self._recalc_width()

    def setText(self, text: str) -> None:
        self._text = text.upper()
        self._recalc_width()
        self.update()

    def setColors(self, fg: str, bg: str) -> None:
        self._fg = QColor(fg)
        self._bg = QColor(bg)
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(self.width(), 20)

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _e) -> None:  # noqa: D401
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._bg)
        p.drawRoundedRect(self.rect(), self.height() / 2, self.height() / 2)
        p.setPen(self._fg)
        p.setFont(self._font)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)

    # ------------------------------------------------------------------ helpers
    def _recalc_width(self) -> None:
        fm = QFontMetrics(self._font)
        w = fm.horizontalAdvance(self._text) + 20
        self.setFixedWidth(w)


def risk_badge(risk: str, palette: Palette) -> Badge:
    label = {"safe": "SAFE", "low": "LOW", "medium": "MEDIUM", "high": "HIGH"}.get(risk, risk.upper())
    return Badge(label, palette=palette, fg=palette.risk_color(risk), bg=palette.risk_dim(risk))


def impact_badge(impact: str, palette: Palette) -> Badge:
    colour = {
        "minor": (palette.text_secondary, palette.border),
        "moderate": ("#4AA8FF", "#10263F"),
        "significant": (palette.accent, palette.accent_dim),
    }.get(impact, (palette.text_secondary, palette.border))
    return Badge(f"IMPACT · {impact.upper()}", palette=palette, fg=colour[0], bg=colour[1])
