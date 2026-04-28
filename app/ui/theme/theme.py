"""Theme aggregator. Apply once to the QApplication and forget about it."""
from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

from .palette import Palette
from .presets import palette_for
from .spacing import Radius, Spacing
from .stylesheet import build_stylesheet
from .typography import Typography


class Theme:
    """Central theme object the rest of the UI reads from."""

    def __init__(self, *, preset: str = "apex") -> None:
        self.preset = preset
        self.palette = palette_for(preset)
        self.type = Typography()
        self.space = Spacing()
        self.radius = Radius()

    # -- palette proxies (very common accesses) ------------------------------
    @property
    def p(self) -> Palette:
        return self.palette

    @property
    def t(self) -> Typography:
        return self.type

    @property
    def s(self) -> Spacing:
        return self.space

    @property
    def r(self) -> Radius:
        return self.radius

    # -----------------------------------------------------------------------
    def apply(self, app: QApplication) -> None:
        app.setStyleSheet(build_stylesheet(self.palette, self.radius, self.space))

        # Base QPalette so Qt's non-styled internals (e.g. line-edit carets,
        # menu separators) match the dark theme.
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, QColor(self.palette.bg_base))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(self.palette.text_primary))
        pal.setColor(QPalette.ColorRole.Base, QColor(self.palette.bg_sunken))
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor(self.palette.bg_surface))
        pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(self.palette.bg_elevated))
        pal.setColor(QPalette.ColorRole.ToolTipText, QColor(self.palette.text_primary))
        pal.setColor(QPalette.ColorRole.Text, QColor(self.palette.text_primary))
        pal.setColor(QPalette.ColorRole.Button, QColor(self.palette.bg_elevated))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(self.palette.text_primary))
        pal.setColor(QPalette.ColorRole.Highlight, QColor(self.palette.accent))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(self.palette.text_on_accent))
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(self.palette.text_tertiary))
        app.setPalette(pal)
