"""Apex hardware-style custom-painted shell components.

These are the *signature* visuals of the GameBoostApex v2 redesign — the bits
that make the app stop looking like another generic "Tailwind on QSS"
dashboard and start looking like Razer Synapse / Logitech G HUB.

Three primitives:

* :class:`HexBackground`   — paints a faint hexagonal grid behind a panel.
                             Stack it inside a card to add "hardware" texture.
* :class:`BracketCard`     — a card whose corners are drawn as four
                             L-shaped lime brackets instead of a continuous
                             border. Used for the hero tiles.
* :class:`HudFrame`        — combines the two: hex grid + bracket corners +
                             optional scan-line + corner ID glyph.

Everything is painted via :class:`QPainter` so it scales to any DPI and
doesn't depend on bitmap assets. ``palette`` is the only required
dependency.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PyQt6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout, QWidget

from ..theme.palette import Palette


def _q(hex_color: str, alpha: int = 255) -> QColor:
    c = QColor(hex_color)
    c.setAlpha(alpha)
    return c


# ---------------------------------------------------------------------------
# HexBackground
# ---------------------------------------------------------------------------

class HexBackground(QWidget):
    """Renders a flat-top hex grid as a subtle backdrop.

    Drop this widget *inside* a parent layout where you want texture.
    It paints transparently outside the cells, so it works as a layered
    backdrop. Set the ``cell_size`` for density and ``intensity`` for how
    visible the grid lines are (0..255).
    """

    def __init__(
        self,
        palette: Palette,
        *,
        cell_size: int = 22,
        intensity: int = 28,
        accent_dot_chance: float = 0.025,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._pal = palette
        self._cell = cell_size
        self._intensity = intensity
        self._dot_chance = accent_dot_chance
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        line = _q(self._pal.hex_line, self._intensity)
        line_hot = _q(self._pal.hex_line_hot, min(255, self._intensity + 25))
        accent = _q(self._pal.accent, 70)

        pen = QPen(line, 1.0)
        pen.setCosmetic(True)
        # CRITICAL: explicitly disable fill or every hex draws as a solid lime
        # blob (the default Qt brush is opaque). This was the root cause of
        # the "green wall" on the Monitor view.
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(pen)

        s = self._cell
        # flat-top hex geometry
        w = s * 2
        h = math.sqrt(3) * s
        col_step = w * 0.75
        row_step = h

        rect = self.rect()
        cols = int(rect.width() / col_step) + 2
        rows = int(rect.height() / row_step) + 2

        # Use a deterministic pseudo-random sequence so dots don't reflow
        # on every paint; cheap LCG seeded by widget id.
        seed = (id(self) ^ 0xA5A5) & 0xFFFFFFFF

        def _rand() -> float:
            nonlocal seed
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            return seed / 0x7FFFFFFF

        for r in range(-1, rows):
            for c in range(-1, cols):
                cx = c * col_step
                cy = r * row_step + (h / 2 if c % 2 else 0)
                hex_poly = self._hex(cx, cy, s)
                # Random subset gets a hotter line to add texture variation
                if _rand() < 0.18:
                    p.setPen(QPen(line_hot, 1.0))
                else:
                    p.setPen(pen)
                # Always paint as outline only.
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPolygon(hex_poly)

                # Sprinkle lime accent dots — must reset the brush to NoBrush
                # afterwards so the next polygon doesn't fill itself in.
                if _rand() < self._dot_chance:
                    p.setBrush(QBrush(accent))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(QPointF(cx, cy), 1.2, 1.2)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(pen)

    @staticmethod
    def _hex(cx: float, cy: float, size: float) -> QPolygonF:
        pts = []
        for i in range(6):
            ang = math.radians(60 * i)
            pts.append(QPointF(cx + size * math.cos(ang),
                               cy + size * math.sin(ang)))
        return QPolygonF(pts)


# ---------------------------------------------------------------------------
# BracketCard
# ---------------------------------------------------------------------------

class BracketCard(QFrame):
    """A frame whose corners are drawn as four lime L-brackets.

    The widget *also* has a near-black fill and a faint hairline border
    for the body, so it works as a regular content card while picking up
    the hardware-HUD presence.

    Public properties:
    * ``corner`` — bracket arm length in px (default 18)
    * ``thickness`` — bracket stroke width (default 2)
    * ``accent`` — bracket colour (defaults to ``palette.accent``)
    * ``label`` — optional 2–4 character ID label rendered top-left
    """

    def __init__(
        self,
        palette: Palette,
        *,
        corner: int = 20,
        thickness: int = 2,
        accent: Optional[str] = None,
        label: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._pal = palette
        self._corner = corner
        self._thickness = thickness
        self._accent = accent or palette.accent
        self._label = label
        self.setProperty("role", "hex-card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    # -- API -----------------------------------------------------------------
    def set_accent(self, color: str) -> None:
        if color != self._accent:
            self._accent = color
            self.update()

    def set_label(self, text: str) -> None:
        if text != self._label:
            self._label = text
            self.update()

    # -- paint ---------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        c = self._corner
        t = self._thickness
        accent = QColor(self._accent)

        pen = QPen(accent, t)
        pen.setCapStyle(Qt.PenCapStyle.SquareCap)
        p.setPen(pen)

        # Top-left
        p.drawLine(rect.left(), rect.top(), rect.left() + c, rect.top())
        p.drawLine(rect.left(), rect.top(), rect.left(), rect.top() + c)
        # Top-right
        p.drawLine(rect.right() - c, rect.top(), rect.right(), rect.top())
        p.drawLine(rect.right(), rect.top(), rect.right(), rect.top() + c)
        # Bottom-left
        p.drawLine(rect.left(), rect.bottom() - c, rect.left(), rect.bottom())
        p.drawLine(rect.left(), rect.bottom(), rect.left() + c, rect.bottom())
        # Bottom-right
        p.drawLine(rect.right() - c, rect.bottom(), rect.right(), rect.bottom())
        p.drawLine(rect.right(), rect.bottom() - c, rect.right(), rect.bottom())

        # Optional ID label at top-left (e.g. "GB-01")
        if self._label:
            p.setPen(QColor(self._pal.text_tertiary))
            f = self.font()
            f.setPointSize(8)
            f.setBold(True)
            f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 130)
            p.setFont(f)
            p.drawText(
                rect.left() + c + 6,
                rect.top() + 4,
                200, 14,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                self._label.upper(),
            )


# ---------------------------------------------------------------------------
# HudFrame
# ---------------------------------------------------------------------------

class HudFrame(QFrame):
    """Composite: BracketCard + faint hex backdrop + optional scan-line.

    Use as the root of a "hero" panel: a custom-painted shell whose only
    job is to be the visual anchor. Any content goes into ``content_layout``.
    """

    def __init__(
        self,
        palette: Palette,
        *,
        corner: int = 22,
        thickness: int = 2,
        accent: Optional[str] = None,
        label: str = "",
        with_hex: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._pal = palette
        self._corner = corner
        self._thickness = thickness
        self._accent = accent or palette.accent
        self._label = label
        self._with_hex = with_hex
        self.setProperty("role", "hex-card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Hex layer (z=0)
        self._hex = HexBackground(palette, parent=self) if with_hex else None
        if self._hex:
            self._hex.lower()

        # Content host on top
        self._content = QWidget(self)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(corner + 8, corner + 8, corner + 8, corner + 8)
        self._content_layout.setSpacing(12)

    # -- layout sync ---------------------------------------------------------
    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._hex:
            self._hex.setGeometry(self.rect())
        self._content.setGeometry(self.rect())

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    # -- paint ---------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        c = self._corner
        t = self._thickness
        accent = QColor(self._accent)

        # Draw a hairline cyan rule along the top, just inside the corners
        rule_pen = QPen(QColor(self._pal.border_strong), 1)
        p.setPen(rule_pen)
        p.drawLine(rect.left() + c + 6, rect.top() + 1,
                   rect.right() - c - 6, rect.top() + 1)

        # Brackets
        pen = QPen(accent, t)
        pen.setCapStyle(Qt.PenCapStyle.SquareCap)
        p.setPen(pen)
        # Top-left
        p.drawLine(rect.left(), rect.top(), rect.left() + c, rect.top())
        p.drawLine(rect.left(), rect.top(), rect.left(), rect.top() + c)
        # Top-right
        p.drawLine(rect.right() - c, rect.top(), rect.right(), rect.top())
        p.drawLine(rect.right(), rect.top(), rect.right(), rect.top() + c)
        # Bottom-left
        p.drawLine(rect.left(), rect.bottom() - c, rect.left(), rect.bottom())
        p.drawLine(rect.left(), rect.bottom(), rect.left() + c, rect.bottom())
        # Bottom-right
        p.drawLine(rect.right() - c, rect.bottom(), rect.right(), rect.bottom())
        p.drawLine(rect.right(), rect.bottom() - c, rect.right(), rect.bottom())

        # Top-left ID label
        if self._label:
            p.setPen(QColor(self._pal.text_tertiary))
            f = self.font()
            f.setPointSize(8)
            f.setBold(True)
            f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 130)
            p.setFont(f)
            p.drawText(
                rect.left() + c + 10,
                rect.top() + 4,
                200, 14,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                self._label.upper(),
            )
