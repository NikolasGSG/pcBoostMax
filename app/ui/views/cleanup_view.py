"""Cleanup view — scan → preview → delete with per-category totals."""
from __future__ import annotations

from typing import Dict, List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...cleanup.cleaner import CleanupFile, CleanupScanResult
from ...utils.formatting import human_bytes
from ..theme.palette import Palette
from ..theme.typography import Typography
from ..viewmodels.cleanup_vm import CleanupViewModel
from ..widgets.banner import Banner
from ..widgets.section import Card, DividerLine, SectionHeader


class CleanupView(QWidget):
    def __init__(
        self,
        vm: CleanupViewModel,
        palette: Palette,
        typography: Typography,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._vm = vm
        self._pal = palette
        self._type = typography
        self._files_by_category: Dict[str, List[CleanupFile]] = {}

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
        self.scan_btn = QPushButton("Scan now")
        self.scan_btn.setProperty("variant", "primary")
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.clicked.connect(self._on_scan)

        root.addWidget(SectionHeader(
            "DISK CLEANUP", "Reclaim space from temp & cache folders",
            palette=palette, typography=typography,
            trailing=self.scan_btn,
            eyebrow_color=palette.amber,
        ))

        # -- Banner
        root.addWidget(Banner(
            "Nothing is deleted until you press Delete selected. The table shows "
            "every file that will be removed, grouped by category.",
            palette=palette, typography=typography, role="warn",
        ))

        # -- Category selection
        cats_row = QHBoxLayout()
        cats_row.setSpacing(18)
        self._category_checks: Dict[str, QCheckBox] = {}
        for cat in vm.categories:
            cb = QCheckBox(cat.label)
            cb.setChecked(True)
            cb.setToolTip(cat.description)
            cb.setFont(typography.body())
            self._category_checks[cat.id] = cb
            cats_row.addWidget(cb)
        cats_row.addStretch()
        root.addLayout(cats_row)

        # -- Summary line + progress
        self.summary_label = QLabel("Ready to scan.")
        self.summary_label.setFont(typography.body())
        self.summary_label.setStyleSheet(f"color: {palette.text_secondary};")
        root.addWidget(self.summary_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setFixedHeight(6)
        root.addWidget(self.progress)

        # -- Results tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Target", "Size", "Modified"])
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setMinimumHeight(280)
        self.tree.setFont(typography.small())
        self.tree.setStyleSheet(f"QTreeWidget::item {{ padding: 4px 8px; }}")
        root.addWidget(self.tree)

        # -- Footer
        root.addWidget(DividerLine(palette))
        footer = QHBoxLayout()
        self.recoverable_label = QLabel("Recoverable: —")
        self.recoverable_label.setFont(typography.body_strong())
        footer.addWidget(self.recoverable_label)
        footer.addStretch()
        self.delete_btn = QPushButton("Delete selected")
        self.delete_btn.setProperty("variant", "danger")
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete)
        footer.addWidget(self.delete_btn)
        root.addLayout(footer)

        # -- VM bindings
        vm.scan_finished.connect(self._on_scan_done)
        vm.scan_failed.connect(self._on_scan_failed)
        vm.scan_progress.connect(self._on_scan_progress)
        vm.deleted.connect(self._on_deleted)

    # ------------------------------------------------------------------ actions
    def _on_scan(self) -> None:
        wanted = [cat_id for cat_id, cb in self._category_checks.items() if cb.isChecked()]
        if not wanted:
            QMessageBox.information(self, "Cleanup", "Select at least one category to scan.")
            return
        self.tree.clear()
        self._files_by_category.clear()
        self.recoverable_label.setText("Recoverable: scanning…")
        self.summary_label.setText("Scanning — this may take a few seconds.")
        self.progress.setVisible(True)
        self.scan_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self._vm.scan(wanted)

    def _on_scan_progress(self, path: str, scanned: int) -> None:
        self.summary_label.setText(f"Scanned {scanned} files… current: {path}")

    def _on_scan_done(self, result: CleanupScanResult) -> None:
        self.progress.setVisible(False)
        self.scan_btn.setEnabled(True)

        by_cat = result.by_category()
        self._files_by_category = by_cat

        labels = {cat.id: cat.label for cat in self._vm.categories}
        for cat_id, files in by_cat.items():
            cat_total = sum(f.size for f in files)
            parent = QTreeWidgetItem([
                f"{labels.get(cat_id, cat_id)} — {len(files)} files",
                human_bytes(cat_total),
                "",
            ])
            # Avoid building a 50k-row tree; show first 400 per category
            for cf in files[:400]:
                child = QTreeWidgetItem([
                    str(cf.path),
                    human_bytes(cf.size),
                    "",
                ])
                parent.addChild(child)
            if len(files) > 400:
                parent.addChild(QTreeWidgetItem([f"… and {len(files) - 400} more files", "", ""]))
            self.tree.addTopLevelItem(parent)
            parent.setExpanded(False)

        total = result.total_bytes
        self.recoverable_label.setText(f"Recoverable: {human_bytes(total)}")
        if total == 0:
            self.summary_label.setText("Nothing to reclaim in the selected categories.")
            self.delete_btn.setEnabled(False)
        else:
            self.summary_label.setText(
                f"Found {len(result.files):,} files across "
                f"{len(by_cat)} categor{'ies' if len(by_cat) != 1 else 'y'}."
            )
            self.delete_btn.setEnabled(True)

    def _on_scan_failed(self, reason: str) -> None:
        self.progress.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.summary_label.setText(f"Scan failed: {reason}")

    def _on_delete(self) -> None:
        total_files = sum(len(v) for v in self._files_by_category.values())
        total_bytes = sum(sum(f.size for f in v) for v in self._files_by_category.values())
        if total_files == 0:
            return
        reply = QMessageBox.question(
            self,
            "Confirm cleanup",
            f"Permanently delete {total_files:,} files ({human_bytes(total_bytes)})?\n\n"
            "Locked files (in use by running apps) are skipped automatically.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        flat: List[CleanupFile] = [f for lst in self._files_by_category.values() for f in lst]
        self.delete_btn.setEnabled(False)
        self._vm.delete(flat)

    def _on_deleted(self, result) -> None:
        self.tree.clear()
        self._files_by_category.clear()
        msg = (
            f"Deleted {result.deleted:,} files, freed {human_bytes(result.bytes_freed)}."
            + (f" {result.skipped} skipped." if result.skipped else "")
        )
        self.summary_label.setText(msg)
        self.recoverable_label.setText("Recoverable: —")
        self.delete_btn.setEnabled(False)
