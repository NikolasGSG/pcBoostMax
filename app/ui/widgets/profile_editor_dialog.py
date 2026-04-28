"""Per-game profile editor — modal dialog launched from the Game Hub.

Edits one :class:`GameProfile` in-place. On *Save* the profile is
persisted via :class:`GameProfileService.save` and the change is
announced on the bus so any open Game Hub tiles refresh their state.

Layout sections:
    * Header — game name + enable/disable switch
    * Power Plan + Process Priority + FPS cap
    * CPU Affinity (visual core grid)
    * Background processes to suspend
    * Exe matchers (one per line)
    * Save / Cancel footer

Style closely follows the existing Settings view: HudFrame + spaced
form rows.
"""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...games.profiles import GameProfile, GameProfileService
from ..theme.palette import Palette
from ..theme.typography import Typography


_POWER_PLAN_OPTIONS = [
    ("ultimate",  "Ultimate Performance"),
    ("high",      "High Performance"),
    ("balanced",  "Balanced (default)"),
    ("off",       "Don't change"),
]

_PRIORITY_OPTIONS = [
    ("normal",       "Normal"),
    ("above_normal", "Above Normal (recommended)"),
    ("high",         "High"),
    ("realtime",     "Realtime — risky"),
    ("off",          "Don't change"),
]


