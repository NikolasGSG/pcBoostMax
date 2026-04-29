"""GameBoostApex brand mark — custom-painted hex bolt + wordmark.

This is the logo that sits at the top of the sidebar. It's drawn entirely
with QPainter so it scales perfectly at any DPI, and so we never need to
ship a bitmap asset that would be a giveaway "AI-generated" SaaS-style
logo. The mark is:

* A hexagonal frame with two missing edges (top-right + bottom-left),
  giving it a "speed-cut" diagonal feel.
* A lightning bolt cut into the centre, painted in lime.
* A thin cyan rule underneath the wordmark.

Pure-paint rendering also means we can theme it: pass an ``accent`` colour
to recolour the bolt for, say, an "Elite" build.
"""
from __future__ import annotations

import math
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PyQt6.QtWidgets import QSizePolicy, QWidget

from ..theme.palette import Palette
from ..theme.typography import Typography


class BrandMark(QWidget):
    """Hex bolt + 'GAMEBOOSTAPEX' / 'APEX' wordmark."""

    def __init__(
        self,
        palette: Palette,
        typography: Typography,
        *,
        wordmark: str = "GAMEBOOSTAPEX",
        sub: str = "APEX",
        accent: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._pal = palette
        self._type = typography
        self._wordmark = wordmark
        self._sub = sub
        self._accent = accent or palette.accent
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()
        cy = rect.center().y()
        size = min(36, rect.height() - 8)
        cx = rect.left() + 8 + size / 2

        # ---- Hex frame (two arms cut for the speed-cut look) --------------
        hex_pts = []
        for i in range(6):
            ang = math.radians(60 * i - 30)   # flat-top
            hex_pts.append(QPointF(
                cx + (size / 2) * math.cos(ang),
                cy + (size / 2) * math.sin(ang),
            ))
        # Faint full hex in border colour
        p.setPen(QPen(QColor(self._pal.border_hairline), 1.4))
        p.setBrush(QColor(self._pal.bg_sunken))
        p.drawPolygon(QPolygonF(hex_pts))

        # Two emphasised arms in accent (top-left and bottom-right, gives
        # the diagonal "speed cut" silhouette)
        p.setPen(QPen(QColor(self._accent), 2.0))
        for a, b in ((0, 1), (3, 4)):
            p.drawLine(hex_pts[a], hex_pts[b])

        # ---- Bolt -------------------------------------------------------
        bolt = QPainterPath()
        s = size * 0.42
        bolt.moveTo(cx + s * 0.05, cy - s)
        bolt.lineTo(cx - s * 0.55, cy + s * 0.10)
        bolt.lineTo(cx - s * 0.05, cy + s * 0.10)
        bolt.lineTo(cx - s * 0.20, cy + s)
        bolt.lineTo(cx + s * 0.55, cy - s * 0.10)
        bolt.lineTo(cx + s * 0.10, cy - s * 0.10)
        bolt.closeSubpath()

        # Glow (very faint)
        glow = QColor(self._accent)
        glow.setAlpha(70)
        p.setPen(QPen(glow, 4.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(bolt)
        # Solid fill
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._accent))
        p.drawPath(bolt)

        # ---- Wordmark ----------------------------------------------------
        text_x = cx + size / 2 + 12
        title_font = QFont(self._type.display_family, 14)
        title_font.setBold(True)
        title_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
        title_font.setCapitalization(QFont.Capitalization.AllUppercase)
        p.setFont(title_font)
        p.setPen(QColor(self._pal.text_primary))
        p.drawText(
            int(text_x), int(cy - 12),
            int(rect.width() - text_x - 8), 18,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self._wordmark,
        )

        # Sub-label, tiny tracked caps in cyan
        sub_font = QFont(self._type.family, 8)
        sub_font.setBold(True)
        sub_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 200)
        sub_font.setCapitalization(QFont.Capitalization.AllUppercase)
        p.setFont(sub_font)
        p.setPen(QColor(self._pal.neon_blue))
        p.drawText(
            int(text_x), int(cy + 6),
            int(rect.width() - text_x - 8), 14,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self._sub,
        )

        # Hairline rule under the wordmark
        p.setPen(QPen(QColor(self._pal.border_hairline), 1))
        p.drawLine(
            int(text_x), int(cy + 20),
            int(text_x + 52), int(cy + 20),
        )
