"""Optimization action card.

Shows: title, What / Why descriptions, risk + impact badges, evidence line,
and a toggle switch to include/exclude the action from the plan. The card
is always framed so users never confuse "recommended" with "applied".
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...optimization.optimization_engine import PlannedAction
from ..theme.palette import Palette
from ..theme.typography import Typography
from .badge import Badge, impact_badge, risk_badge
from .toggle_switch import ToggleSwitch


def _format_relative(ts: float) -> str:
    """Render an epoch ts as a compact human-readable delta."""
    delta = max(0, int(time.time() - ts))
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{delta // 60}m ago"
    if delta < 86_400:
        return f"{delta // 3600}h ago"
    return f"{delta // 86_400}d ago"


class ActionCard(QFrame):
    """Single row in the optimization preview list."""

    selection_changed = pyqtSignal(str, bool)   # rule_id, selected

    def __init__(
        self,
        planned: PlannedAction,
        *,
        palette: Palette,
        typography: Typography,
        last_applied_ts: Optional[float] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._planned = planned
        self._pal = palette
        self._last_applied_ts = last_applied_ts

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(14)

        # -- Left: risk indicator stripe
        stripe = QFrame()
        stripe.setFixedWidth(4)
        stripe.setStyleSheet(f"background-color: {palette.risk_color(planned.rule.risk)}; border-radius: 2px;")
        root.addWidget(stripe)

        # -- Middle: text block
        middle = QVBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel(planned.rule.title)
        title.setFont(typography.h2())
        title.setWordWrap(True)
        header.addWidget(title)
        header.addStretch()
        middle.addLayout(header)

        # Badges row
        badges = QHBoxLayout()
        badges.setSpacing(6)
        badges.addWidget(risk_badge(planned.rule.risk, palette))
        badges.addWidget(impact_badge(planned.rule.impact, palette))
        if not planned.rule.reversible:
            advisory = Badge(
                "ADVISORY",
                palette=palette,
                fg=palette.text_secondary,
                bg=palette.border,
            )
            badges.addWidget(advisory)
        if planned.rule.requires_admin:
            admin_badge = Badge(
                "ADMIN",
                palette=palette,
                fg=palette.amber,
                bg=palette.amber_dim,
            )
            badges.addWidget(admin_badge)
        self._applied_badge: Badge | None = None
        if last_applied_ts is not None:
            self._applied_badge = Badge(
                f"APPLIED · {_format_relative(last_applied_ts).upper()}",
                palette=palette,
                fg=palette.accent,
                bg=palette.accent_dim,
            )
            badges.addWidget(self._applied_badge)
        badges.addStretch()
        middle.addLayout(badges)

        # What
        what = QLabel(f"<b style='color:{palette.text_primary};'>What it does.</b> "
                      f"<span style='color:{palette.text_secondary};'>{planned.rule.what}</span>")
        what.setWordWrap(True)
        what.setFont(typography.body())
        what.setTextFormat(Qt.TextFormat.RichText)
        middle.addWidget(what)

        # Why
        why = QLabel(f"<b style='color:{palette.text_primary};'>Why it matters.</b> "
                     f"<span style='color:{palette.text_secondary};'>{planned.rule.why}</span>")
        why.setWordWrap(True)
        why.setFont(typography.body())
        why.setTextFormat(Qt.TextFormat.RichText)
        middle.addWidget(why)

        # Evidence
        if planned.evaluation.reason:
            evidence = QLabel(f"↳ {planned.evaluation.reason}")
            evidence.setWordWrap(True)
            evidence.setFont(typography.small())
            evidence.setStyleSheet(f"color: {palette.text_tertiary};")
            middle.addWidget(evidence)

        root.addLayout(middle, 1)

        # -- Right: toggle switch + score pill
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(10)
        right.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        self._toggle = ToggleSwitch(palette)
        self._toggle.setChecked(planned.selected)
        self._toggle.toggled.connect(self._on_toggled)
        right.addWidget(self._toggle, alignment=Qt.AlignmentFlag.AlignRight)

        score = QLabel(f"SCORE · {planned.evaluation.score}")
        score.setFont(typography.micro())
        score.setStyleSheet(f"color: {palette.text_secondary}; letter-spacing: 1.5px;")
        score.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(score)

        root.addLayout(right)

    # ------------------------------------------------------------------ API
    @property
    def planned(self) -> PlannedAction:
        return self._planned

    @planned.setter
    def planned(self, value: PlannedAction) -> None:
        self._planned = value
        # Badge refresh is triggered explicitly by the view after bulk update.

    def _refresh_badges(self) -> None:
        """Update the APPLIED badge visibility based on current applicability."""
        evaluation = getattr(self._planned, "evaluation", None)
        now_applicable = bool(evaluation and evaluation.applicable)
        if self._applied_badge:
            self._applied_badge.setVisible(not now_applicable)

    def _on_toggled(self, checked: bool) -> None:
        self._planned.selected = checked
        self.selection_changed.emit(self._planned.rule.id, checked)

    def is_selected(self) -> bool:
        return self._toggle.isChecked()

    def set_selected(self, selected: bool) -> None:
        """Programmatically toggle the card (used by Preset buttons)."""
        if self._toggle.isChecked() == selected:
            return
        self._toggle.blockSignals(True)
        self._toggle.setChecked(selected)
        self._toggle.blockSignals(False)
        self._planned.selected = selected
