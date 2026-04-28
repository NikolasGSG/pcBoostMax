"""Inline, role-tinted banner (info / warn / danger / violet) used across views."""
from __future__ import annotations

from typing import Literal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy

from ..theme.palette import Palette
from ..theme.typography import Typography

BannerRole = Literal["info", "warn", "danger", "violet"]


class Banner(QFrame):
    def __init__(
        self,
        text: str,
        *,
        palette: Palette,
        typography: Typography,
        role: BannerRole = "info",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", f"banner-{role}")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setFont(typography.body())
        self._label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._label, 1)

    def setText(self, text: str) -> None:
        self._label.setText(text)
