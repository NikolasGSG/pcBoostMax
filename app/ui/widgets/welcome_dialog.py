"""First-run welcome / disclaimer dialog.

Shown the first time the user launches the app (``config.accepted_disclaimer
== False``). Explains:

* what the app does, in plain English
* the exact safety net (restore points, rollback, preview-only)
* why the UAC prompt / admin banner may appear
* that the app ships UNSIGNED so SmartScreen may warn — this is expected
  and does NOT mean the binary is malicious.

The dialog is deliberately opinionated and long-ish: we'd rather use the
screen real-estate once to build trust than ship a tiny "Accept" nag.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core.constants import APP_NAME, APP_VERSION
from ..theme.palette import Palette
from ..theme.typography import Typography


class WelcomeDialog(QDialog):
    """Shown once, before the main window, to establish trust + consent."""

    def __init__(
        self,
        *,
        palette: Palette,
        typography: Typography,
        is_admin: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Welcome to {APP_NAME}")
        self.setModal(True)
        self.setMinimumSize(640, 720)
        self.resize(720, 780)

        self._pal = palette
        self._type = typography

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(16)

        # ---- Header ---------------------------------------------------
        header = QVBoxLayout()
        header.setSpacing(4)

        eyebrow = QLabel("FIRST RUN")
        eyebrow.setFont(typography.small())
        eyebrow.setStyleSheet(
            f"color: {palette.accent}; letter-spacing: 2px; font-weight: 700;"
        )
        header.addWidget(eyebrow)

        title = QLabel(f"Welcome to {APP_NAME}")
        title.setFont(typography.h1())
        title.setStyleSheet(f"color: {palette.text_primary};")
        header.addWidget(title)

        subtitle = QLabel(
            "A gaming optimizer that explains every change it makes — and lets "
            "you undo any of them in one click."
        )
        subtitle.setWordWrap(True)
        subtitle.setFont(typography.body())
        subtitle.setStyleSheet(f"color: {palette.text_secondary};")
        header.addWidget(subtitle)

        root.addLayout(header)

        # ---- Scrollable body ------------------------------------------
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body_host = QWidget()
        body = QVBoxLayout(body_host)
        body.setContentsMargins(0, 0, 8, 0)
        body.setSpacing(14)

        body.addWidget(self._section(
            "What this app actually does",
            "GameBoost inspects your PC, suggests Windows settings that can "
            "improve gaming performance, and applies only the ones you "
            "explicitly tick. It never installs drivers, never downloads "
            "anything, never contacts a server. Every action is local.",
        ))

        body.addWidget(self._section(
            "You are always in control",
            "• Every optimization is presented in a preview screen before anything changes.\n"
            "• Nothing happens automatically. YOU choose which rules to apply.\n"
            "• A Windows System Restore point is created before every apply (when admin).\n"
            "• Every reversible change has an Undo button in the Safety tab.",
            bullets=True,
        ))

        body.addWidget(self._section(
            "About administrator rights",
            "Many high-impact rules (power plans, services, HAGS, network stack) "
            "need administrator rights to write to HKLM. If you launch without "
            "admin, the app still works — those rules are shown but will report "
            "FAILED if applied. Right-click the app → 'Run as administrator' to "
            "unlock them.",
        ))

        body.addWidget(self._section(
            "Why you may see a SmartScreen / antivirus warning",
            "This build is not code-signed (a digital certificate costs hundreds "
            "of dollars per year). SmartScreen therefore labels it 'unknown "
            "publisher'. That warning is NOT a virus detection — it just means "
            "Microsoft hasn't built a reputation for this file yet. You can "
            "click 'More info' → 'Run anyway' to proceed.",
        ))

        body.addWidget(self._section(
            "No terminal should ever flash",
            "The app makes its Windows tweaks by calling built-in utilities "
            "(powercfg, reg, sc, PowerShell). Every one of those calls is "
            "launched with CREATE_NO_WINDOW so you should never see a black "
            "console window flash on screen. If you do — that's a bug, please "
            "report it.",
        ))

        body.addWidget(self._admin_row(is_admin))

        scroll.setWidget(body_host)
        root.addWidget(scroll, 1)

        # ---- Acceptance + buttons -------------------------------------
        self._accept_cb = QCheckBox(
            "I understand. This app modifies Windows settings that I have reviewed."
        )
        self._accept_cb.setFont(typography.body())
        self._accept_cb.setStyleSheet(f"color: {palette.text_primary}; spacing: 10px;")
        self._accept_cb.stateChanged.connect(self._sync_button_state)
        root.addWidget(self._accept_cb)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)

        quit_btn = QPushButton("Exit")
        quit_btn.setProperty("variant", "ghost")
        quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quit_btn.clicked.connect(self.reject)
        buttons.addWidget(quit_btn)

        buttons.addStretch(1)

        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setFont(typography.small())
        version_label.setStyleSheet(f"color: {palette.text_tertiary};")
        buttons.addWidget(version_label)

        self._continue_btn = QPushButton("Continue to GameBoost")
        self._continue_btn.setProperty("variant", "primary")
        self._continue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._continue_btn.setEnabled(False)
        self._continue_btn.clicked.connect(self.accept)
        buttons.addWidget(self._continue_btn)

        root.addLayout(buttons)

    # ------------------------------------------------------------------
    def _section(self, title: str, body: str, *, bullets: bool = False) -> QWidget:
        card = QFrame()
        card.setProperty("role", "surface-card")
        card.setStyleSheet(
            f"QFrame[role='surface-card'] {{"
            f" background: {self._pal.bg_surface};"
            f" border: 1px solid {self._pal.border};"
            f" border-radius: 12px; }}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(8)

        heading = QLabel(title)
        heading.setFont(self._type.h2())
        heading.setStyleSheet(f"color: {self._pal.text_primary};")
        lay.addWidget(heading)

        text = QLabel(body)
        text.setFont(self._type.body())
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        colour = self._pal.text_secondary
        text.setStyleSheet(f"color: {colour}; line-height: 150%;")
        lay.addWidget(text)
        return card

    def _admin_row(self, is_admin: bool) -> QWidget:
        card = QFrame()
        card.setProperty("role", "admin-row")
        bg = self._pal.accent_dim if is_admin else self._pal.amber_dim
        border = self._pal.accent if is_admin else self._pal.amber
        card.setStyleSheet(
            f"QFrame[role='admin-row'] {{"
            f" background: {bg}; border: 1px solid {border};"
            f" border-radius: 12px; }}"
        )
        lay = QHBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(12)

        dot = QLabel("●")
        dot_font = QFont(self._type.body())
        dot_font.setPointSize(16)
        dot.setFont(dot_font)
        dot.setStyleSheet(f"color: {border};")
        lay.addWidget(dot)

        status = QLabel(
            "Running with administrator privileges — every rule is available."
            if is_admin else
            "Running as a standard user — some rules will be greyed out until "
            "you relaunch via right-click → 'Run as administrator'."
        )
        status.setFont(self._type.body())
        status.setWordWrap(True)
        status.setStyleSheet(f"color: {self._pal.text_primary};")
        lay.addWidget(status, 1)
        return card

    def _sync_button_state(self) -> None:
        self._continue_btn.setEnabled(self._accept_cb.isChecked())
