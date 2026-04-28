"""UI panel that renders the live Insight stream from ``LiveInsightEngine``.

Subscribes to ``insights.updated`` on the controller's event bus and
re-renders the visible cards whenever the set of insights changes. Each
card is colour-tinted by severity and includes an optional "take action"
button that routes to another view (Optimize, Game Mode).

Updates are **live** — a new sample can surface / retire an insight within
a second. We keep the re-render lightweight by diffing on the ``id`` of
each insight: unchanged cards are reused rather than recreated, so no
flicker when only one entry changed.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...core.event_bus import EventBus
from ...monitoring.live_insights import (
    Insight,
    SEVERITY_CRIT,
    SEVERITY_INFO,
    SEVERITY_WARN,
    SEVERITY_WATCH,
)
from ..theme.palette import Palette
from ..theme.typography import Typography


# Map severity → (border hex, inner wash hex, indicator dot hex)
def _severity_colors(palette: Palette, severity: str) -> tuple[str, str, str]:
    if severity == SEVERITY_CRIT:
        return palette.coral, palette.coral_dim, palette.coral
    if severity == SEVERITY_WARN:
        return palette.amber, palette.amber_dim, palette.amber
    if severity == SEVERITY_WATCH:
        return palette.neon_blue, palette.neon_blue_dim, palette.neon_blue
    # INFO
    return palette.accent, palette.accent_dim, palette.accent


class _InsightCard(QFrame):
    """Single insight row. Carries an optional action button."""

    action_clicked = pyqtSignal(str)    # emits Insight.action_target

    def __init__(
        self,
        insight: Insight,
        palette: Palette,
        typography: Typography,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._insight = insight
        self._pal = palette
        self._type = typography
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._build()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        border, wash, dot = _severity_colors(self._pal, self._insight.severity)
        self.setStyleSheet(
            "QFrame[role='insight-card'] {"
            f" background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            f"   stop:0 {wash}, stop:1 {self._pal.bg_surface});"
            f" border: 1px solid {border}; border-radius: 12px; }}"
        )
        self.setProperty("role", "insight-card")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(14)

        # Indicator dot
        indicator = QLabel("●")
        from PyQt6.QtGui import QFont
        f = QFont(self._type.body())
        f.setPointSize(16)
        indicator.setFont(f)
        indicator.setStyleSheet(f"color: {dot};")
        indicator.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(indicator)

        # Text block
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        headline = QLabel(self._insight.headline)
        headline.setFont(self._type.body_strong())
        headline.setStyleSheet(f"color: {self._pal.text_primary};")
        headline.setWordWrap(True)
        text_col.addWidget(headline)

        body = QLabel(self._insight.body)
        body.setFont(self._type.small())
        body.setStyleSheet(f"color: {self._pal.text_secondary};")
        body.setWordWrap(True)
        text_col.addWidget(body)

        lay.addLayout(text_col, 1)

        # Action button (optional)
        if self._insight.action and self._insight.action_target:
            btn = QPushButton(self._insight.action)
            btn.setProperty("variant", "ghost")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda: self.action_clicked.emit(self._insight.action_target)
            )
            lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignTop)

    # ------------------------------------------------------------------ api
    @property
    def insight(self) -> Insight:
        return self._insight


class LiveInsightsPanel(QWidget):
    """Panel that subscribes to live insights and renders them in order."""

    navigation_requested = pyqtSignal(str)   # emits "optimize" | "game_mode" | "cleanup"
    # Internal signal used to marshal bus events (which arrive on the monitor
    # thread) onto the UI thread. Qt auto-picks ``QueuedConnection`` for the
    # cross-thread hop, so rendering always runs on the main thread.
    _insights_received = pyqtSignal(object)

    def __init__(
        self,
        bus: EventBus,
        palette: Palette,
        typography: Typography,
        *,
        initial: Optional[List[Insight]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._bus = bus
        self._pal = palette
        self._type = typography
        self._cards: Dict[str, _InsightCard] = {}
        self._current_ids: List[str] = []
        # Route thread-foreign bus events onto the GUI thread.
        self._insights_received.connect(self._on_updated)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # Header
        header = QHBoxLayout()
        header.setSpacing(10)
        eyebrow = QLabel("ADAPTIVE")
        eyebrow.setFont(typography.small())
        eyebrow.setStyleSheet(
            f"color: {palette.neon_blue}; letter-spacing: 2px; font-weight: 700;"
        )
        header.addWidget(eyebrow)
        title = QLabel("Live Insights")
        title.setFont(typography.h2())
        title.setStyleSheet(f"color: {palette.text_primary};")
        header.addWidget(title)
        header.addStretch()
        self._status_label = QLabel("listening…")
        self._status_label.setFont(typography.small())
        self._status_label.setStyleSheet(f"color: {palette.text_tertiary};")
        header.addWidget(self._status_label)
        root.addLayout(header)

        # Body container (cards live here)
        self._body = QVBoxLayout()
        self._body.setSpacing(10)
        root.addLayout(self._body)

        # Empty state
        self._empty = QLabel(
            "No live alerts. The engine is watching CPU, RAM, disk and GPU in "
            "real time — you'll see suggestions here the moment pressure appears."
        )
        self._empty.setWordWrap(True)
        self._empty.setFont(typography.body())
        self._empty.setStyleSheet(
            f"color: {palette.text_secondary}; padding: 16px;"
            f" background: {palette.bg_sunken};"
            f" border: 1px dashed {palette.border_soft};"
            f" border-radius: 12px;"
        )
        self._body.addWidget(self._empty)

        # Subscribe to updates. We emit via the signal so Qt will hop the
        # data onto the GUI thread before we touch any widgets.
        bus.subscribe("insights.updated", self._insights_received.emit)

        if initial:
            self._on_updated(initial)

    # ------------------------------------------------------------------ rendering
    def _on_updated(self, insights: List[Insight]) -> None:
        self._status_label.setText(
            f"{len(insights)} active" if insights else "all clear"
        )
        new_ids = [i.id for i in insights]
        if new_ids == self._current_ids and all(
            self._cards.get(i.id) and self._cards[i.id].insight == i for i in insights
        ):
            return  # nothing changed

        # Remove cards that disappeared
        for gone_id in list(self._cards):
            if gone_id not in new_ids:
                card = self._cards.pop(gone_id)
                self._body.removeWidget(card)
                card.deleteLater()

        # Remove the empty-state widget if we're about to render cards
        self._empty.setVisible(not insights)
        if insights:
            self._body.removeWidget(self._empty)

        # Rebuild order by re-indexing existing cards and inserting new ones
        # where needed. We pop everything, then re-add in the desired order.
        for card in list(self._cards.values()):
            self._body.removeWidget(card)

        for insight in insights:
            card = self._cards.get(insight.id)
            if card is None or card.insight != insight:
                if card is not None:
                    card.deleteLater()
                card = _InsightCard(insight, self._pal, self._type, self)
                card.action_clicked.connect(self.navigation_requested.emit)
                self._cards[insight.id] = card
            self._body.addWidget(card)

        self._current_ids = new_ids

        # Put the empty-state back if we have nothing to show.
        if not insights:
            self._body.addWidget(self._empty)
