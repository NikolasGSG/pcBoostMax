"""Overlay settings view — configure the in-game HUD.

Toggles, metric picks, position, opacity, hotkey binding and live preview.
All changes persist to ``AppConfig`` and are pushed to the :class:`OverlayWindow`
so the HUD updates in real time.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ...core.app_controller import AppController
from ...overlay.overlay_window import OverlayConfig
from ..theme.palette import Palette
from ..theme.typography import Typography
from ..widgets.banner import Banner
from ..widgets.section import Card, DividerLine, SectionHeader
from ..widgets.toggle_switch import ToggleSwitch


def overlay_config_from_app_config(c) -> OverlayConfig:
    """Build an :class:`OverlayConfig` from a live :class:`AppConfig`.

    Free-function so callers can derive a HUD config without first
    instantiating an :class:`OverlayView` — useful for lazy view loading.
    """
    return OverlayConfig(
        enabled=c.overlay_enabled,
        position=c.overlay_position,
        opacity=c.overlay_opacity,
        click_through=c.overlay_click_through,
        show_fps=c.overlay_show_fps,
        show_cpu=c.overlay_show_cpu,
        show_gpu=c.overlay_show_gpu,
        show_ram=c.overlay_show_ram,
        show_net=c.overlay_show_net,
        show_disk=c.overlay_show_disk,
        show_frametime=c.overlay_show_frametime,
        show_process=c.overlay_show_process,
        compact=c.overlay_compact,
    )


class OverlayView(QWidget):
    """Settings UI for the in-game overlay."""

    config_changed = pyqtSignal(OverlayConfig)
    toggle_requested = pyqtSignal()

    _POSITIONS = [
        ("top-left", "Top-left"),
        ("top-right", "Top-right"),
        ("bottom-left", "Bottom-left"),
        ("bottom-right", "Bottom-right"),
    ]
    _KEYS = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
             "O", "H", "G", "P", "HOME", "END", "INSERT", "DELETE"]

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
        self._toggles: dict[str, ToggleSwitch] = {}

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

        # -- Header + main toggle button
        self.toggle_btn = QPushButton("Enable overlay")
        self.toggle_btn.setProperty("variant", "primary")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle_requested.emit)

        root.addWidget(SectionHeader(
            "IN-GAME HUD", "A lightweight overlay that stays on top of your game",
            palette=palette, typography=typography,
            trailing=self.toggle_btn,
            eyebrow_color=palette.chart_gpu,
        ))

        # -- FPS source banner
        fps_source = self._ctrl.fps.source
        if fps_source == "presentmon":
            msg = "PresentMon detected — showing true per-process FPS."
            role = "info"
        else:
            msg = ("Showing GPU-activity proxy (not a true FPS). Drop PresentMon.exe next "
                   "to this app's folder to enable real per-process frame-rate measurement.")
            role = "warn"
        root.addWidget(Banner(msg, palette=palette, typography=typography, role=role))

        # -- Position + Opacity
        layout_card = Card(palette=palette, padding=22)
        layout_card.body().addWidget(SectionHeader(
            "Layout", "Position, size and transparency",
            palette=palette, typography=typography,
            eyebrow_color=palette.accent,
        ))

        # Position radio grid
        pos_row = QHBoxLayout()
        pos_row.setSpacing(8)
        self._pos_group = QButtonGroup(self)
        self._pos_buttons: dict[str, QRadioButton] = {}
        for pid, label in self._POSITIONS:
            rb = QRadioButton(label)
            rb.setFont(typography.body())
            rb.setCursor(Qt.CursorShape.PointingHandCursor)
            rb.toggled.connect(lambda on, p=pid: on and self._set_position(p))
            self._pos_group.addButton(rb)
            self._pos_buttons[pid] = rb
            pos_row.addWidget(rb)
        pos_row.addStretch()
        layout_card.body().addLayout(pos_row)

        # Opacity slider
        op_row = QHBoxLayout()
        op_row.setSpacing(14)
        op_label = QLabel("Opacity")
        op_label.setFont(typography.body())
        op_label.setFixedWidth(80)
        op_row.addWidget(op_label)
        self._opacity = QSlider(Qt.Orientation.Horizontal)
        self._opacity.setRange(40, 100)
        self._opacity.valueChanged.connect(self._set_opacity)
        op_row.addWidget(self._opacity, 1)
        self._opacity_value = QLabel("85%")
        self._opacity_value.setFixedWidth(40)
        self._opacity_value.setFont(typography.body_strong())
        op_row.addWidget(self._opacity_value)
        layout_card.body().addLayout(op_row)

        # Click-through + compact toggles
        layout_card.body().addLayout(self._toggle_row(
            "click_through",
            "Click-through (ignore mouse)",
            "Let mouse clicks pass through the HUD to the game underneath.",
        ))
        layout_card.body().addLayout(self._toggle_row(
            "compact",
            "Compact layout",
            "Hide process line and graph — ideal for small monitors.",
        ))
        root.addWidget(layout_card)

        # -- Metrics card
        metrics_card = Card(palette=palette, padding=22)
        metrics_card.body().addWidget(SectionHeader(
            "Metrics", "What to show in the HUD",
            palette=palette, typography=typography,
            eyebrow_color=palette.violet,
        ))

        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(4)
        rows = [
            ("show_fps", "Frames per second"),
            ("show_frametime", "Frame time (ms)"),
            ("show_cpu", "CPU usage"),
            ("show_gpu", "GPU usage"),
            ("show_ram", "RAM usage"),
            ("show_net", "Network throughput"),
            ("show_disk", "Disk throughput"),
            ("show_process", "Foreground process"),
        ]
        for i, (key, label) in enumerate(rows):
            col = i % 2
            row = i // 2
            wrap = QWidget()
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(0, 6, 0, 6)
            wl.setSpacing(10)
            t = QLabel(label)
            t.setFont(typography.body())
            wl.addWidget(t, 1)
            toggle = ToggleSwitch(palette)
            toggle.toggled.connect(lambda v, k=key: self._set_attr(k, v))
            self._toggles[key] = toggle
            wl.addWidget(toggle)
            grid.addWidget(wrap, row, col)
        metrics_card.body().addLayout(grid)
        root.addWidget(metrics_card)

        # -- Hotkey card
        hk_card = Card(palette=palette, padding=22)
        hk_card.body().addWidget(SectionHeader(
            "Hotkey", "Toggle the overlay from inside a game",
            palette=palette, typography=typography,
            eyebrow_color=palette.amber,
        ))

        hk_row = QHBoxLayout()
        hk_row.setSpacing(8)

        self._hk_ctrl = self._mod_button("Ctrl")
        self._hk_shift = self._mod_button("Shift")
        self._hk_alt = self._mod_button("Alt")
        self._hk_ctrl.toggled.connect(lambda v: self._set_attr("hotkey_ctrl", v))
        self._hk_shift.toggled.connect(lambda v: self._set_attr("hotkey_shift", v))
        self._hk_alt.toggled.connect(lambda v: self._set_attr("hotkey_alt", v))
        hk_row.addWidget(self._hk_ctrl)
        hk_row.addWidget(self._hk_shift)
        hk_row.addWidget(self._hk_alt)

        plus = QLabel("+")
        plus.setFont(typography.body_strong())
        hk_row.addWidget(plus)

        self._hk_key = QComboBox()
        self._hk_key.addItems(self._KEYS)
        self._hk_key.currentTextChanged.connect(lambda t: self._set_attr("hotkey_key", t))
        hk_row.addWidget(self._hk_key)
        hk_row.addStretch()

        hk_card.body().addLayout(hk_row)
        hk_card.body().addWidget(DividerLine(palette))
        hk_card.body().addLayout(self._toggle_row(
            "auto_show_game",
            "Auto-show when a fullscreen game is detected",
            "Automatically pop the HUD the first time a fullscreen foreground app is seen.",
        ))
        root.addWidget(hk_card)

        root.addStretch()

        self._load_from_config()

    # ------------------------------------------------------------------ state
    def _load_from_config(self) -> None:
        c = self._ctrl.config
        self._pos_buttons[c.overlay_position].setChecked(True)
        self._opacity.setValue(c.overlay_opacity)
        self._opacity_value.setText(f"{c.overlay_opacity}%")
        self._toggles["click_through"].setChecked(c.overlay_click_through)
        self._toggles["compact"].setChecked(c.overlay_compact)
        self._toggles["show_fps"].setChecked(c.overlay_show_fps)
        self._toggles["show_frametime"].setChecked(c.overlay_show_frametime)
        self._toggles["show_cpu"].setChecked(c.overlay_show_cpu)
        self._toggles["show_gpu"].setChecked(c.overlay_show_gpu)
        self._toggles["show_ram"].setChecked(c.overlay_show_ram)
        self._toggles["show_net"].setChecked(c.overlay_show_net)
        self._toggles["show_disk"].setChecked(c.overlay_show_disk)
        self._toggles["show_process"].setChecked(c.overlay_show_process)
        self._toggles["auto_show_game"].setChecked(c.overlay_auto_show_game)
        self._hk_ctrl.setChecked(c.overlay_hotkey_ctrl)
        self._hk_shift.setChecked(c.overlay_hotkey_shift)
        self._hk_alt.setChecked(c.overlay_hotkey_alt)
        idx = max(0, self._KEYS.index(c.overlay_hotkey_key) if c.overlay_hotkey_key in self._KEYS else 11)
        self._hk_key.setCurrentIndex(idx)
        self.set_overlay_active(c.overlay_enabled)

    def set_overlay_active(self, active: bool) -> None:
        self.toggle_btn.setText("Hide overlay" if active else "Enable overlay")
        self.toggle_btn.setProperty("variant", "danger" if active else "primary")
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)

    def current_overlay_config(self) -> OverlayConfig:
        return overlay_config_from_app_config(self._ctrl.config)

    # ------------------------------------------------------------------ handlers
    def _set_position(self, pos: str) -> None:
        self._ctrl.config.update(overlay_position=pos)
        self.config_changed.emit(self.current_overlay_config())

    def _set_opacity(self, val: int) -> None:
        self._opacity_value.setText(f"{val}%")
        self._ctrl.config.update(overlay_opacity=int(val))
        self.config_changed.emit(self.current_overlay_config())

    def _set_attr(self, short_key: str, value) -> None:
        self._ctrl.config.update(**{f"overlay_{short_key}": value})
        self.config_changed.emit(self.current_overlay_config())

    # ------------------------------------------------------------------ UI helpers
    def _toggle_row(self, key: str, title: str, subtitle: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 8, 0, 8)
        row.setSpacing(18)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        t = QLabel(title)
        t.setFont(self._type.body_strong())
        s = QLabel(subtitle)
        s.setFont(self._type.small())
        s.setWordWrap(True)
        s.setStyleSheet(f"color: {self._pal.text_secondary};")
        texts.addWidget(t)
        texts.addWidget(s)
        row.addLayout(texts, 1)
        tog = ToggleSwitch(self._pal)
        tog.toggled.connect(lambda v, k=key: self._set_attr(k, v))
        self._toggles[key] = tog
        row.addWidget(tog, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        return row

    def _mod_button(self, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("variant", "mod")
        btn.setMinimumWidth(70)
        return btn
