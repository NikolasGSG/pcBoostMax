"""Modal dialog that shows the outcome of applying an optimization plan.

Each row states whether a rule:
    - applied cleanly
    - failed (with reason)
    - applied, but a post-apply verification flagged that the change may not
      have stuck (often an admin-rights problem)

Purpose: give the user explicit, visual confirmation that each setting
either took effect or didn't, so they don't have to take "Applied N actions"
on faith.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..theme.palette import Palette
from ..theme.typography import Typography


@dataclass
class RuleResult:
    rule_id: str
    title: str
    status: str            # "applied" | "failed" | "needs_reboot" | "not_verified"
    detail: str = ""
    admin_required: bool = False


class _StatusBadge(QLabel):
    """Pill label coloured by status."""

    _STYLES = {
        "applied": ("OK", "accent"),
        "failed": ("FAILED", "coral"),
        "needs_reboot": ("REBOOT", "amber"),
        "not_verified": ("CHECK", "amber"),
    }

    def __init__(self, status: str, palette: Palette, typography: Typography, parent=None) -> None:
        label, role = self._STYLES.get(status, ("?", "accent"))
        super().__init__(label, parent)
        self.setFont(typography.micro())
        fg = {
            "accent": palette.accent, "coral": palette.coral, "amber": palette.amber,
        }[role]
        bg = {
            "accent": palette.accent_dim,
            "coral": palette.coral_dim,
            "amber": palette.amber_dim,
        }[role]
        self.setStyleSheet(
            f"color: {fg}; background: {bg}; border-radius: 6px; "
            f"padding: 3px 8px; letter-spacing: 1.2px; font-weight: 700;"
        )
        self.setFixedWidth(78)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class _ResultRow(QFrame):
    """Single rule → result line."""

    def __init__(self, result: RuleResult, palette: Palette, typography: Typography,
                 parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ResultRow")
        self.setStyleSheet(
            f"#ResultRow {{background: {palette.bg_elevated}; "
            f"border: 1px solid {palette.border}; border-radius: 10px;}}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(14)

        badge = _StatusBadge(result.status, palette, typography)
        layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        title = QLabel(result.title)
        title.setFont(typography.body_strong())
        text_box.addWidget(title)

        subtitle_parts: list[str] = []
        if result.rule_id:
            subtitle_parts.append(result.rule_id)
        if result.admin_required:
            subtitle_parts.append("needs admin")
        subtitle = " · ".join(subtitle_parts)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setFont(typography.small())
            sub.setStyleSheet(f"color: {palette.text_tertiary}; letter-spacing: 1px;")
            text_box.addWidget(sub)

        if result.detail:
            detail = QLabel(result.detail)
            detail.setFont(typography.small())
            detail.setWordWrap(True)
            detail.setStyleSheet(f"color: {palette.text_secondary};")
            text_box.addWidget(detail)

        layout.addLayout(text_box, 1)


class ApplyReportDialog(QDialog):
    """Scrollable per-rule status dialog."""

    def __init__(
        self,
        *,
        results: List[RuleResult],
        restore_point_created: bool,
        restore_point_reason: str,
        palette: Palette,
        typography: Typography,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Apply Report")
        self.setModal(True)
        self.resize(620, 520)
        self.setStyleSheet(f"QDialog {{ background: {palette.bg_base}; }}")

        applied = sum(1 for r in results if r.status == "applied")
        failed = sum(1 for r in results if r.status == "failed")
        reboot = sum(1 for r in results if r.status == "needs_reboot")
        noverify = sum(1 for r in results if r.status == "not_verified")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 20)
        outer.setSpacing(14)

        # ---- Header
        head_row = QHBoxLayout()
        head_row.setSpacing(10)
        title = QLabel("Apply Report")
        title.setFont(typography.h2())
        head_row.addWidget(title)
        head_row.addStretch()
        summary_bits = [f"{applied} OK"]
        if failed: summary_bits.append(f"{failed} failed")
        if reboot: summary_bits.append(f"{reboot} reboot")
        if noverify: summary_bits.append(f"{noverify} unverified")
        summary_lbl = QLabel("   ·   ".join(summary_bits))
        summary_lbl.setFont(typography.body_strong())
        summary_lbl.setStyleSheet(f"color: {palette.text_secondary};")
        head_row.addWidget(summary_lbl)
        outer.addLayout(head_row)

        # Restore point info
        rp_txt = ("System restore point created before applying."
                  if restore_point_created
                  else f"Restore point skipped: {restore_point_reason or 'not requested'}")
        rp = QLabel(rp_txt)
        rp.setFont(typography.small())
        rp.setStyleSheet(f"color: {palette.text_tertiary};")
        outer.addWidget(rp)

        # ---- Scrollable list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, 1)

        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)

        # Order: failed first, then needs_reboot/not_verified, then applied
        order = {"failed": 0, "needs_reboot": 1, "not_verified": 2, "applied": 3}
        for r in sorted(results, key=lambda x: order.get(x.status, 9)):
            col.addWidget(_ResultRow(r, palette, typography))
        col.addStretch()
        scroll.setWidget(container)

        # ---- Footer
        if failed or noverify:
            note = QLabel(
                "Tip: some settings require administrator rights. "
                "If several rows show FAILED or CHECK, re-run the app as Administrator."
            )
            note.setFont(typography.small())
            note.setWordWrap(True)
            note.setStyleSheet(
                f"color: {palette.amber}; background: {palette.amber_dim}; "
                f"border-radius: 8px; padding: 10px 14px;"
            )
            outer.addWidget(note)

        if reboot:
            note2 = QLabel(
                "Some changes (e.g. HAGS, registry-based graphics tweaks) only take effect "
                "after a Windows restart."
            )
            note2.setFont(typography.small())
            note2.setWordWrap(True)
            note2.setStyleSheet(
                f"color: {palette.chart_gpu}; background: {palette.bg_sunken}; "
                f"border-radius: 8px; padding: 10px 14px;"
            )
            outer.addWidget(note2)

        row = QHBoxLayout()
        row.addStretch()
        close = QPushButton("Done")
        close.setProperty("variant", "primary")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.accept)
        row.addWidget(close)
        outer.addLayout(row)
