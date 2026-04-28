"""Optimize view — preview & apply the optimization plan."""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core.constants import RISK_LOW, RISK_SAFE
from ...optimization.optimization_engine import OptimizationPlan
from ..theme.palette import Palette
from ..theme.typography import Typography
from ..viewmodels.optimize_vm import OptimizeViewModel
from ..widgets.action_card import ActionCard
from ..widgets.apply_report_dialog import ApplyReportDialog, RuleResult
from ..widgets.banner import Banner
from ..widgets.section import Card, SectionHeader


class OptimizeView(QWidget):
    def __init__(
        self,
        vm: OptimizeViewModel,
        palette: Palette,
        typography: Typography,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._vm = vm
        self._pal = palette
        self._type = typography
        self._plan: Optional[OptimizationPlan] = None
        self._cards: List[ActionCard] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, stretch=1)

        container = QWidget()
        scroll.setWidget(container)

        root = QVBoxLayout(container)
        root.setContentsMargins(32, 20, 32, 10)
        root.setSpacing(14)

        # -- Header: eyebrow + title + actions
        regenerate_btn = QPushButton("Re-analyze")
        regenerate_btn.setProperty("variant", "ghost")
        regenerate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        regenerate_btn.clicked.connect(self._regenerate)

        root.addWidget(SectionHeader(
            "OPTIMIZATION PLAN", "Review before applying",
            palette=palette, typography=typography,
            trailing=regenerate_btn,
        ))

        # -- Summary banner
        self.summary = Banner(
            "This plan is a preview only. Nothing is applied to your system until "
            "you press Apply. Every reversible action can be rolled back from Safety.",
            palette=palette, typography=typography, role="info",
        )
        root.addWidget(self.summary)

        # -- Admin warning banner (only visible when an admin-required rule
        #    is selected and we are NOT running elevated)
        self.admin_warning = Banner(
            "Some selected rules need administrator rights. They will show "
            "FAILED in the Apply Report unless you relaunch this app as Administrator.",
            palette=palette, typography=typography, role="warn",
        )
        self.admin_warning.setVisible(False)
        root.addWidget(self.admin_warning)

        # -- Presets row: quick-select buttons
        presets = QHBoxLayout()
        presets.setSpacing(10)

        preset_label = QLabel("Presets:")
        preset_label.setFont(typography.small())
        preset_label.setStyleSheet(f"color: {palette.text_tertiary}; letter-spacing: 1.2px;")
        presets.addWidget(preset_label)

        self._preset_conservative = QPushButton("Conservative")
        self._preset_conservative.setProperty("variant", "ghost")
        self._preset_conservative.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preset_conservative.setToolTip(
            "Select only safe, low-risk rules. No registry or service changes."
        )
        self._preset_conservative.clicked.connect(lambda: self._apply_preset("conservative"))
        presets.addWidget(self._preset_conservative)

        self._preset_recommended = QPushButton("Recommended")
        self._preset_recommended.setProperty("variant", "cool")
        self._preset_recommended.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preset_recommended.setToolTip(
            "Select rules with low or safe risk — a balanced default."
        )
        self._preset_recommended.clicked.connect(lambda: self._apply_preset("recommended"))
        presets.addWidget(self._preset_recommended)

        self._preset_absolute = QPushButton("ABSOLUTE PERFORMANCE")
        self._preset_absolute.setProperty("variant", "brand")
        self._preset_absolute.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preset_absolute.setToolTip(
            "Select EVERY applicable rule — maximum throughput at the cost of "
            "battery, telemetry, and some Windows niceties. Reversible."
        )
        self._preset_absolute.clicked.connect(lambda: self._apply_preset("absolute"))
        presets.addWidget(self._preset_absolute)
        presets.addStretch()
        root.addLayout(presets)

        # -- Search / filter bar
        search_row = QHBoxLayout()
        search_row.setSpacing(10)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText(
            "Search rules by name, category, or what they do…"
        )
        self._search_box.setClearButtonEnabled(True)
        self._search_box.setFont(typography.body())
        self._search_box.textChanged.connect(self._apply_filter)
        search_row.addWidget(self._search_box, 1)

        self._match_label = QLabel("")
        self._match_label.setFont(typography.small())
        self._match_label.setStyleSheet(f"color: {palette.text_tertiary};")
        search_row.addWidget(self._match_label)
        root.addLayout(search_row)

        # -- Plan list (the cards live in this layout). We DO NOT add the
        # empty-state to it permanently because _on_plan() wipes the layout
        # to rebuild cards; the empty state is re-created on demand.
        self._list_container = QVBoxLayout()
        self._list_container.setSpacing(8)
        self._list_container.setContentsMargins(0, 0, 0, 0)
        root.addLayout(self._list_container)
        # Push every card up to the top so when the plan is shorter than the
        # viewport, the leftover space sits *between* the list and the docked
        # footer as plain bg, instead of stretching the cards.
        root.addStretch(1)

        self._empty_state: Optional[QLabel] = None
        self._show_empty_state(
            "Click Re-analyze to scan your system and build the plan."
        )

        # ---- Footer (lives OUTSIDE the scroll area) ----------------------
        # This keeps the apply button pinned to the bottom of the viewport
        # regardless of plan length. We deliberately do NOT draw a top
        # border here: when the plan is shorter than the viewport, a hard
        # divider line would make the empty bg read as a gap. Without it,
        # the leftover space flows naturally into the apply row.
        footer_wrap = QWidget()
        footer_wrap.setObjectName("optimizeFooter")
        footer_wrap.setStyleSheet(
            f"#optimizeFooter {{ background: {palette.bg_base}; }}"
        )
        footer_outer = QVBoxLayout(footer_wrap)
        footer_outer.setContentsMargins(32, 10, 32, 14)
        footer_outer.setSpacing(0)

        footer = QHBoxLayout()
        footer.setSpacing(12)

        self.selected_label = QLabel("0 of 0 actions selected")
        self.selected_label.setFont(typography.body())
        self.selected_label.setStyleSheet(f"color: {palette.text_secondary};")
        footer.addWidget(self.selected_label)

        self.impact_pill = QLabel("IMPACT · —")
        self.impact_pill.setFont(typography.micro())
        self.impact_pill.setStyleSheet(
            f"color: {palette.accent}; letter-spacing: 1.6px;"
            f"background: {palette.accent_dim}; border-radius: 10px; padding: 4px 10px;"
        )
        footer.addWidget(self.impact_pill)

        footer.addStretch()

        self.restore_point_hint = QLabel("Restore point will be created before apply.")
        self.restore_point_hint.setFont(typography.small())
        self.restore_point_hint.setStyleSheet(f"color: {palette.text_tertiary};")
        footer.addWidget(self.restore_point_hint)

        self.apply_btn = QPushButton("Apply selected")
        self.apply_btn.setProperty("variant", "primary")
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._apply)
        footer.addWidget(self.apply_btn)

        footer_outer.addLayout(footer)
        outer.addWidget(footer_wrap, stretch=0)

        # -- bind VM
        self._vm.plan_ready.connect(self._on_plan)
        self._vm.plan_applied.connect(self._on_applied)
        self._vm.plan_refreshed.connect(self._on_plan_refreshed)

    # ------------------------------------------------------------------ actions
    def refresh(self) -> None:
        self._regenerate()

    def _regenerate(self) -> None:
        self._vm.regenerate()

    def _apply(self) -> None:
        if not self._plan:
            return
        selected = [a for a in self._plan.actions if a.selected]
        if not selected:
            return
        reply = QMessageBox.question(
            self,
            "Apply optimization plan",
            f"Apply {len(selected)} selected action(s) now?\n\n"
            f"A system restore point will be created first if your configuration allows it. "
            f"Every reversible action is rolled back instantly from the Safety tab.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.apply_btn.setEnabled(False)
        self.apply_btn.setText("Applying…")
        self._vm.apply(self._plan)

    # ------------------------------------------------------------------ vm handlers
    def _on_plan(self, plan: OptimizationPlan) -> None:
        self._plan = plan
        self._vm.current_plan = plan
        # Clear existing cards (and empty-state, if present)
        while self._list_container.count():
            item = self._list_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        # The label above was just deleted — drop our cached reference so
        # we rebuild a fresh one next time.
        self._empty_state = None
        self._cards.clear()

        if not plan.actions:
            self._show_empty_state(
                "No recommendations — your machine is already well-tuned. "
                "Re-analyze anytime your usage changes."
            )
            self.apply_btn.setEnabled(False)
            self._update_footer()
            self._apply_filter()
            return

        last_applied = self._build_last_applied_map()
        for planned in plan.actions:
            card = ActionCard(
                planned,
                palette=self._pal,
                typography=self._type,
                last_applied_ts=last_applied.get(planned.rule.id),
            )
            card.selection_changed.connect(lambda _id, _sel: self._update_footer())
            self._cards.append(card)
            self._list_container.addWidget(card)

        self.apply_btn.setEnabled(True)
        self._update_footer()
        self._apply_filter()

    def _show_empty_state(self, message: str) -> None:
        """Render a fresh empty-state QLabel inside the list container.

        We always re-create the widget — keeping a long-lived reference is
        not safe because :meth:`_on_plan` deletes everything in the list
        container when it rebuilds the card list.
        """
        label = QLabel(message)
        label.setWordWrap(True)
        label.setFont(self._type.body())
        label.setStyleSheet(
            f"color: {self._pal.text_secondary};"
            f"padding: 18px 22px;"
            f"background: {self._pal.bg_sunken};"
            f"border: 1px dashed {self._pal.border_soft};"
            f"border-radius: 12px;"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._list_container.addWidget(label)
        self._empty_state = label

    def _on_plan_refreshed(self, plan: OptimizationPlan) -> None:
        """Called when applicability changed (apply/rollback) — update badges."""
        self._plan = plan
        # Patch each existing card's model without rebuilding UI
        for card in self._cards:
            for action in plan.actions:
                if action.rule.id == card.planned.rule.id:
                    card.planned = action
                    card._refresh_badges()
        self._update_footer()

    # ------------------------------------------------------------------ filtering
    def _apply_filter(self) -> None:
        query = self._search_box.text().strip().lower() if hasattr(self, "_search_box") else ""
        shown = 0
        for card in self._cards:
            rule = card.planned.rule
            text = " ".join([rule.id, rule.title, rule.category, rule.what, rule.why]).lower()
            is_match = not query or query in text
            card.setVisible(is_match)
            if is_match:
                shown += 1
        total = len(self._cards)
        if not total:
            self._match_label.setText("")
        elif query:
            self._match_label.setText(f"{shown} / {total} rules match")
        else:
            self._match_label.setText(f"{total} rules")

    def _build_last_applied_map(self) -> dict:
        """Return {rule_id: most_recent_applied_ts} from history."""
        ctrl = getattr(self._vm, "controller", None)
        history = getattr(ctrl, "history", None) if ctrl else None
        if history is None:
            return {}
        out: dict = {}
        try:
            for rec in history.all():
                if rec.category != "optimize" or rec.status != "applied":
                    continue
                prev = out.get(rec.action)
                if prev is None or rec.ts > prev:
                    out[rec.action] = rec.ts
        except Exception:
            return {}
        return out

    def _on_applied(self, report) -> None:
        self.apply_btn.setEnabled(True)
        self.apply_btn.setText("Apply selected")

        # Build the detailed per-rule result list for the dialog.
        results: List[RuleResult] = [
            RuleResult(
                rule_id=r.rule_id,
                title=r.title,
                status=r.status,
                detail=r.detail,
                admin_required=r.admin_required,
            )
            for r in getattr(report, "results", [])
        ]
        dlg = ApplyReportDialog(
            results=results,
            restore_point_created=report.restore_point_created,
            restore_point_reason=report.restore_point_reason,
            palette=self._pal,
            typography=self._type,
            parent=self,
        )
        dlg.exec()
        self._regenerate()

    # ------------------------------------------------------------------ presets
    def _apply_preset(self, preset: str) -> None:
        if not self._plan:
            return
        for action in self._plan.actions:
            rule = action.rule
            if preset == "conservative":
                action.selected = rule.risk == RISK_SAFE and not rule.requires_admin
            elif preset == "recommended":
                action.selected = rule.risk in (RISK_SAFE, RISK_LOW)
            elif preset == "absolute":
                action.selected = True  # every applicable rule, full send
            else:
                continue
        for card in self._cards:
            card.set_selected(card.planned.selected)
        self._update_footer()

    def _update_footer(self) -> None:
        if not self._plan:
            self.selected_label.setText("0 of 0 actions selected")
            self.impact_pill.setText("IMPACT · —")
            self.apply_btn.setEnabled(False)
            self.admin_warning.setVisible(False)
            return
        total = len(self._plan.actions)
        selected = sum(1 for a in self._plan.actions if a.selected)
        self.selected_label.setText(
            f"{selected} of {total} action{'s' if total != 1 else ''} selected"
        )

        # Show admin warning if any selected rule needs elevation & we don't have it
        if not self._vm.is_admin and any(
            a.selected and a.rule.requires_admin for a in self._plan.actions
        ):
            self.admin_warning.setVisible(True)
        else:
            self.admin_warning.setVisible(False)
        score = self._plan.expected_score
        label = "LOW" if score < 33 else "MEDIUM" if score < 66 else "HIGH"
        self.impact_pill.setText(f"IMPACT · {label} ({score}/100)")
        color = (self._pal.text_secondary if score == 0
                 else self._pal.amber if score < 33
                 else self._pal.accent if score < 66
                 else self._pal.violet)
        bg = (self._pal.border if score == 0
              else self._pal.risk_dim("medium") if score < 33
              else self._pal.accent_dim if score < 66
              else self._pal.violet_dim)
        self.impact_pill.setStyleSheet(
            f"color: {color}; letter-spacing: 1.6px;"
            f"background: {bg}; border-radius: 10px; padding: 4px 10px;"
        )
        self.apply_btn.setEnabled(selected > 0)
