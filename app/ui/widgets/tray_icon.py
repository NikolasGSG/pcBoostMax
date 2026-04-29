"""System tray icon for GameBoostApex.

Keeps the app alive when the user clicks the window's [X]. The tray menu
gives quick access to:

* Show / hide the main window
* Toggle Game Mode
* Toggle the HUD overlay
* Quit

The icon uses a procedurally-drawn mint bolt — no external .ico file is
needed, which keeps the single-file exe small.
"""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from ...core.constants import APP_NAME
from ..theme.palette import Palette


def _bolt_pixmap(size: int, colour: str) -> QPixmap:
    """Draw a simple filled bolt glyph at the requested size."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    path = QPainterPath()
    # Relative coords in a 100×100 box, scaled to `size`.
    pts = [
        (58, 4), (22, 54), (44, 54), (32, 96), (82, 40), (54, 40), (72, 4),
    ]
    scale = size / 100.0
    sx, sy = pts[0]
    path.moveTo(sx * scale, sy * scale)
    for x, y in pts[1:]:
        path.lineTo(x * scale, y * scale)
    path.closeSubpath()

    p.fillPath(path, QColor(colour))
    p.end()
    return pm


def tray_icon(palette: Palette) -> QIcon:
    """Return a ready-to-use multi-size QIcon for the tray and window."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64):
        icon.addPixmap(_bolt_pixmap(size, palette.accent), QIcon.Mode.Normal, QIcon.State.Off)
    return icon


class GameBoostApexTray(QSystemTrayIcon):
    """System tray icon + context menu."""

    def __init__(
        self,
        *,
        palette: Palette,
        on_show: Callable[[], None],
        on_toggle_game_mode: Callable[[], None],
        on_toggle_overlay: Callable[[], None],
        on_quit: Callable[[], None],
        on_memory_trim: Optional[Callable[[], None]] = None,
        on_press_to_boost: Optional[Callable[[], None]] = None,
        on_run_cleanup: Optional[Callable[[], None]] = None,
        parent: Optional[QSystemTrayIcon] = None,
    ) -> None:
        super().__init__(parent)
        self._palette = palette
        self.setIcon(tray_icon(palette))
        self.setToolTip(f"{APP_NAME} — running in the background")

        menu = QMenu()
        menu.setStyleSheet(
            f"QMenu {{ background: {palette.bg_elevated};"
            f" color: {palette.text_primary};"
            f" border: 1px solid {palette.border};"
            f" border-radius: 8px; padding: 4px; }}"
            f"QMenu::item {{ padding: 6px 18px; border-radius: 4px; }}"
            f"QMenu::item:selected {{ background: {palette.accent_dim};"
            f" color: {palette.accent}; }}"
            f"QMenu::separator {{ height: 1px; background: {palette.border};"
            f" margin: 4px 8px; }}"
        )

        show_act = QAction("Open GameBoostApex", menu)
        show_act.triggered.connect(on_show)
        menu.addAction(show_act)

        menu.addSeparator()

        # ---- Quick actions (v2.1) ------------------------------------
        if on_press_to_boost is not None:
            boost_act = QAction("Press-to-Boost (30 min)", menu)
            boost_act.triggered.connect(on_press_to_boost)
            menu.addAction(boost_act)

        if on_memory_trim is not None:
            trim_act = QAction("Trim memory now", menu)
            trim_act.triggered.connect(on_memory_trim)
            menu.addAction(trim_act)

        if on_run_cleanup is not None:
            clean_act = QAction("Run quick cleanup", menu)
            clean_act.triggered.connect(on_run_cleanup)
            menu.addAction(clean_act)

        if any((on_press_to_boost, on_memory_trim, on_run_cleanup)):
            menu.addSeparator()

        self._game_mode_act = QAction("Toggle Game Mode", menu)
        self._game_mode_act.triggered.connect(on_toggle_game_mode)
        menu.addAction(self._game_mode_act)

        self._overlay_act = QAction("Toggle HUD overlay", menu)
        self._overlay_act.triggered.connect(on_toggle_overlay)
        menu.addAction(self._overlay_act)

        menu.addSeparator()

        quit_act = QAction("Quit GameBoostApex", menu)
        quit_act.triggered.connect(on_quit)
        menu.addAction(quit_act)

        self.setContextMenu(menu)
        # Double-click also opens the window
        self.activated.connect(
            lambda reason: on_show()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick
            else None
        )

    # ---- Tooltip helpers ---------------------------------------------------
    def set_state_message(self, message: str) -> None:
        self.setToolTip(f"{APP_NAME} — {message}")

    def notify(self, title: str, body: str, *, timeout_ms: int = 4000) -> None:
        """Raise a balloon notification if the OS allows it."""
        self.showMessage(title, body, self.icon(), timeout_ms)
