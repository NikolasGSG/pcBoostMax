"""Generic labelled section / card-group helpers used throughout views."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..theme.palette import Palette
from ..theme.typography import Typography


class SectionHeader(QWidget):
    """Eyebrow + title + optional trailing widget (e.g. 'View all' button)."""

    def __init__(
        self,
        eyebrow: str,
        title: str,
        *,
        palette: Palette,
        typography: Typography,
        trailing: Optional[QWidget] = None,
        eyebrow_color: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        eyebrow_label = QLabel(eyebrow.upper())
        eyebrow_label.setFont(typography.micro())
        eyebrow_label.setStyleSheet(
            f"color: {eyebrow_color or palette.accent}; letter-spacing: 2.2px;"
        )
        root.addWidget(eyebrow_label)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        title_label = QLabel(title)
        title_label.setFont(typography.h1())
        row.addWidget(title_label)
        row.addStretch()
        if trailing is not None:
            row.addWidget(trailing)
        root.addLayout(row)


class DividerLine(QFrame):
    def __init__(self, palette: Palette, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("role", "divider")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background-color: {palette.border_soft};")


class Card(QFrame):
    """Basic card wrapper with standard padding — a convenience container."""

    def __init__(
        self,
        *,
        palette: Palette,
        role: str = "card",
        padding: int = 20,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", role)
        self._body = QVBoxLayout(self)
        self._body.setContentsMargins(padding, padding, padding, padding)
        self._body.setSpacing(12)

    def body(self) -> QVBoxLayout:
        return self._body


class StatRow(QWidget):
    """Label/value horizontal row used for spec lists (CPU, GPU, RAM)."""

    def __init__(
        self,
        key: str,
        value: str,
        *,
        palette: Palette,
        typography: Typography,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        k = QLabel(key)
        k.setFont(typography.small())
        k.setStyleSheet(f"color: {palette.text_tertiary};")
        k.setFixedWidth(110)
        v = QLabel(value)
        v.setFont(typography.body())
        v.setStyleSheet(f"color: {palette.text_primary};")
        v.setWordWrap(True)
        v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(k)
        layout.addWidget(v, 1)

    def setValue(self, text: str) -> None:
        items = self.findChildren(QLabel)
        if len(items) >= 2:
            items[1].setText(text)
