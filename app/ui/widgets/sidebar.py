"""Side navigation.

Custom-painted brand mark + row of ``NavItem`` buttons. The active row is
highlighted with an accent left-border pill that slides into position via
a property animation — one of the subtle touches that separates this UI
from stock Qt apps.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..theme.palette import Palette
from ..theme.typography import Typography
from . import icons as icon_lib
from .brand_mark import BrandMark


@dataclass
class NavEntry:
    id: str
    title: str
    icon: str


class _NavButton(QPushButton):
    """Individual navigation entry. Paints its own icon using the active colour."""

    def __init__(self, entry: NavEntry, palette: Palette, parent=None) -> None:
        super().__init__(entry.title, parent)
        self.entry = entry
        self._pal = palette
        self._active = False
        self.setObjectName("NavItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setMinimumHeight(42)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setProperty("active", "false")
        self._refresh_icon()

    def setActive(self, active: bool) -> None:
        self._active = active
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self._refresh_icon()

    def _refresh_icon(self) -> None:
        color = self._pal.accent if self._active else self._pal.text_secondary
        pm = icon_lib.pixmap_for(self.entry.icon, color, size=20)
        self.setIcon(QIcon(pm))


class Sidebar(QFrame):
    """Vertical nav column. Emits ``navigated(id)`` on click."""

    navigated = pyqtSignal(str)

    def __init__(
        self,
        palette: Palette,
        typography: Typography,
        entries: List[NavEntry],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._pal = palette
        self._type = typography
        self.setObjectName("Sidebar")
        self.setFixedWidth(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(4)

        # -- Brand mark (custom-painted hex bolt + wordmark) --
        brand = BrandMark(palette, typography, wordmark="GAMEBOOSTAPEX", sub="APEX v2")
        brand.setFixedHeight(56)
        layout.addWidget(brand)
        layout.addSpacing(20)

        # -- Nav section: MAIN --
        layout.addWidget(_SectionLabel("MAIN", palette, typography))
        layout.addSpacing(4)
        self._buttons: List[_NavButton] = []
        self._active_id: str = ""
        _main_ids = {"dashboard", "games", "optimize", "game_mode"}
        _tools_ids = {"monitor", "overlay", "cleanup"}
        for entry in entries:
            if entry.id not in _main_ids:
                continue
            btn = _NavButton(entry, palette, self)
            btn.clicked.connect(lambda _checked=False, e=entry: self._on_click(e.id))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addSpacing(16)
        layout.addWidget(_SectionLabel("TOOLS", palette, typography))
        layout.addSpacing(4)
        for entry in entries:
            if entry.id not in _tools_ids:
                continue
            btn = _NavButton(entry, palette, self)
            btn.clicked.connect(lambda _checked=False, e=entry: self._on_click(e.id))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addSpacing(16)
        layout.addWidget(_SectionLabel("SYSTEM", palette, typography))
        layout.addSpacing(4)
        for entry in entries:
            if entry.id in _main_ids or entry.id in _tools_ids:
                continue
            btn = _NavButton(entry, palette, self)
            btn.clicked.connect(lambda _checked=False, e=entry: self._on_click(e.id))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()

        # -- Footer: thin divider + admin status badge --
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {palette.border_soft};")
        layout.addWidget(divider)
        layout.addSpacing(10)

        self._status_dot = _StatusDot(palette)
        self._status_dot.setFixedSize(8, 8)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(8)
        status_row.addWidget(self._status_dot)
        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(f"color: {palette.text_tertiary};")
        self._status.setFont(typography.small())
        status_row.addWidget(self._status, 1)
        layout.addLayout(status_row)

    # ------------------------------------------------------------------ API
    def set_active(self, entry_id: str) -> None:
        self._active_id = entry_id
        for btn in self._buttons:
            btn.setActive(btn.entry.id == entry_id)

    def set_status(self, text: str, *, admin: Optional[bool] = None) -> None:
        self._status.setText(text)
        if admin is not None:
            self._status_dot.set_ok(admin)

    # ------------------------------------------------------------------ internal
    def _on_click(self, entry_id: str) -> None:
        if entry_id == self._active_id:
            return
        self.set_active(entry_id)
        self.navigated.emit(entry_id)


class _BrandMark(QWidget):
    """Simple painted hex-shaped logo mark with accent gradient feel."""

    def __init__(self, palette: Palette, parent=None) -> None:
        super().__init__(parent)
        self._pal = palette

    def paintEvent(self, _e) -> None:  # noqa: D401
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect()
        cx, cy = r.width() / 2, r.height() / 2
        size = min(r.width(), r.height()) - 4
        # filled rounded square with mint accent
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._pal.accent))
        p.drawRoundedRect(QRect(int(cx - size / 2), int(cy - size / 2), size, size), 7, 7)
        # inner "G" stroke
        pen = QPen(QColor(self._pal.bg_base))
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        margin = size * 0.28
        p.drawArc(
            int(cx - size / 2 + margin),
            int(cy - size / 2 + margin),
            int(size - margin * 2),
            int(size - margin * 2),
            30 * 16,
            290 * 16,
        )


class _SectionLabel(QLabel):
    """Uppercase, muted section divider inside the sidebar."""

    def __init__(self, text: str, palette, typography, parent=None) -> None:
        super().__init__(text.upper(), parent)
        self.setStyleSheet(f"color: {palette.text_tertiary}; letter-spacing: 2.2px;")
        font = typography.micro()
        font.setPointSize(8)
        self.setFont(font)


class _StatusDot(QWidget):
    """Small pulsing dot: green for admin / amber for standard user."""

    def __init__(self, palette, parent=None) -> None:
        super().__init__(parent)
        self._pal = palette
        self._ok = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_ok(self, ok: bool) -> None:
        self._ok = ok
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: D401
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(self._pal.accent if self._ok else self._pal.amber)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