class ProfileEditorDialog(QDialog):
    def __init__(
        self,
        *,
        profile: GameProfile,
        service: GameProfileService,
        palette: Palette,
        typography: Typography,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._service = service
        self._pal = palette
        self._type = typography
        self.setWindowTitle(f"Profile — {profile.name}")
        self.setMinimumWidth(640)
        self.setStyleSheet(self._dialog_qss())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 22)
        outer.setSpacing(18)

        outer.addLayout(self._build_header())
        outer.addWidget(self._build_runtime_section())
        outer.addWidget(self._build_affinity_section())
        outer.addWidget(self._build_lists_section())
        outer.addStretch(1)
        outer.addLayout(self._build_footer())

        self._populate()

    # ------------------------------------------------------------------ sections
    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(14)

        col = QVBoxLayout()
        col.setSpacing(2)

        eyebrow = QLabel("PROFILE")
        eyebrow.setFont(self._type.eyebrow())
        eyebrow.setStyleSheet(f"color: {self._pal.accent};")
        col.addWidget(eyebrow)

        title = QLabel(self._profile.name or "Untitled")
        title.setFont(self._type.display_h1())
        title.setStyleSheet(f"color: {self._pal.text_primary};")
        col.addWidget(title)

        sub = QLabel("Tuning applied while the game is running. Reverts when it closes.")
        sub.setFont(self._type.body())
        sub.setStyleSheet(f"color: {self._pal.text_secondary};")
        sub.setWordWrap(True)
        col.addWidget(sub)

        row.addLayout(col, stretch=1)

        self._enabled_cb = QCheckBox("Enabled")
        self._enabled_cb.setStyleSheet(f"color: {self._pal.text_primary};")
        row.addWidget(self._enabled_cb, alignment=Qt.AlignmentFlag.AlignTop)
        return row

    def _build_runtime_section(self) -> QFrame:
        frame = self._section_frame("Runtime")
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        grid.setContentsMargins(0, 6, 0, 0)
        frame.layout().addLayout(grid)

        # Power plan
        grid.addWidget(self._field_label("Power plan"), 0, 0)
        self._power_combo = QComboBox()
        for value, label in _POWER_PLAN_OPTIONS:
            self._power_combo.addItem(label, value)
        grid.addWidget(self._power_combo, 0, 1)

        # Process priority
        grid.addWidget(self._field_label("Process priority"), 1, 0)
        self._priority_combo = QComboBox()
        for value, label in _PRIORITY_OPTIONS:
            self._priority_combo.addItem(label, value)
        grid.addWidget(self._priority_combo, 1, 1)

        # FPS cap
        grid.addWidget(self._field_label("FPS cap (HUD only)"), 2, 0)
        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(0, 360)
        self._fps_spin.setSpecialValueText("Uncapped")
        self._fps_spin.setSuffix(" Hz")
        grid.addWidget(self._fps_spin, 2, 1)

        # Disable Game Bar
        self._gamebar_cb = QCheckBox("Disable Xbox Game Bar overlay for this game")
        self._gamebar_cb.setStyleSheet(f"color: {self._pal.text_primary};")
        grid.addWidget(self._gamebar_cb, 3, 0, 1, 2)
        return frame

    def _build_affinity_section(self) -> QFrame:
        frame = self._section_frame("CPU affinity")
        sub = QLabel("Pick which logical cores the game can use. Leave all checked for default behaviour.")
        sub.setFont(self._type.body())
        sub.setStyleSheet(f"color: {self._pal.text_secondary};")
        sub.setWordWrap(True)
        frame.layout().addWidget(sub)

        try:
            import psutil
            core_count = psutil.cpu_count() or 0
        except Exception:
            core_count = 0
        core_count = min(64, max(0, core_count))

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(0, 8, 0, 0)
        self._core_cbs: List[QCheckBox] = []
        cols = 8
        for i in range(core_count):
            cb = QCheckBox(f"#{i}")
            cb.setStyleSheet(f"color: {self._pal.text_primary};")
            grid.addWidget(cb, i // cols, i % cols)
            self._core_cbs.append(cb)
        frame.layout().addLayout(grid)
        if not self._core_cbs:
            note = QLabel("Could not enumerate CPU cores on this system.")
            note.setStyleSheet(f"color: {self._pal.text_tertiary};")
            frame.layout().addWidget(note)
        return frame

    def _build_lists_section(self) -> QFrame:
        frame = self._section_frame("Background process control")
        sub = QLabel("Process names to suspend while this game runs (one per line). Resumes automatically on exit.")
        sub.setFont(self._type.body())
        sub.setStyleSheet(f"color: {self._pal.text_secondary};")
        sub.setWordWrap(True)
        frame.layout().addWidget(sub)

        self._suspend_text = QPlainTextEdit()
        self._suspend_text.setPlaceholderText("e.g. spotify.exe, OneDrive.exe")
        self._suspend_text.setFixedHeight(90)
        frame.layout().addWidget(self._suspend_text)

        sub2 = QLabel("Executable matchers (used to auto-apply when the game launches)")
        sub2.setFont(self._type.body())
        sub2.setStyleSheet(f"color: {self._pal.text_secondary};")
        frame.layout().addWidget(sub2)

        self._exe_text = QPlainTextEdit()
        self._exe_text.setPlaceholderText("e.g. cs2.exe")
        self._exe_text.setFixedHeight(70)
        frame.layout().addWidget(self._exe_text)
        return frame

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)

        save = QPushButton("Save profile")
        save.setDefault(True)
        save.setObjectName("primary")
        save.clicked.connect(self._on_save)
        row.addWidget(save)
        return row

    # ------------------------------------------------------------------ helpers
    def _section_frame(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        eyebrow = QLabel(title.upper())
        eyebrow.setFont(self._type.eyebrow())
        eyebrow.setStyleSheet(f"color: {self._pal.accent};")
        layout.addWidget(eyebrow)
        return frame

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(self._type.body())
        lbl.setStyleSheet(f"color: {self._pal.text_secondary};")
        return lbl

    def _populate(self) -> None:
        p = self._profile
        self._enabled_cb.setChecked(p.enabled)
        self._select_combo(self._power_combo, p.power_plan)
        self._select_combo(self._priority_combo, p.process_priority)
        self._fps_spin.setValue(int(p.fps_cap_hz or 0))
        self._gamebar_cb.setChecked(p.disable_gamebar)
        self._suspend_text.setPlainText("\n".join(p.suspend_processes or []))
        self._exe_text.setPlainText("\n".join(p.exe_match or []))

        if self._core_cbs:
            mask = p.process_affinity_mask
            for i, cb in enumerate(self._core_cbs):
                if mask is None:
                    cb.setChecked(True)
                else:
                    cb.setChecked(bool(mask & (1 << i)))

    @staticmethod
    def _select_combo(combo: QComboBox, value: str) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
        combo.setCurrentIndex(0)

    # ------------------------------------------------------------------ save
    def _on_save(self) -> None:
        p = self._profile
        p.enabled = self._enabled_cb.isChecked()
        p.power_plan = self._power_combo.currentData() or "ultimate"
        p.process_priority = self._priority_combo.currentData() or "above_normal"
        p.fps_cap_hz = int(self._fps_spin.value())
        p.disable_gamebar = self._gamebar_cb.isChecked()
        p.suspend_processes = [
            line.strip() for line in self._suspend_text.toPlainText().splitlines()
            if line.strip()
        ]
        p.exe_match = [
            line.strip() for line in self._exe_text.toPlainText().splitlines()
            if line.strip()
        ]

        # CPU affinity mask (None = all cores or unset)
        if self._core_cbs:
            mask = 0
            all_checked = True
            for i, cb in enumerate(self._core_cbs):
                if cb.isChecked():
                    mask |= (1 << i)
                else:
                    all_checked = False
            p.process_affinity_mask = None if all_checked else (mask or None)

        try:
            self._service.save(p)
        except Exception:
            from ...utils.logger import get_logger
            get_logger("ui.profile_editor").exception("save failed")
        self.accept()

    # ------------------------------------------------------------------ qss
    def _dialog_qss(self) -> str:
        p = self._pal
        return f"""
QDialog {{
    background: {p.bg_base};
}}
QFrame#card {{
    background: {p.bg_elevated};
    border: 1px solid {p.border};
    border-radius: 12px;
}}
QComboBox, QSpinBox, QPlainTextEdit, QLineEdit {{
    background: {p.bg_sunken};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 6px 10px;
}}
QPlainTextEdit {{
    padding: 8px;
}}
QPushButton {{
    background: {p.bg_elevated};
    color: {p.text_primary};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 8px 18px;
}}
QPushButton:hover {{
    background: {p.bg_surface};
}}
QPushButton#primary {{
    background: {p.accent};
    color: {p.text_on_accent};
    border: none;
}}
QPushButton#primary:hover {{
    background: {p.accent_hover};
}}
"""
