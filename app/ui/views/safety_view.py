"""Safety view — action history, per-action rollback, restore-point status, export."""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.app_controller import AppController
from ...safety.action_history import ActionRecord
from ..theme.palette import Palette
from ..theme.typography import Typography
from ..widgets.badge import Badge, risk_badge
from ..widgets.banner import Banner
from ..widgets.section import Card, DividerLine, SectionHeader


class SafetyView(QWidget):
    def __init__(
        self,
        controller: AppController,
        palette: Palette,
        typography: Typography,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._ctrl = controller
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

        # -- Header + actions
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)

        self.create_rp_btn = QPushButton("Create restore point")
        self.create_rp_btn.setProperty("variant", "ghost")
        self.create_rp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.create_rp_btn.clicked.connect(self._create_restore_point)
        buttons_row.addWidget(self.create_rp_btn)

        self.export_btn = QPushButton("Export history (JSON)")
        self.export_btn.setProperty("variant", "ghost")
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.clicked.connect(self._export)
        buttons_row.addWidget(self.export_btn)

        wrap = QWidget()
        wrap.setLayout(buttons_row)

        root.addWidget(SectionHeader(
            "SAFETY & HISTORY", "Every change this tool has made",
            palette=palette, typography=typography,
            trailing=wrap,
            eyebrow_color=palette.accent,
        ))

        # -- Restore point status
        self.rp_banner = Banner("Checking restore point status…", palette=palette, typography=typography, role="info")
        root.addWidget(self.rp_banner)

        # -- History tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["When", "Category", "Action", "Status", "Risk"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        h = self.tree.header()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setMinimumHeight(260)
        self.tree.setFont(typography.small())
        self.tree.itemSelectionChanged.connect(self._on_select)
        root.addWidget(self.tree)

        # -- Footer: rollback selected
        root.addWidget(DividerLine(palette))
        footer = QHBoxLayout()
        self.selection_label = QLabel("Select an action to roll back.")
        self.selection_label.setFont(typography.body())
        self.selection_label.setStyleSheet(f"color: {palette.text_secondary};")
        footer.addWidget(self.selection_label)
        footer.addStretch()

        self.rollback_btn = QPushButton("Roll back selected")
        self.rollback_btn.setProperty("variant", "danger")
        self.rollback_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rollback_btn.setEnabled(False)
        self.rollback_btn.clicked.connect(self._rollback_selected)
        footer.addWidget(self.rollback_btn)

        root.addLayout(footer)
        root.addStretch()

        self.refresh()

    # ------------------------------------------------------------------ actions
    def refresh(self) -> None:
        # Restore point banner
        if self._ctrl.restore_points.is_supported():
            last = self._ctrl.restore_points.last_restore_point()
            if last:
                self.rp_banner.setText(f"Most recent restore point: {last}")
            else:
                self.rp_banner.setText(
                    "No existing restore point detected. "
                    "Use 'Create restore point' before your first optimization."
                )
        else:
            self.rp_banner.setText("System Restore is a Windows-only feature — other OS detected.")

        # Wire restorers so rollback works even if engine hasn't been touched
        self._ctrl.optimizer.bind_rollback(self._ctrl.rollback)

        # History
        self.tree.clear()
        for rec in self._ctrl.history.recent(200):
            self.tree.addTopLevelItem(self._record_to_item(rec))

    def _create_restore_point(self) -> None:
        res = self._ctrl.restore_points.create("GameBoostApex: manual")
        if res.created:
            QMessageBox.information(self, "Restore point", "Restore point created successfully.")
        else:
            QMessageBox.warning(self, "Restore point", res.reason or "Could not create restore point.")
        self.refresh()

    def _export(self) -> None:
        default = str(Path.home() / "Downloads" / "gameboostapex-actions.json")
        path, _ = QFileDialog.getSaveFileName(self, "Export action history", default, "JSON files (*.json)")
        if not path:
            return
        count = self._ctrl.history.export(path)
        QMessageBox.information(self, "Export complete", f"Wrote {count} actions to {path}.")

    def _on_select(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            self.rollback_btn.setEnabled(False)
            self.selection_label.setText("Select an action to roll back.")
            return
        rec: ActionRecord = items[0].data(0, Qt.ItemDataRole.UserRole)
        if self._ctrl.rollback.available_for(rec):
            self.rollback_btn.setEnabled(True)
            self.selection_label.setText(f"Ready to roll back: {rec.summary}")
        else:
            self.rollback_btn.setEnabled(False)
            reason = (
                "already rolled back" if rec.status == "rolled_back"
                else "not reversible" if not rec.reversible
                else "no backup stored"
            )
            self.selection_label.setText(f"Can't roll back ({reason}): {rec.summary}")

    def _rollback_selected(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            return
        rec: ActionRecord = items[0].data(0, Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Roll back",
                                f"Roll back:\n\n{rec.summary}\n\nContinue?") != QMessageBox.StandardButton.Yes:
            return
        ok = self._ctrl.rollback.rollback_action(rec)
        if ok:
            QMessageBox.information(self, "Rolled back", "Action reverted successfully.")
        else:
            QMessageBox.warning(self, "Rollback failed",
                                 "The action could not be reverted. Check logs for details.")
        self.refresh()

    # ------------------------------------------------------------------ helpers
    def _record_to_item(self, rec: ActionRecord) -> QTreeWidgetItem:
        dt = datetime.datetime.fromtimestamp(rec.ts).strftime("%Y-%m-%d %H:%M:%S")
        item = QTreeWidgetItem([dt, rec.category.upper(), rec.summary, rec.status.upper(), rec.risk.upper()])
        item.setData(0, Qt.ItemDataRole.UserRole, rec)
        # Colour status column
        color = {
            "applied": self._pal.accent,
            "rolled_back": self._pal.text_secondary,
            "failed": self._pal.coral,
            "skipped": self._pal.text_tertiary,
        }.get(rec.status, self._pal.text_primary)
        from PyQt6.QtGui import QBrush, QColor
        item.setForeground(3, QBrush(QColor(color)))
        item.setForeground(4, QBrush(QColor(self._pal.risk_color(rec.risk))))
        return item
