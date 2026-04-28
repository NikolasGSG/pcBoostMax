"""Game Mode view — one-tap activation with status + options."""
from __future__ import annotations

import time
from typing import List, Optional

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...utils.formatting import human_duration
from ..theme.palette import Palette
from ..theme.typography import Typography
from ..viewmodels.game_mode_vm import GameModeViewModel
from ..widgets.banner import Banner
from ..widgets.section import Card, DividerLine, SectionHeader
from ..widgets.toggle_switch import ToggleSwitch


class GameModeView(QWidget):
    def __init__(
        self,
        vm: GameModeViewModel,
        palette: Palette,
        typography: Typography,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._vm = vm
        self._pal = palette
        self._type = typography

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        root = QVBoxLayout(container)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(18)

        # -- Header
        root.addWidget(SectionHeader(
            "SESSION LAUNCHER", "Game Mode",
            palette=palette, typography=typography,
            eyebrow_color=palette.violet,
        ))

        # -- Status card (big)
        self.status_card = _StatusCard(palette=palette, typography=typography)
        self.status_card.toggle_requested.connect(self._on_toggle_clicked)
        root.addWidget(self.status_card)

        # -- Two column: Options + What it does
        columns = QHBoxLayout()
        columns.setSpacing(16)

        opts = Card(palette=palette, padding=22)
        opts.body().addWidget(SectionHeader(
            "Options", "What to change during the session",
            palette=palette, typography=typography,
            eyebrow_color=palette.accent,
        ))

        self._switch_power = self._toggle_row(
            "Switch to High Performance power plan",
            "Keeps CPU responsive between bursts. Reversed on deactivation.",
        )
        opts.body().addWidget(self._switch_power["row"])

        self._switch_visual = self._toggle_row(
            "Trim Windows animations",
            "Uses the 'Best performance' preset. Reverts when you exit Game Mode.",
        )
        opts.body().addWidget(self._switch_visual["row"])

        self._switch_dvr = self._toggle_row(
            "Disable Game DVR background recording",
            "Stops Game Bar's always-on capture. Toggle back anytime.",
        )
        opts.body().addWidget(self._switch_dvr["row"])

        self._switch_suspend = self._toggle_row(
            "Suspend heavy background apps",
            "Pauses a curated list of browsers/chat/cloud apps. Work stays open — they're resumed on deactivation.",
        )
        opts.body().addWidget(self._switch_suspend["row"])
        opts.body().addStretch()
        columns.addWidget(opts, 1)

        explain = Card(palette=palette, padding=22)
        explain.body().addWidget(SectionHeader(
            "How this works", "Safety model",
            palette=palette, typography=typography,
            eyebrow_color=palette.amber,
        ))
        bullets = [
            ("Snapshot first", "Every setting we change is captured before any modification — so deactivation reverts it exactly."),
            ("Nothing killed", "Background apps are *suspended*, not killed. Your tabs, chat history and documents stay intact."),
            ("Idempotent", "You can hit activate / deactivate as many times as you like; the state machine handles it cleanly."),
            ("Crash-safe", "Every change is in the action log, so even after a crash you can rollback from the Safety tab."),
        ]
        for title, body in bullets:
            explain.body().addWidget(_Bullet(title, body, palette=palette, typography=typography))
        explain.body().addStretch()
        columns.addWidget(explain, 1)

        root.addLayout(columns)
        root.addStretch()

        # -- Bind VM
        self._vm.activated.connect(lambda _snap: self._refresh_state())
        self._vm.deactivated.connect(lambda _snap: self._refresh_state())

        # Timer for the elapsed counter while active
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._update_elapsed)

        self._refresh_state()

    # ------------------------------------------------------------------ helpers
    def _toggle_row(self, title: str, subtitle: str) -> dict:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 10, 0, 10)
        lay.setSpacing(18)

        texts = QVBoxLayout()
        texts.setSpacing(2)
        t = QLabel(title)
        t.setFont(self._type.body_strong())
        s = QLabel(subtitle)
        s.setWordWrap(True)
        s.setFont(self._type.small())
        s.setStyleSheet(f"color: {self._pal.text_secondary};")
        texts.addWidget(t)
        texts.addWidget(s)
        lay.addLayout(texts, 1)

        toggle = ToggleSwitch(self._pal)
        toggle.setChecked(True)
        lay.addWidget(toggle, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        return {"row": row, "toggle": toggle}

    # ------------------------------------------------------------------ actions
    def _on_toggle_clicked(self) -> None:
        if self._vm.is_active:
            self._vm.deactivate()
        else:
            suspend: Optional[List[str]] = None
            if self._switch_suspend["toggle"].isChecked():
                suspend = self._default_suspend_targets()
            self._vm.activate(
                suspend_targets=suspend,
                enable_power=self._switch_power["toggle"].isChecked(),
                enable_visual=self._switch_visual["toggle"].isChecked(),
                enable_dvr=self._switch_dvr["toggle"].isChecked(),
            )

    def _refresh_state(self) -> None:
        active = self._vm.is_active
        self.status_card.set_active(active, self._vm.started_at)
        if active and not self._tick.isActive():
            self._tick.start()
        elif not active and self._tick.isActive():
            self._tick.stop()

    def _update_elapsed(self) -> None:
        self.status_card.update_elapsed(self._vm.started_at)

    @staticmethod
    def _default_suspend_targets() -> List[str]:
        return [
            "chrome.exe", "msedge.exe", "firefox.exe",
            "slack.exe", "teams.exe",
            "onedrive.exe", "dropbox.exe",
        ]


class _Bullet(QWidget):
    def __init__(self, title: str, body: str, *, palette: Palette, typography: Typography, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 6)
        lay.setSpacing(2)
        t = QLabel(f"· {title}")
        t.setFont(typography.body_strong())
        b = QLabel(body)
        b.setWordWrap(True)
        b.setFont(typography.body())
        b.setStyleSheet(f"color: {palette.text_secondary}; padding-left: 12px;")
        lay.addWidget(t)
        lay.addWidget(b)


class _StatusCard(QFrame):
    """Big status card — shows idle / active state with a single CTA button."""

    from PyQt6.QtCore import pyqtSignal as _pyqtSignal
    toggle_requested = _pyqtSignal()

    def __init__(self, *, palette: Palette, typography: Typography, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("role", "card-elevated")
        self.setMinimumHeight(160)
        self._pal = palette
        self._type = typography

        root = QHBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(22)

        # Pulse light
        self.pulse = _Pulse(palette)
        self.pulse.setFixedSize(56, 56)
        root.addWidget(self.pulse)

        text = QVBoxLayout()
        text.setSpacing(2)
        self._eyebrow = QLabel("STATUS")
        self._eyebrow.setFont(typography.micro())
        self._eyebrow.setStyleSheet(f"color: {palette.text_tertiary}; letter-spacing: 2.2px;")
        text.addWidget(self._eyebrow)

        self._title = QLabel("Game Mode is idle")
        tfont = typography.display()
        tfont.setPointSize(22)
        self._title.setFont(tfont)
        text.addWidget(self._title)

        self._detail = QLabel("Activate to apply a curated, fully reversible session preset.")
        self._detail.setWordWrap(True)
        self._detail.setFont(typography.body())
        self._detail.setStyleSheet(f"color: {palette.text_secondary};")
        text.addWidget(self._detail)
        root.addLayout(text, 1)

        self.button = QPushButton("Activate Game Mode")
        self.button.setProperty("variant", "violet")
        self.button.setMinimumHeight(44)
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self.toggle_requested.emit)
        root.addWidget(self.button, alignment=Qt.AlignmentFlag.AlignVCenter)

    def set_active(self, active: bool, started_at: Optional[float]) -> None:
        self.pulse.set_active(active)
        if active:
            self._title.setText("Game Mode is active")
            elapsed = human_duration((time.time() - (started_at or time.time())))
            self._detail.setText(f"Session preset applied. Running for {elapsed}.")
            self.button.setText("Deactivate & restore")
            self.button.setProperty("variant", "danger")
        else:
            self._title.setText("Game Mode is idle")
            self._detail.setText("Activate to apply a curated, fully reversible session preset.")
            self.button.setText("Activate Game Mode")
            self.button.setProperty("variant", "violet")
        # trigger QSS refresh
        self.button.style().unpolish(self.button)
        self.button.style().polish(self.button)

    def update_elapsed(self, started_at: Optional[float]) -> None:
        if started_at is None:
            return
        self._detail.setText(f"Session preset applied. Running for {human_duration(time.time() - started_at)}.")


class _Pulse(QWidget):
    """Animated pulse ring — soft mint when idle, violet when active."""

    def __init__(self, palette: Palette, parent=None) -> None:
        super().__init__(parent)
        self._pal = palette
        self._active = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def _advance(self) -> None:
        self._phase = (self._phase + 0.05) % (2 * 3.1415926)
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: D401
        import math

        from PyQt6.QtGui import QColor, QPainter

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(4, 4, -4, -4)
        base = QColor(self._pal.violet if self._active else self._pal.accent)
        # Outer pulse ring
        pulse_alpha = 70 + int(60 * (math.sin(self._phase) * 0.5 + 0.5))
        ring = QColor(base)
        ring.setAlpha(pulse_alpha)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ring)
        expand = 4 if self._active else 2
        p.drawEllipse(rect.adjusted(-expand, -expand, expand, expand))
        # Core
        p.setBrush(base)
        p.drawEllipse(rect.adjusted(6, 6, -6, -6))
