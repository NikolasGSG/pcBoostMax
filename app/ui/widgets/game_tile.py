"""Game tile — one card in the Game Hub grid.

Each tile is a 2:3-ish portrait card with:

* Custom-painted hex backdrop + lime corner brackets (signature look).
* The first letter of the title in a huge condensed display face,
  acting as a placeholder when no cover art is available.
* Title + launcher chip at the bottom.
* Two micro buttons on hover: ``Play`` (lime) and ``Tune`` (cyan).

The whole tile is clickable — clicks route via signals so the parent
view can decide what "click" means (typically opens the profile editor).
"""
from __future__ import annotations

import math
from typing import Optional

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...games.library import Game, Launcher
from ..theme.palette import Palette
from ..theme.typography import Typography


_LAUNCHER_COLOR = {
    Launcher.STEAM:      "#7AB8E8",
    Launcher.EPIC:       "#FFFFFF",
    Launcher.GOG:        "#B070FF",
    Launcher.BATTLE_NET: "#00AEFF",
    Launcher.RIOT:       "#D13639",
    Launcher.XBOX:       "#A6FF00",
    Launcher.UBISOFT:    "#FFFFFF",
    Launcher.EA:         "#FF453A",
    Launcher.STANDALONE: "#7E8C9F",
    Launcher.MANUAL:     "#7E8C9F",
}


class GameTile(QFrame):
    """One game card."""

    play_clicked = pyqtSignal(str)         # game_id
    tune_clicked = pyqtSignal(str)         # game_id
    activated    = pyqtSignal(str)         # game_id (clicked anywhere)

    def __init__(
        self,
        game: Game,
        palette: Palette,
        typography: Typography,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GameTile")
        self._game = game
        self._pal = palette
        self._type = typography
        self.setFixedSize(220, 300)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        col = QVBoxLayout(self)
        col.setContentsMargins(14, 14, 14, 12)
        col.setSpacing(0)

        col.addStretch(1)

        # Title block at the bottom
        title = QLabel(game.name)
        title.setObjectName("GameTileTitle")
        title.setWordWrap(True)
        f = typography.h2()
        f.setPointSize(13)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        col.addWidget(title)

        sub = QHBoxLayout()
        sub.setSpacing(6)
        chip = QLabel(game.launcher.label.upper())
        chip.setObjectName("GameTileSub")
        chip.setFont(typography.eyebrow())
        chip.setStyleSheet(
            f"color: {_LAUNCHER_COLOR.get(game.launcher, palette.text_secondary)};"
        )
        sub.addWidget(chip)
        sub.addStretch()
        col.addLayout(sub)

        # Action row
        actions = QHBoxLayout()
        actions.setSpacing(6)
        self._play_btn = QPushButton("PLAY")
        self._play_btn.setProperty("variant", "primary")
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.setMinimumHeight(28)
        self._play_btn.clicked.connect(lambda: self.play_clicked.emit(game.id))
        actions.addWidget(self._play_btn, 1)

        self._tune_btn = QPushButton("TUNE")
        self._tune_btn.setProperty("variant", "ghost")
        self._tune_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tune_btn.setMinimumHeight(28)
        self._tune_btn.clicked.connect(lambda: self.tune_clicked.emit(game.id))
        actions.addWidget(self._tune_btn)
        col.addSpacing(10)
        col.addLayout(actions)

    # -- whole-tile click ---------------------------------------------------
    def mouseReleaseEvent(self, event):  # type: ignore[override]
        # If neither button caught the click, treat as tile activation.
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.pos())
            if child is None or not isinstance(child, QPushButton):
                self.activated.emit(self._game.id)

    # -- paint --------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)

        # Hex motif top-half
        self._paint_hex_motif(p, rect)

        # Big launcher initial in the upper area as art placeholder
        initial = (self._game.name or "?")[0].upper()
        f = QFont(self._type.display_family, 84)
        f.setBold(True)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 95)
        p.setFont(f)
        accent = QColor(_LAUNCHER_COLOR.get(self._game.launcher, self._pal.accent))
        accent.setAlpha(40)
        p.setPen(QColor(accent))
        p.drawText(
            rect.left() + 8, rect.top() + 4,
            rect.width() - 16, int(rect.height() * 0.55),
            int(Qt.AlignmentFlag.AlignCenter),
            initial,
        )

        # Lime corner brackets (signature)
        c, t = 14, 2
        bracket = QColor(self._pal.accent)
        p.setPen(QPen(bracket, t, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap))
        p.drawLine(rect.left(), rect.top(), rect.left() + c, rect.top())
        p.drawLine(rect.left(), rect.top(), rect.left(), rect.top() + c)
        p.drawLine(rect.right() - c, rect.top(), rect.right(), rect.top())
        p.drawLine(rect.right(), rect.top(), rect.right(), rect.top() + c)
        p.drawLine(rect.left(), rect.bottom() - c, rect.left(), rect.bottom())
        p.drawLine(rect.left(), rect.bottom(), rect.left() + c, rect.bottom())
        p.drawLine(rect.right() - c, rect.bottom(), rect.right(), rect.bottom())
        p.drawLine(rect.right(), rect.bottom() - c, rect.right(), rect.bottom())

        # Hairline divider above the title block
        title_y = rect.bottom() - 86
        p.setPen(QPen(QColor(self._pal.border_hairline), 1))
        p.drawLine(rect.left() + 14, title_y, rect.right() - 14, title_y)

    # -- helpers ------------------------------------------------------------
    def _paint_hex_motif(self, p: QPainter, rect) -> None:
        s = 12
        line = QColor(self._pal.hex_line)
        line.setAlpha(80)
        p.setPen(QPen(line, 1))
        # Outline-only — Qt's default brush is opaque, which would otherwise
        # fill each hex with white/lime.
        p.setBrush(Qt.BrushStyle.NoBrush)

        w = s * 2
        h = math.sqrt(3) * s
        col_step = w * 0.75

        cols = int(rect.width() / col_step) + 2
        rows = int(rect.height() / h) + 2
        for r in range(-1, rows):
            for c in range(-1, cols):
                cx = rect.left() + c * col_step
                cy = rect.top() + r * h + (h / 2 if c % 2 else 0)
                if cy > rect.bottom() - 90:
                    continue   # leave the title block clean
                pts = []
                for i in range(6):
                    ang = math.radians(60 * i)
                    pts.append(QPointF(cx + s * math.cos(ang),
                                       cy + s * math.sin(ang)))
                p.drawPolygon(QPolygonF(pts))
